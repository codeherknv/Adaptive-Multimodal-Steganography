"""Automated test suite for PNG image steganography and quality metrics."""

import io
import math
import numpy as np
from PIL import Image
import pytest

from app.core.crypto_utils import generate_key, encrypt, decrypt
from app.evaluation.quality_metrics import (
    calculate_mse,
    calculate_psnr,
    calculate_ssim,
    evaluate_image_quality,
)
from app.media.image_stego import (
    FRAME_HEADER_SIZE,
    IMAGE_MAGIC,
    get_image_capacity,
    embed_in_image,
    extract_from_image,
    save_image_to_png_bytes,
    load_image_as_rgb_array,
    InsufficientCapacityError,
    CarrierExtractionError,
    UnsupportedImageFormatError,
)


def create_synthetic_png(width: int = 100, height: int = 100, mode: str = "RGB") -> bytes:
    """Generate in-memory synthetic PNG bytes with known pattern."""
    np.random.seed(42)
    channels = 3 if mode == "RGB" else 4
    arr = np.random.randint(20, 230, size=(height, width, channels), dtype=np.uint8)
    if mode == "RGBA":
        arr[:, :, 3] = 255  # fully opaque
    img = Image.fromarray(arr, mode=mode)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


class TestImageQualityMetrics:
    def test_identical_images_metrics(self):
        img = np.ones((50, 50, 3), dtype=np.uint8) * 128
        mse = calculate_mse(img, img)
        psnr = calculate_psnr(img, img)
        ssim = calculate_ssim(img, img)

        assert mse == 0.0
        assert math.isinf(psnr)
        assert ssim == 1.0

    def test_known_mathematical_mse_and_psnr(self):
        # 10x10 RGB image = 300 channel values
        img1 = np.zeros((10, 10, 3), dtype=np.uint8)
        img2 = np.zeros((10, 10, 3), dtype=np.uint8)

        # Alter exactly one channel value by 3 units: (3^2) / 300 = 9 / 300 = 0.03
        img2[0, 0, 0] = 3
        expected_mse = 9.0 / 300.0
        actual_mse = calculate_mse(img1, img2)
        assert pytest.approx(actual_mse, rel=1e-5) == expected_mse

        expected_psnr = 10.0 * math.log10((255.0 ** 2) / expected_mse)
        actual_psnr = calculate_psnr(img1, img2)
        assert pytest.approx(actual_psnr, rel=1e-5) == expected_psnr

    def test_shape_mismatch_raises_value_error(self):
        img1 = np.zeros((20, 20, 3), dtype=np.uint8)
        img2 = np.zeros((20, 30, 3), dtype=np.uint8)
        with pytest.raises(ValueError, match="Image dimensions must match"):
            calculate_mse(img1, img2)

    def test_evaluate_image_quality_dictionary(self):
        img1 = np.ones((20, 20, 3), dtype=np.uint8) * 100
        img2 = img1.copy()
        img2[0, 0, 0] = 101
        res = evaluate_image_quality(img1, img2)
        assert "mse" in res
        assert "psnr" in res
        assert "ssim" in res
        assert res["mse"] > 0
        assert res["ssim"] > 0.99


class TestImageSteganographyCapacity:
    def test_capacity_estimation_rgb(self):
        png_bytes = create_synthetic_png(width=80, height=60, mode="RGB")
        cap = get_image_capacity(png_bytes)

        assert cap["width"] == 80
        assert cap["height"] == 60
        assert cap["channels"] == 3
        assert cap["color_mode"] == "RGB"

        # 80 * 60 * 3 bits = 14,400 bits = 1800 bytes
        assert cap["total_carrier_bits"] == 14400
        assert cap["total_carrier_bytes"] == 1800
        assert cap["header_overhead_bytes"] == FRAME_HEADER_SIZE  # 14
        assert cap["max_usable_payload_bytes"] == 1800 - 14

    def test_capacity_estimation_rgba_preserves_alpha(self):
        png_bytes = create_synthetic_png(width=50, height=50, mode="RGBA")
        cap = get_image_capacity(png_bytes)

        # Uses 3 RGB channels, ignores alpha
        assert cap["embeddable_channels_per_pixel"] == 3
        assert cap["total_carrier_bits"] == 50 * 50 * 3


