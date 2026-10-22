"""Unit and integration tests for video steganography and video quality metrics."""

import math
import os
import struct
import zlib
import pytest
import numpy as np

from app.core.crypto_utils import generate_key, encrypt, decrypt
from app.evaluation.quality_metrics import (
    validate_video_frame_pairs,
    calculate_video_metrics,
)
from app.media.video_stego import (
    VIDEO_MAGIC,
    VIDEO_FORMAT_VERSION,
    FRAME_HEADER_SIZE,
    VideoStegoError,
    InsufficientCapacityError,
    CarrierExtractionError,
    UnsupportedVideoFormatError,
    CodecUnavailableError,
    bytes_to_bits,
    bits_to_bytes,
    pack_stego_frame,
    detect_available_lossless_codec,
    save_video_to_bytes,
    load_video_from_bytes,
    get_video_capacity,
    embed_in_video,
    extract_from_video,
)


def create_synthetic_video_bytes(
    num_frames: int = 4,
    width: int = 64,
    height: int = 64,
    fps: float = 25.0
) -> bytes:
    """Helper to generate a deterministic synthetic video in bytes."""
    codec, ext = detect_available_lossless_codec()
    # Generate reproducible deterministic color frames
    np.random.seed(42)
    frames = [
        np.random.randint(0, 256, (height, width, 3), dtype=np.uint8)
        for _ in range(num_frames)
    ]
    return save_video_to_bytes(frames, fps, width, height, fourcc_str=codec, ext=ext)


class TestVideoQualityMetrics:
    """Tests for calculate_video_metrics and frame pair validation."""

    def test_identical_video_metrics(self):
        frames = [np.zeros((32, 32, 3), dtype=np.uint8) for _ in range(3)]
        metrics = calculate_video_metrics(frames, frames)
        assert metrics["average_mse"] == 0.0
        assert metrics["average_psnr"] == float("inf")
        assert "Infinity" in metrics["psnr_display"]
        assert metrics["total_frames"] == 3
        assert metrics["modified_frames"] == 0

    def test_known_mathematical_mse_and_psnr(self):
        # 2 frames of 10x10 RGB = 200 pixels, 600 subpixels total
        c_frames = [np.zeros((10, 10, 3), dtype=np.uint8) for _ in range(2)]
        s_frames = [np.zeros((10, 10, 3), dtype=np.uint8) for _ in range(2)]

        # Modify first subpixel of frame 0 by +1
        s_frames[0][0, 0, 0] = 1

        # Frame 0 MSE: 1 / 300 = 0.0033333...
        # Frame 1 MSE: 0
        # Overall average MSE: (1 / 300 + 0) / 2 = 1 / 600
        metrics = calculate_video_metrics(c_frames, s_frames)
        expected_mse = 1.0 / 600.0
        assert math.isclose(metrics["average_mse"], expected_mse, rel_tol=1e-5)

        expected_psnr = 10.0 * math.log10((255.0 ** 2) / expected_mse)
        assert math.isclose(metrics["average_psnr"], expected_psnr, rel_tol=1e-3)
        assert metrics["total_frames"] == 2
        assert metrics["modified_frames"] == 1

    def test_frame_count_mismatch_raises_value_error(self):
        f1 = [np.zeros((10, 10, 3), dtype=np.uint8)]
        f2 = [np.zeros((10, 10, 3), dtype=np.uint8), np.zeros((10, 10, 3), dtype=np.uint8)]
        with pytest.raises(ValueError, match="frame counts must match"):
            validate_video_frame_pairs(f1, f2)

    def test_frame_dimension_mismatch_raises_value_error(self):
        f1 = [np.zeros((10, 10, 3), dtype=np.uint8)]
        f2 = [np.zeros((12, 10, 3), dtype=np.uint8)]
        with pytest.raises(ValueError, match="dimensions at index 0 must match"):
            validate_video_frame_pairs(f1, f2)

    def test_empty_frames_raises_value_error(self):
        with pytest.raises(ValueError, match="cannot be empty"):
            validate_video_frame_pairs([], [])


class TestVideoSteganographyCapacity:
    """Tests for get_video_capacity and framing constraints."""

    def test_capacity_calculation(self):
        vid_bytes = create_synthetic_video_bytes(num_frames=4, width=64, height=64, fps=20.0)
        cap = get_video_capacity(vid_bytes)

        assert cap["width"] == 64
        assert cap["height"] == 64
        assert cap["channels_per_frame"] == 3
        assert cap["num_frames"] == 4
        assert cap["fps"] == 20.0
        assert math.isclose(cap["duration_seconds"], 0.2, rel_tol=1e-2)

        total_bits = 4 * 64 * 64 * 3  # 49152 bits
        assert cap["total_carrier_bits"] == total_bits
        assert cap["total_carrier_bytes"] == total_bits // 8
        assert cap["header_overhead_bytes"] == 14
        assert cap["max_usable_payload_bytes"] == (total_bits - 112) // 8

    def test_codec_detection(self):
        codec, ext = detect_available_lossless_codec()
        assert codec in ["FFV1", "HFYU"]
        assert ext in [".avi", ".mkv"]


