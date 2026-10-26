"""Tests for unified multimodal orchestration engine (Phase 6)."""

import json
import zipfile
import pytest

from app.allocation.engine import (
    embed_multimodal,
    extract_multimodal,
    create_stego_zip_bundle,
    unpack_stego_zip_bundle,
    MultimodalEmbeddingResult,
    MultimodalExtractionResult,
    MultimodalEngineError,
    CarrierExtractionMismatchError,
)
from app.core.crypto_utils import generate_key, bytes_to_hex
from tests.test_profiler import (
    create_synthetic_png,
    create_synthetic_wav,
    create_synthetic_video,
)


@pytest.fixture
def synthetic_carriers():
    """Create fresh, reusable synthetic covers for testing."""
    img = create_synthetic_png(width=80, height=80, pattern="noise")
    aud = create_synthetic_wav(duration_sec=0.5, sample_rate=16000, channels=1)
    vid = create_synthetic_video(num_frames=12, width=64, height=64, moving=True)
    return img, aud, vid


class TestMultimodalEngineEndToEnd:
    def test_e2e_password_encryption_and_recovery(self, synthetic_carriers):
        img_cov, aud_cov, vid_cov = synthetic_carriers
        secret_msg = "Top-Secret Multimodal Cryptographic Payload 🔒🛰️"
        password = "CyberResearch2026!SecureKey"

        # 1. Embed using Adaptive strategy
        embed_res = embed_multimodal(
            message=secret_msg,
            image_bytes=img_cov,
            audio_bytes=aud_cov,
            video_bytes=vid_cov,
            password=password,
            strategy_name="adaptive",
        )

        assert isinstance(embed_res, MultimodalEmbeddingResult)
        assert embed_res.salt_bytes is not None
        assert len(embed_res.zip_bundle_bytes) > 0
        assert embed_res.allocation_plan.total_payload_bytes > 0
        assert sum(a.payload_bytes for a in embed_res.allocation_plan.allocations.values()) == embed_res.allocation_plan.total_payload_bytes

        # Manifest security check: no key or plaintext
        manifest_str = json.dumps(embed_res.manifest)
        assert secret_msg not in manifest_str
        assert password not in manifest_str
        assert embed_res.key_bytes.hex() not in manifest_str

        # 2. Extract using password and salt
        ext_res = extract_multimodal(
            stego_image_bytes=embed_res.stego_image_bytes,
            stego_audio_bytes=embed_res.stego_audio_bytes,
            stego_video_bytes=embed_res.stego_video_bytes,
            password=password,
            salt_bytes=embed_res.salt_bytes,
        )

        assert isinstance(ext_res, MultimodalExtractionResult)
        assert ext_res.verified is True
        assert ext_res.plaintext == secret_msg
        assert ext_res.message_id_hex == embed_res.message_id_hex
        assert ext_res.chunk_count == 3

    def test_e2e_direct_key_encryption_and_recovery(self, synthetic_carriers):
        img_cov, aud_cov, vid_cov = synthetic_carriers
        secret_msg = "Direct AES-256 Key Multimodal Test"
        raw_key = generate_key()

        # Embed using Fixed baseline strategy
        embed_res = embed_multimodal(
            message=secret_msg,
            image_bytes=img_cov,
            audio_bytes=aud_cov,
            video_bytes=vid_cov,
            key_bytes=raw_key,
            strategy_name="fixed",
        )

        # Extract using direct key
        ext_res = extract_multimodal(
            stego_image_bytes=embed_res.stego_image_bytes,
            stego_audio_bytes=embed_res.stego_audio_bytes,
            stego_video_bytes=embed_res.stego_video_bytes,
            key_bytes=raw_key,
        )

        assert ext_res.plaintext == secret_msg

    def test_zip_bundle_roundtrip(self, synthetic_carriers):
        img_cov, aud_cov, vid_cov = synthetic_carriers
        secret_msg = "ZIP Bundle Packaging Test Message"
        password = "ZipPassword123"

        embed_res = embed_multimodal(
            message=secret_msg,
            image_bytes=img_cov,
            audio_bytes=aud_cov,
            video_bytes=vid_cov,
            password=password,
        )

        # Unpack from zip bytes
        img_b, aud_b, vid_b, manifest = unpack_stego_zip_bundle(embed_res.zip_bundle_bytes)
        assert len(img_b) > 0
        assert len(aud_b) > 0
        assert len(vid_b) > 0
        assert manifest is not None
        assert manifest["message_id"] == embed_res.message_id_hex

        # Extract from unpacked carriers
        ext_res = extract_multimodal(
            stego_image_bytes=img_b,
            stego_audio_bytes=aud_b,
            stego_video_bytes=vid_b,
            password=password,
            salt_bytes=embed_res.salt_bytes,
            manifest_dict=manifest,
        )
        assert ext_res.plaintext == secret_msg
        assert ext_res.manifest == manifest


class TestMultimodalEngineFailureModes:
    def test_wrong_password_rejected(self, synthetic_carriers):
        img_cov, aud_cov, vid_cov = synthetic_carriers
        embed_res = embed_multimodal(
            message="Confidential Secret",
            image_bytes=img_cov,
            audio_bytes=aud_cov,
            video_bytes=vid_cov,
            password="CorrectPassword123",
        )

        with pytest.raises(MultimodalEngineError) as exc_info:
            extract_multimodal(
                stego_image_bytes=embed_res.stego_image_bytes,
                stego_audio_bytes=embed_res.stego_audio_bytes,
                stego_video_bytes=embed_res.stego_video_bytes,
                password="WrongPassword999",
                salt_bytes=embed_res.salt_bytes,
            )
        assert "authentication failed" in str(exc_info.value).lower()

    def test_corrupted_carrier_rejected(self, synthetic_carriers):
        img_cov, aud_cov, vid_cov = synthetic_carriers
        raw_key = generate_key()

        embed_res = embed_multimodal(
            message="Data Integrity Test",
            image_bytes=img_cov,
            audio_bytes=aud_cov,
            video_bytes=vid_cov,
            key_bytes=raw_key,
        )

        # Corrupt the image carrier with non-stego image
        corrupted_img = create_synthetic_png(width=80, height=80, pattern="flat")

        with pytest.raises(MultimodalEngineError):
            extract_multimodal(
                stego_image_bytes=corrupted_img,
                stego_audio_bytes=embed_res.stego_audio_bytes,
                stego_video_bytes=embed_res.stego_video_bytes,
                key_bytes=raw_key,
            )

    def test_incomplete_zip_bundle_rejected(self):
        # Create a ZIP missing video
        import io
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("stego_carrier.png", b"fake_png")
            zf.writestr("stego_carrier.wav", b"fake_wav")
        
        with pytest.raises(MultimodalEngineError) as exc_info:
            unpack_stego_zip_bundle(buf.getvalue())
        assert "Missing required carrier" in str(exc_info.value)