class TestImageSteganographyRoundTrip:
    def test_embed_and_extract_phase2_envelope_exact(self):
        cover_png = create_synthetic_png(width=100, height=100, mode="RGB")
        secret_key = generate_key()
        secret_plaintext = "Research message hidden inside lossless PNG carrier! 🚀"

        # Phase 2 AES-256-GCM encryption produces versioned binary envelope
        envelope = encrypt(secret_plaintext.encode("utf-8"), secret_key)
        assert len(envelope) >= 30

        # Embed envelope into PNG
        stego_array, metrics = embed_in_image(cover_png, envelope)
        assert metrics["psnr"] > 50.0  # High fidelity PSNR
        assert metrics["ssim"] > 0.999
        assert metrics["embedded_bytes"] == len(envelope)

        # Save to PNG and reload from binary
        stego_png_bytes = save_image_to_png_bytes(stego_array)

        # Extract envelope from stego PNG
        recovered_envelope = extract_from_image(stego_png_bytes)
        assert recovered_envelope == envelope  # Exact byte-for-byte match!

        # Authenticate and decrypt with Phase 2 crypto
        recovered_plaintext = decrypt(recovered_envelope, secret_key).decode("utf-8")
        assert recovered_plaintext == secret_plaintext

    def test_empty_payload_round_trip(self):
        cover_png = create_synthetic_png(width=40, height=40)
        empty_payload = b""

        stego_arr, _ = embed_in_image(cover_png, empty_payload)
        stego_bytes = save_image_to_png_bytes(stego_arr)
        recovered = extract_from_image(stego_bytes)
        assert recovered == b""

    def test_rgba_preserves_alpha_channel_integrity(self):
        rgba_png = create_synthetic_png(width=40, height=40, mode="RGBA")
        cover_arr, _ = load_image_as_rgb_array(rgba_png)
        original_alpha = cover_arr[:, :, 3].copy()

        payload = b"Testing alpha channel non-interference."
        stego_arr, _ = embed_in_image(rgba_png, payload)

        # Ensure alpha channel is bit-for-bit identical
        assert np.array_equal(stego_arr[:, :, 3], original_alpha)

        recovered = extract_from_image(stego_arr)
        assert recovered == payload


class TestImageSteganographyRejection:
    def test_insufficient_capacity_rejected(self):
        # 10x10 RGB image = 300 bits = 37 bytes total. Overhead = 14 bytes -> max 23 bytes.
        small_png = create_synthetic_png(width=10, height=10)
        large_payload = b"A" * 50  # 50 bytes > 23 bytes

        with pytest.raises(InsufficientCapacityError, match="exceeds carrier capacity"):
            embed_in_image(small_png, large_payload)

    def test_clean_cover_image_has_no_signature(self):
        clean_png = create_synthetic_png(width=50, height=50)
        with pytest.raises(CarrierExtractionError, match="Invalid steganography signature"):
            extract_from_image(clean_png)

    def test_corrupted_payload_crc32_rejected(self):
        cover_png = create_synthetic_png(width=60, height=60)
        payload = b"Tamper detection verification."

        stego_arr, _ = embed_in_image(cover_png, payload)

        # Corrupt pixel channels in payload area (offset after 14-byte header = 112 bits)
        # Pixel at (y=0, x=50, ch=0) has bit index 50 * 3 = 150 (within payload range [112, 351])
        stego_arr[0, 50, 0] ^= 0x01

        with pytest.raises(CarrierExtractionError, match="Payload CRC32 checksum mismatch"):
            extract_from_image(stego_arr)

    def test_invalid_image_bytes_rejected(self):
        with pytest.raises(UnsupportedImageFormatError):
            load_image_as_rgb_array(b"NOT_A_VALID_IMAGE_FILE")

        with pytest.raises(UnsupportedImageFormatError):
            get_image_capacity(b"NOT_AN_IMAGE")