class TestVideoSteganographyRoundTrip:
    """Tests for embedding, extraction, and bit-level recovery."""

    def test_video_round_trip_with_encrypted_envelope(self):
        cover_vid = create_synthetic_video_bytes(num_frames=5, width=64, height=64, fps=25.0)

        # 1. Encrypt message using Phase 2 AES-256-GCM
        secret_msg = b"High-security classified video steganography payload test."
        key_bytes = generate_key()
        envelope_bytes = encrypt(secret_msg, key_bytes)

        # 2. Embed into video
        stego_vid, metrics, preview_png = embed_in_video(cover_vid, envelope_bytes)
        assert len(stego_vid) > 0
        assert metrics["embedded_bytes"] == len(envelope_bytes)
        assert metrics["modified_frames"] >= 1
        assert metrics["average_psnr"] > 50.0  # High visual fidelity
        assert len(preview_png) > 0

        # 3. Extract from video
        extracted_envelope = extract_from_video(stego_vid)
        assert extracted_envelope == envelope_bytes

        # 4. Decrypt extracted envelope
        recovered_msg = decrypt(extracted_envelope, key_bytes)
        assert recovered_msg == secret_msg

    def test_multi_frame_spanning_payload(self):
        # Create video with small frames (20x20) so payload spans multiple frames
        # Each frame has 20 * 20 * 3 = 1200 bits = 150 bytes
        cover_vid = create_synthetic_video_bytes(num_frames=6, width=20, height=20, fps=10.0)

        # Payload of 250 bytes will span:
        # Header (14 bytes) + 250 = 264 bytes = 2112 bits -> 2 frames
        payload = b"Z" * 250
        stego_vid, metrics, _ = embed_in_video(cover_vid, payload)
        assert metrics["modified_frames"] == 2
        assert metrics["total_frames"] == 6

        extracted = extract_from_video(stego_vid)
        assert extracted == payload

    def test_empty_payload_round_trip(self):
        cover_vid = create_synthetic_video_bytes(num_frames=3, width=32, height=32)
        payload = b""
        stego_vid, metrics, _ = embed_in_video(cover_vid, payload)
        assert metrics["embedded_bytes"] == 0
        assert metrics["modified_frames"] == 1  # 14 bytes header embedded

        extracted = extract_from_video(stego_vid)
        assert extracted == payload

    def test_video_metadata_preservation(self):
        cover_vid = create_synthetic_video_bytes(num_frames=4, width=48, height=36, fps=15.0)
        c_frames, c_meta = load_video_from_bytes(cover_vid)

        payload = b"Preserve container parameters"
        stego_vid, _, _ = embed_in_video(cover_vid, payload)
        s_frames, s_meta = load_video_from_bytes(stego_vid)

        assert len(c_frames) == len(s_frames) == 4
        assert c_meta["width"] == s_meta["width"] == 48
        assert c_meta["height"] == s_meta["height"] == 36
        assert c_meta["num_frames"] == s_meta["num_frames"] == 4
        assert math.isclose(c_meta["fps"], s_meta["fps"], rel_tol=1e-1)


class TestVideoSteganographyRejection:
    """Tests for bounds checking, corruption detection, and error handling."""

    def test_insufficient_capacity_rejected(self):
        # 2 frames of 16x16 = 2 * 16 * 16 * 3 = 1536 bits = 192 bytes
        # Max usable = (1536 - 112) // 8 = 178 bytes
        cover_vid = create_synthetic_video_bytes(num_frames=2, width=16, height=16)

        oversized_payload = b"X" * 200
        with pytest.raises(InsufficientCapacityError, match="exceeds video usable capacity"):
            embed_in_video(cover_vid, oversized_payload)

    def test_clean_cover_video_has_no_vstg_signature(self):
        cover_vid = create_synthetic_video_bytes(num_frames=3, width=32, height=32)
        with pytest.raises(CarrierExtractionError, match="Invalid video steganography signature"):
            extract_from_video(cover_vid)

    def test_corrupted_payload_crc32_rejected(self):
        cover_vid = create_synthetic_video_bytes(num_frames=4, width=40, height=40)
        payload = b"Integrity protected payload"
        stego_vid, _, _ = embed_in_video(cover_vid, payload)

        # Tamper with the stego video frames by flipping a pixel bit in the payload region
        s_frames, meta = load_video_from_bytes(stego_vid)
        # Flip LSB of a subpixel in frame 0 at index 120 (after the 14-byte / 112-bit header)
        flat = s_frames[0].reshape(-1)
        flat[120] ^= 1

        tampered_vid = save_video_to_bytes(
            s_frames,
            fps=meta["fps"],
            width=meta["width"],
            height=meta["height"],
            fourcc_str=meta["fourcc"] if meta["fourcc"] in ["FFV1", "HFYU"] else "FFV1"
        )

        with pytest.raises(CarrierExtractionError, match="CRC32 checksum mismatch"):
            extract_from_video(tampered_vid)

    def test_invalid_video_bytes_rejected(self):
        with pytest.raises(UnsupportedVideoFormatError):
            load_video_from_bytes(b"not a valid video stream content")
