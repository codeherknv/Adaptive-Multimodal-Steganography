"""Tests for carrier profiling and feature extraction (Phase 6)."""

import io
import math
import struct
import wave
import cv2
import numpy as np
import pytest
from PIL import Image

from app.allocation.profiler import (
    ImageProfile,
    AudioProfile,
    VideoProfile,
    MultimodalTriadProfile,
    profile_image_carrier,
    profile_audio_carrier,
    profile_video_carrier,
    profile_multimodal_triad,
    InvalidCarrierError,
)
from app.media.video_stego import save_video_to_bytes, detect_available_lossless_codec


def create_synthetic_png(width: int = 64, height: int = 64, pattern: str = "noise") -> bytes:
    """Create in-memory lossless PNG bytes with a controllable spatial pattern."""
    if pattern == "noise":
        arr = np.random.randint(0, 256, (height, width, 3), dtype=np.uint8)
    elif pattern == "flat":
        arr = np.full((height, width, 3), 128, dtype=np.uint8)
    else:  # gradient
        grad = np.linspace(0, 255, width, dtype=np.uint8)
        arr = np.tile(grad, (height, 1))
        arr = np.stack([arr, arr, arr], axis=-1)

    img = Image.fromarray(arr, mode="RGB")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def create_synthetic_wav(
    duration_sec: float = 0.5,
    sample_rate: int = 16000,
    channels: int = 1,
    sample_width: int = 2,
    freq: float = 440.0
) -> bytes:
    """Create in-memory PCM WAV bytes with a controllable waveform."""
    total_samples = int(duration_sec * sample_rate)
    t = np.linspace(0, duration_sec, total_samples, endpoint=False)
    # Sine wave in [-1.0, 1.0]
    waveform = np.sin(2 * np.pi * freq * t)

    if sample_width == 2:
        samples = (waveform * 32000.0).astype(np.int16)
        raw_bytes = samples.tobytes()
    else:
        samples = ((waveform + 1.0) * 127.5).astype(np.uint8)
        raw_bytes = samples.tobytes()

    if channels == 2:
        # Interleave stereo
        stereo = np.empty((total_samples * 2,), dtype=samples.dtype)
        stereo[0::2] = samples
        stereo[1::2] = samples
        raw_bytes = stereo.tobytes()

    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(sample_width)
        wf.setframerate(sample_rate)
        wf.writeframes(raw_bytes)
    return buf.getvalue()


def create_synthetic_video(
    num_frames: int = 10,
    width: int = 64,
    height: int = 64,
    fps: float = 25.0,
    moving: bool = True
) -> bytes:
    """Create in-memory lossless AVI video bytes."""
    codec_str, ext = detect_available_lossless_codec()
    frames = []
    for i in range(num_frames):
        if moving:
            # Shift bright square across frames
            f = np.zeros((height, width, 3), dtype=np.uint8)
            x_pos = (i * 4) % (width - 16)
            f[10:30, x_pos:x_pos+16] = 255
        else:
            f = np.full((height, width, 3), 100, dtype=np.uint8)
        frames.append(f)

    return save_video_to_bytes(frames, fps, width, height, codec_str, ext)


class TestCarrierProfiling:
    def test_profile_image_texture_vs_flat(self):
        noisy_png = create_synthetic_png(64, 64, pattern="noise")
        flat_png = create_synthetic_png(64, 64, pattern="flat")

        noisy_profile = profile_image_carrier(noisy_png)
        flat_profile = profile_image_carrier(flat_png)

        assert isinstance(noisy_profile, ImageProfile)
        assert noisy_profile.width == 64
        assert noisy_profile.height == 64
        assert noisy_profile.max_usable_payload_bytes == (64 * 64 * 3 // 8) - 14

        # Noisy texture has significantly higher Laplacian variance than flat surface
        assert noisy_profile.laplacian_variance > flat_profile.laplacian_variance
        assert noisy_profile.complexity_score > flat_profile.complexity_score
        assert flat_profile.edge_density == 0.0

    def test_profile_invalid_image_rejected(self):
        with pytest.raises(InvalidCarrierError):
            profile_image_carrier(b"not_an_image_file_data_corrupted")

    def test_profile_audio_features(self):
        wav_bytes = create_synthetic_wav(duration_sec=0.25, sample_rate=16000, channels=1)
        profile = profile_audio_carrier(wav_bytes)

        assert isinstance(profile, AudioProfile)
        assert profile.sample_rate == 16000
        assert profile.bits_per_sample == 16
        assert profile.num_channels == 1
        assert profile.channel_layout == "Mono"
        assert profile.duration_seconds == 0.25
        assert profile.total_samples == 4000
        assert profile.max_usable_payload_bytes == (4000 // 8) - 14
        assert profile.rms_energy > 0.0
        assert profile.sample_diff_variance > 0.0
        assert 0.05 <= profile.complexity_score <= 1.0

    def test_profile_invalid_audio_rejected(self):
        with pytest.raises(InvalidCarrierError):
            profile_audio_carrier(b"RIFF\x00\x00\x00\x00corrupt_wav")

    def test_profile_video_motion_vs_static(self):
        moving_vid = create_synthetic_video(num_frames=8, width=64, height=64, moving=True)
        static_vid = create_synthetic_video(num_frames=8, width=64, height=64, moving=False)

        moving_profile = profile_video_carrier(moving_vid)
        static_profile = profile_video_carrier(static_vid)

        assert isinstance(moving_profile, VideoProfile)
        assert moving_profile.width == 64
        assert moving_profile.height == 64
        assert moving_profile.num_frames == 8
        assert moving_profile.frame_diff_variance > static_profile.frame_diff_variance
        assert moving_profile.complexity_score >= static_profile.complexity_score

    def test_profile_invalid_video_rejected(self):
        with pytest.raises(InvalidCarrierError):
            profile_video_carrier(b"not_a_valid_avi_video_stream")

    def test_profile_multimodal_triad_consolidation(self):
        img_bytes = create_synthetic_png(64, 64)
        aud_bytes = create_synthetic_wav(duration_sec=0.2, sample_rate=8000)
        vid_bytes = create_synthetic_video(num_frames=6, width=48, height=48)

        triad = profile_multimodal_triad(img_bytes, aud_bytes, vid_bytes)
        assert isinstance(triad, MultimodalTriadProfile)
        assert triad.total_usable_capacity_bytes > 0
        assert sum(triad.capacity_shares.values()) == pytest.approx(1.0, abs=1e-3)
        assert triad.capacity_shares["image"] > 0
        assert triad.capacity_shares["audio"] > 0
        assert triad.capacity_shares["video"] > 0
