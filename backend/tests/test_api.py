"""Automated tests for health, status, crypto, and image steganography API endpoints."""

import base64
import io
import numpy as np
from PIL import Image
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.config import settings
from app.core.crypto_utils import generate_key, bytes_to_base64, bytes_to_hex


@pytest.fixture
def client():
    return TestClient(app)


def make_test_png_bytes(width: int = 80, height: int = 80, mode: str = "RGB") -> bytes:
    """Helper to generate in-memory PNG bytes for API tests."""
    channels = 3 if mode == "RGB" else 4
    arr = np.ones((height, width, channels), dtype=np.uint8) * 120
    img = Image.fromarray(arr, mode=mode)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_root_endpoint(client):
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["project"] == settings.PROJECT_NAME
    assert data["version"] == settings.VERSION
    assert "health_url" in data


def test_health_endpoint(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["version"] == settings.VERSION
    assert "timestamp" in data
    assert "C:" not in str(data)
    assert "secret" not in str(data).lower()


def test_system_status_endpoint_phase_8(client):
    response = client.get("/api/status")
    assert response.status_code == 200
    data = response.json()
    assert data["current_phase"] == 8
    assert "modules" in data
    
    # Phase 1 through 8 modules are implemented
    assert data["modules"]["infrastructure"]["status"] == "implemented"
    assert data["modules"]["cryptography"]["status"] == "implemented"
    assert data["modules"]["payload_codec"]["status"] == "implemented"
    assert data["modules"]["image_stego"]["status"] == "implemented"
    assert len(data["modules"]["image_stego"]["capabilities"]) > 0
    assert data["modules"]["audio_stego"]["status"] == "implemented"
    assert len(data["modules"]["audio_stego"]["capabilities"]) > 0
    assert data["modules"]["video_stego"]["status"] == "implemented"
    assert len(data["modules"]["video_stego"]["capabilities"]) > 0
    assert data["modules"]["allocation"]["status"] == "implemented"
    assert len(data["modules"]["allocation"]["capabilities"]) > 0
    assert data["modules"]["steganalysis"]["status"] == "implemented"
    assert len(data["modules"]["steganalysis"]["capabilities"]) > 0
    assert data["modules"]["evaluation_lab"]["status"] == "implemented"
    assert len(data["modules"]["evaluation_lab"]["capabilities"]) > 0


class TestCryptoAPIEndpoints:
    def test_encrypt_and_decrypt_auto_key_roundtrip(self, client):
        msg = "Secret academic payload across carriers 🚀"
        enc_res = client.post(
            "/api/crypto/encrypt",
            json={"plaintext": msg, "encoding": "base64"}
        )
        assert enc_res.status_code == 200
        enc_data = enc_res.json()
        assert "key" in enc_data
        assert "envelope" in enc_data
        assert enc_data["envelope_version"] == 1
        assert enc_data["plaintext_bytes_length"] == len(msg.encode("utf-8"))
        assert "Educational Key Workflow" in enc_data["warning"]

        # Now decrypt using the returned key
        dec_res = client.post(
            "/api/crypto/decrypt",
            json={
                "envelope": enc_data["envelope"],
                "key": enc_data["key"],
                "encoding": "base64"
            }
        )
        assert dec_res.status_code == 200
        dec_data = dec_res.json()
        assert dec_data["plaintext"] == msg
        assert dec_data["authenticated"] is True
        assert dec_data["envelope_version"] == 1

    def test_encrypt_and_decrypt_user_key(self, client):
        raw_key = generate_key()
        b64_key = bytes_to_base64(raw_key)
        msg = "Target carrier allocation: Image=33%, Audio=33%, Video=34%"

        enc_res = client.post(
            "/api/crypto/encrypt",
            json={
                "plaintext": msg,
                "key": b64_key,
                "encoding": "base64"
            }
        )
        assert enc_res.status_code == 200
        enc_data = enc_res.json()
        assert enc_data["key"] == b64_key

        dec_res = client.post(
            "/api/crypto/decrypt",
            json={
                "envelope": enc_data["envelope"],
                "key": b64_key,
                "encoding": "base64"
            }
        )
        assert dec_res.status_code == 200
        assert dec_res.json()["plaintext"] == msg

    def test_encrypt_and_decrypt_hex_encoding(self, client):
        msg = "Hex-encoded payload round-trip check"
        enc_res = client.post(
            "/api/crypto/encrypt",
            json={"plaintext": msg, "encoding": "hex"}
        )
        assert enc_res.status_code == 200
        enc_data = enc_res.json()
        assert enc_data["key_encoding"] == "hex"

        dec_res = client.post(
            "/api/crypto/decrypt",
            json={
                "envelope": enc_data["envelope"],
                "key": enc_data["key"],
                "encoding": "hex"
            }
        )
        assert dec_res.status_code == 200
        assert dec_res.json()["plaintext"] == msg

    def test_encrypt_and_decrypt_password_derivation(self, client):
        password = "MasterPassword2026!#"
        msg = "Key derived via PBKDF2-HMAC-SHA256"

        enc_res = client.post(
            "/api/crypto/encrypt",
            json={
                "plaintext": msg,
                "password": password,
                "encoding": "base64"
            }
        )
        assert enc_res.status_code == 200
        enc_data = enc_res.json()
        assert enc_data["salt"] is not None

        # Decrypt using password and returned salt
        dec_res = client.post(
            "/api/crypto/decrypt",
            json={
                "envelope": enc_data["envelope"],
                "password": password,
                "salt": enc_data["salt"],
                "encoding": "base64"
            }
        )
        assert dec_res.status_code == 200
        assert dec_res.json()["plaintext"] == msg

    def test_decrypt_with_wrong_key_rejected(self, client):
        enc_res = client.post(
            "/api/crypto/encrypt",
            json={"plaintext": "Confidential message"}
        )
        envelope = enc_res.json()["envelope"]

        wrong_key = bytes_to_base64(generate_key())
        dec_res = client.post(
            "/api/crypto/decrypt",
            json={"envelope": envelope, "key": wrong_key}
        )
        assert dec_res.status_code == 400
        assert "Authentication tag verification failed" in dec_res.json()["detail"]

    def test_decrypt_tampered_envelope_rejected(self, client):
        enc_res = client.post(
            "/api/crypto/encrypt",
            json={"plaintext": "Data integrity test"}
        )
        enc_data = enc_res.json()
        key = enc_data["key"]

        tampered_envelope = enc_data["envelope"][:-4] + "AAAA"

        dec_res = client.post(
            "/api/crypto/decrypt",
            json={"envelope": tampered_envelope, "key": key}
        )
        assert dec_res.status_code == 400

    def test_validation_rejects_key_and_password_simultaneously(self, client):
        res = client.post(
            "/api/crypto/encrypt",
            json={
                "plaintext": "Test",
                "key": bytes_to_base64(generate_key()),
                "password": "Password123"
            }
        )
        assert res.status_code == 422

    def test_validation_rejects_empty_decrypt_credentials(self, client):
        res = client.post(
            "/api/crypto/decrypt",
            json={"envelope": "dGVzdA=="}
        )
        assert res.status_code == 422


class TestImageStegoAPIEndpoints:
    def test_image_capacity_endpoint(self, client):
        png_bytes = make_test_png_bytes(width=100, height=80)
        res = client.post(
            "/api/image/capacity",
            files={"image": ("test_cover.png", png_bytes, "image/png")}
        )
        assert res.status_code == 200
        data = res.json()
        assert data["width"] == 100
        assert data["height"] == 80
        assert data["channels"] == 3
        assert data["total_carrier_bits"] == 100 * 80 * 3
        assert data["max_usable_payload_bytes"] == (100 * 80 * 3 // 8) - 14

    def test_image_embed_and_extract_end_to_end_pipeline(self, client):
        original_secret = "End-to-End Image Steganography Verification with AES-256-GCM!"

        # 1. Encrypt message via crypto endpoint
        enc_res = client.post(
            "/api/crypto/encrypt",
            json={"plaintext": original_secret, "encoding": "base64"}
        )
        assert enc_res.status_code == 200
        enc_data = enc_res.json()
        envelope_b64 = enc_data["envelope"]
        secret_key_b64 = enc_data["key"]

        # 2. Embed into PNG carrier
        cover_png = make_test_png_bytes(width=120, height=120)
        embed_res = client.post(
            "/api/image/embed",
            files={"image": ("cover.png", cover_png, "image/png")},
            data={"envelope": envelope_b64, "encoding": "base64"}
        )
        assert embed_res.status_code == 200
        embed_data = embed_res.json()
        assert "stego_image_data_url" in embed_data
        assert embed_data["stego_image_data_url"].startswith("data:image/png;base64,")
        assert embed_data["metrics"]["psnr"] > 50.0
        assert embed_data["metrics"]["ssim"] > 0.999

        # 3. Decode stego image data URL back to binary PNG bytes
        data_url = embed_data["stego_image_data_url"]
        b64_content = data_url.split(",", 1)[1]
        stego_png_bytes = base64.b64decode(b64_content)

        # 4. Extract envelope from stego PNG
        extract_res = client.post(
            "/api/image/extract",
            files={"image": ("stego.png", stego_png_bytes, "image/png")},
            data={"encoding": "base64"}
        )
        assert extract_res.status_code == 200
        extract_data = extract_res.json()
        extracted_envelope = extract_data["envelope"]
        assert extracted_envelope == envelope_b64  # Exact match!

        # 5. Decrypt extracted envelope via crypto endpoint
        dec_res = client.post(
            "/api/crypto/decrypt",
            json={
                "envelope": extracted_envelope,
                "key": secret_key_b64,
                "encoding": "base64"
            }
        )
        assert dec_res.status_code == 200
        dec_data = dec_res.json()
        assert dec_data["plaintext"] == original_secret
        assert dec_data["authenticated"] is True

    def test_image_embed_insufficient_capacity_returns_400(self, client):
        # 10x10 PNG: total carrier is 37 bytes, overhead is 14 bytes -> capacity 23 bytes
        tiny_png = make_test_png_bytes(width=10, height=10)
        # Encrypt text that generates an envelope larger than 23 bytes
        enc_res = client.post("/api/crypto/encrypt", json={"plaintext": "A" * 50})
        envelope_b64 = enc_res.json()["envelope"]

        embed_res = client.post(
            "/api/image/embed",
            files={"image": ("tiny.png", tiny_png, "image/png")},
            data={"envelope": envelope_b64, "encoding": "base64"}
        )
        assert embed_res.status_code == 400
        assert "exceeds carrier capacity" in embed_res.json()["detail"]

    def test_image_extract_non_stego_image_returns_400(self, client):
        clean_png = make_test_png_bytes(width=50, height=50)
        res = client.post(
            "/api/image/extract",
            files={"image": ("clean.png", clean_png, "image/png")},
            data={"encoding": "base64"}
        )
        assert res.status_code == 400
        assert "Extraction failed" in res.json()["detail"]

    def test_image_invalid_file_returns_400(self, client):
        res = client.post(
            "/api/image/capacity",
            files={"image": ("bad.png", b"NOT_A_PNG_FILE_DATA", "image/png")}
        )
        assert res.status_code == 400


# ---------------------------------------------------------
# Audio Steganography API Endpoint Tests (Phase 4)
# ---------------------------------------------------------

def make_test_wav_bytes(channels: int = 1, sample_rate: int = 44100, duration: float = 0.5) -> bytes:
    """Helper to generate in-memory PCM WAV bytes for API tests."""
    import wave
    num_frames = int(sample_rate * duration)
    t = np.linspace(0, duration, num_frames, endpoint=False)
    samples = (np.sin(2 * np.pi * 440 * t) * 16000).astype(np.int16)
    if channels == 2:
        interleaved = np.empty((num_frames * 2,), dtype=np.int16)
        interleaved[0::2] = samples
        interleaved[1::2] = samples
        raw = interleaved.tobytes()
    else:
        raw = samples.tobytes()
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(raw)
    return buf.getvalue()


class TestAudioStegoAPIEndpoints:
    """Integration test suite for audio steganography REST API endpoints."""

    def test_audio_capacity_endpoint(self, client):
        wav_bytes = make_test_wav_bytes(channels=2, sample_rate=44100, duration=1.0)
        res = client.post(
            "/api/audio/capacity",
            files={"audio": ("test.wav", wav_bytes, "audio/wav")}
        )
        assert res.status_code == 200
        data = res.json()
        assert data["num_channels"] == 2
        assert data["channel_layout"] == "Stereo"
        assert data["sample_rate"] == 44100
        assert data["bits_per_sample"] == 16
        assert data["total_samples"] == 88200
        assert data["total_carrier_bits"] == 88200
        assert data["total_carrier_bytes"] == 88200 // 8
        assert data["header_overhead_bytes"] == 14
        assert data["max_usable_payload_bytes"] == (88200 // 8) - 14

    def test_audio_embed_and_extract_end_to_end_pipeline(self, client):
        original_secret = "Confidential audio research secret 🎵"
        enc_res = client.post("/api/crypto/encrypt", json={"plaintext": original_secret, "encoding": "base64"})
        assert enc_res.status_code == 200
        enc_data = enc_res.json()
        envelope_b64 = enc_data["envelope"]
        secret_key_b64 = enc_data["key"]

        # 1. Check Capacity of a 1.0s stereo WAV
        cover_wav = make_test_wav_bytes(channels=2, sample_rate=44100, duration=1.0)
        cap_res = client.post(
            "/api/audio/capacity",
            files={"audio": ("carrier.wav", cover_wav, "audio/wav")}
        )
        assert cap_res.status_code == 200
        assert cap_res.json()["max_usable_payload_bytes"] > enc_data["envelope_bytes_length"]

        # 2. Embed envelope into WAV
        embed_res = client.post(
            "/api/audio/embed",
            files={"audio": ("carrier.wav", cover_wav, "audio/wav")},
            data={"envelope": envelope_b64, "encoding": "base64"}
        )
        assert embed_res.status_code == 200
        embed_data = embed_res.json()
        assert "data:audio/wav;base64," in embed_data["stego_audio_data_url"]
        assert embed_data["metrics"]["snr"] > 50.0  # High fidelity

        # 3. Decode data URL to WAV bytes
        data_url = embed_data["stego_audio_data_url"]
        b64_content = data_url.split(",", 1)[1]
        stego_wav_bytes = base64.b64decode(b64_content)

        # 4. Extract envelope from stego WAV
        extract_res = client.post(
            "/api/audio/extract",
            files={"audio": ("stego.wav", stego_wav_bytes, "audio/wav")},
            data={"encoding": "base64"}
        )
        assert extract_res.status_code == 200
        extract_data = extract_res.json()
        assert extract_data["envelope"] == envelope_b64

        # 5. Decrypt envelope
        dec_res = client.post(
            "/api/crypto/decrypt",
            json={"envelope": extract_data["envelope"], "key": secret_key_b64, "encoding": "base64"}
        )
        assert dec_res.status_code == 200
        assert dec_res.json()["plaintext"] == original_secret
        assert dec_res.json()["authenticated"] is True

    def test_audio_embed_insufficient_capacity_returns_400(self, client):
        # 0.05s mono WAV at 1000 Hz = 50 samples (< 112 bits for header)
        short_wav = make_test_wav_bytes(channels=1, sample_rate=1000, duration=0.05)
        enc_res = client.post("/api/crypto/encrypt", json={"plaintext": "A" * 30})
        envelope_b64 = enc_res.json()["envelope"]

        embed_res = client.post(
            "/api/audio/embed",
            files={"audio": ("short.wav", short_wav, "audio/wav")},
            data={"envelope": envelope_b64, "encoding": "base64"}
        )
        assert embed_res.status_code == 400
        assert "exceeds audio carrier capacity" in embed_res.json()["detail"]

    def test_audio_extract_non_stego_audio_returns_400(self, client):
        clean_wav = make_test_wav_bytes(channels=1, sample_rate=44100, duration=0.5)
        res = client.post(
            "/api/audio/extract",
            files={"audio": ("clean.wav", clean_wav, "audio/wav")},
            data={"encoding": "base64"}
        )
        assert res.status_code == 400
        assert "Extraction failed" in res.json()["detail"]

    def test_audio_invalid_file_returns_400(self, client):
        res = client.post(
            "/api/audio/capacity",
            files={"audio": ("bad.wav", b"NOT_A_VALID_WAV_FILE_HEADER", "audio/wav")}
        )
        assert res.status_code == 400


def make_test_video_bytes(num_frames: int = 4, width: int = 40, height: int = 40, fps: float = 25.0) -> bytes:
    """Helper to generate in-memory lossless AVI video bytes for API tests."""
    from app.media.video_stego import save_video_to_bytes, detect_available_lossless_codec
    codec, ext = detect_available_lossless_codec()
    frames = [
        np.ones((height, width, 3), dtype=np.uint8) * (80 + i * 10)
        for i in range(num_frames)
    ]
    return save_video_to_bytes(frames, fps, width, height, fourcc_str=codec, ext=ext)


class TestVideoStegoAPIEndpoints:
    """Integration test suite for video steganography REST API endpoints."""

    def test_video_capacity_endpoint(self, client):
        vid_bytes = make_test_video_bytes(num_frames=4, width=64, height=48, fps=20.0)
        res = client.post(
            "/api/video/capacity",
            files={"video": ("test_video.avi", vid_bytes, "video/x-msvideo")}
        )
        assert res.status_code == 200
        data = res.json()
        assert data["width"] == 64
        assert data["height"] == 48
        assert data["channels_per_frame"] == 3
        assert data["num_frames"] == 4
        assert data["fps"] == 20.0
        assert data["total_carrier_bits"] == 4 * 64 * 48 * 3
        assert data["header_overhead_bytes"] == 14
        assert data["max_usable_payload_bytes"] == (4 * 64 * 48 * 3 - 112) // 8

    def test_video_embed_and_extract_end_to_end_pipeline(self, client):
        original_secret = "Top Secret Video Steganography Payload 🎬"
        enc_res = client.post("/api/crypto/encrypt", json={"plaintext": original_secret, "encoding": "base64"})
        assert enc_res.status_code == 200
        enc_data = enc_res.json()
        envelope_b64 = enc_data["envelope"]
        secret_key_b64 = enc_data["key"]

        # 1. Check capacity
        cover_vid = make_test_video_bytes(num_frames=5, width=64, height=64)
        cap_res = client.post(
            "/api/video/capacity",
            files={"video": ("cover.avi", cover_vid, "video/x-msvideo")}
        )
        assert cap_res.status_code == 200
        assert cap_res.json()["max_usable_payload_bytes"] > enc_data["envelope_bytes_length"]

        # 2. Embed envelope into video
        embed_res = client.post(
            "/api/video/embed",
            files={"video": ("cover.avi", cover_vid, "video/x-msvideo")},
            data={"envelope": envelope_b64, "encoding": "base64"}
        )
        assert embed_res.status_code == 200
        embed_data = embed_res.json()
        assert "data:video/avi;base64," in embed_data["stego_video_data_url"]
        assert "data:image/png;base64," in embed_data["preview_frame_data_url"]
        assert embed_data["metrics"]["average_psnr"] > 50.0  # High visual fidelity
        assert embed_data["embedded_bytes"] == enc_data["envelope_bytes_length"]

        # 3. Decode data URL to video bytes
        b64_content = embed_data["stego_video_data_url"].split(",", 1)[1]
        stego_vid_bytes = base64.b64decode(b64_content)

        # 4. Extract envelope from stego video
        extract_res = client.post(
            "/api/video/extract",
            files={"video": ("stego.avi", stego_vid_bytes, "video/x-msvideo")},
            data={"encoding": "base64"}
        )
        assert extract_res.status_code == 200
        extract_data = extract_res.json()
        assert extract_data["envelope"] == envelope_b64
        assert extract_data["status"] == "verified"

        # 5. Decrypt envelope
        dec_res = client.post(
            "/api/crypto/decrypt",
            json={"envelope": extract_data["envelope"], "key": secret_key_b64, "encoding": "base64"}
        )
        assert dec_res.status_code == 200
        assert dec_res.json()["plaintext"] == original_secret
        assert dec_res.json()["authenticated"] is True

    def test_video_embed_insufficient_capacity_returns_400(self, client):
        # 1 tiny frame of 8x8 = 8 * 8 * 3 = 192 bits = 24 bytes
        # Max usable = (192 - 112) // 8 = 10 bytes
        short_vid = make_test_video_bytes(num_frames=1, width=8, height=8)
        enc_res = client.post("/api/crypto/encrypt", json={"plaintext": "A" * 50})
        envelope_b64 = enc_res.json()["envelope"]

        embed_res = client.post(
            "/api/video/embed",
            files={"video": ("short.avi", short_vid, "video/x-msvideo")},
            data={"envelope": envelope_b64, "encoding": "base64"}
        )
        assert embed_res.status_code == 400
        assert "exceeds video usable capacity" in embed_res.json()["detail"]

    def test_video_extract_non_stego_video_returns_400(self, client):
        clean_vid = make_test_video_bytes(num_frames=3, width=32, height=32)
        res = client.post(
            "/api/video/extract",
            files={"video": ("clean.avi", clean_vid, "video/x-msvideo")},
            data={"encoding": "base64"}
        )
        assert res.status_code == 400
        assert "Extraction failed" in res.json()["detail"]

    def test_video_invalid_file_returns_400(self, client):
        res = client.post(
            "/api/video/capacity",
            files={"video": ("bad.avi", b"NOT_A_VALID_VIDEO_CONTAINER_OR_CODEC", "video/x-msvideo")}
        )
        assert res.status_code == 400


class TestMultimodalAPIEndpoints:
    @pytest.fixture
    def triad_files(self):
        img_bytes = make_test_png_bytes(width=64, height=64)
        aud_bytes = make_test_wav_bytes(duration=0.25, sample_rate=16000)
        vid_bytes = make_test_video_bytes(num_frames=6, width=48, height=48)
        return img_bytes, aud_bytes, vid_bytes

    def test_multimodal_analyze_endpoint(self, client, triad_files):
        img_b, aud_b, vid_b = triad_files
        res = client.post(
            "/api/multimodal/analyze",
            files={
                "image": ("cover.png", img_b, "image/png"),
                "audio": ("cover.wav", aud_b, "audio/wav"),
                "video": ("cover.avi", vid_b, "video/x-msvideo"),
            },
            data={"payload_length": "200", "strategy": "adaptive"}
        )
        assert res.status_code == 200
        data = res.json()
        assert "image" in data
        assert "audio" in data
        assert "video" in data
        assert data["total_usable_capacity_bytes"] > 0
        assert data["simulated_allocation"] is not None
        assert data["simulated_allocation"]["total_payload_bytes"] == 200

    def test_multimodal_embed_and_extract_with_zip_bundle(self, client, triad_files):
        img_b, aud_b, vid_b = triad_files
        secret = "Multimodal Triad API Integration Secret 🔐"
        password = "ResearchPassword2026!"

        # 1. Embed via API
        embed_res = client.post(
            "/api/multimodal/embed",
            files={
                "image": ("cover.png", img_b, "image/png"),
                "audio": ("cover.wav", aud_b, "audio/wav"),
                "video": ("cover.avi", vid_b, "video/x-msvideo"),
            },
            data={
                "message": secret,
                "strategy": "adaptive",
                "password": password,
                "encoding": "base64",
            }
        )
        assert embed_res.status_code == 200
        embed_data = embed_res.json()
        assert "zip_bundle_data_url" in embed_data
        assert "salt" in embed_data
        salt_b64 = embed_data["salt"]
        zip_data_url = embed_data["zip_bundle_data_url"]

        # Decode ZIP bytes from data URL
        header, b64_payload = zip_data_url.split(",", 1)
        import base64
        zip_bytes = base64.b64decode(b64_payload)

        # 2. Extract using uploaded ZIP bundle
        extract_res = client.post(
            "/api/multimodal/extract",
            files={"bundle_zip": ("bundle.zip", zip_bytes, "application/zip")},
            data={
                "password": password,
                "salt": salt_b64,
                "encoding": "base64",
            }
        )
        assert extract_res.status_code == 200
        ext_data = extract_res.json()
        assert ext_data["plaintext"] == secret
        assert ext_data["verified"] is True
        assert ext_data["chunk_count"] == 3

    def test_multimodal_embed_capacity_exceeded_returns_400(self, client):
        tiny_img = make_test_png_bytes(width=16, height=16)
        tiny_aud = make_test_wav_bytes(duration=0.05, sample_rate=8000)
        tiny_vid = make_test_video_bytes(num_frames=1, width=16, height=16)

        huge_message = "A" * 50_000
        res = client.post(
            "/api/multimodal/embed",
            files={
                "image": ("t_img.png", tiny_img, "image/png"),
                "audio": ("t_aud.wav", tiny_aud, "audio/wav"),
                "video": ("t_vid.avi", tiny_vid, "video/x-msvideo"),
            },
            data={"message": huge_message, "strategy": "adaptive"}
        )
        assert res.status_code == 400
        assert "exceeds combined net multimodal capacity" in res.json()["detail"]

    def test_multimodal_extract_wrong_password_returns_400(self, client, triad_files):
        img_b, aud_b, vid_b = triad_files
        embed_res = client.post(
            "/api/multimodal/embed",
            files={
                "image": ("c.png", img_b, "image/png"),
                "audio": ("c.wav", aud_b, "audio/wav"),
                "video": ("c.avi", vid_b, "video/x-msvideo"),
            },
            data={"message": "Test Secret", "password": "CorrectPassword1"}
        )
        embed_data = embed_res.json()
        salt_b64 = embed_data["salt"]
        import base64
        zip_bytes = base64.b64decode(embed_data["zip_bundle_data_url"].split(",", 1)[1])

        bad_res = client.post(
            "/api/multimodal/extract",
            files={"bundle_zip": ("bundle.zip", zip_bytes, "application/zip")},
            data={"password": "IncorrectPassword999", "salt": salt_b64}
        )
        assert bad_res.status_code == 400
        assert "authentication failed" in bad_res.json()["detail"].lower()


class TestSteganalysisAPIEndpoints:
    def test_steganalysis_dataset_generate_endpoint(self, client):
        res = client.post(
            "/api/steganalysis/dataset/generate",
            json={"modality": "image", "model_type": "random_forest", "num_sources": 6}
        )
        assert res.status_code == 200
        data = res.json()
        assert len(data) >= 1
        assert data[0]["modality"] == "image"
        assert data[0]["total_samples"] > 6
        assert len(data[0]["feature_names"]) == 10

    def test_steganalysis_dataset_summary_endpoint(self, client):
        res = client.get("/api/steganalysis/dataset/summary")
        assert res.status_code == 200
        data = res.json()
        assert len(data) >= 1

    def test_steganalysis_train_endpoint(self, client):
        res = client.post(
            "/api/steganalysis/train",
            json={"modality": "image", "model_type": "random_forest", "num_sources": 8}
        )
        assert res.status_code == 200
        data = res.json()
        assert len(data) >= 1
        first = data[0]
        assert first["modality"] == "image"
        assert first["model_type"] == "random_forest"
        assert "test_metrics" in first
        assert "accuracy" in first["test_metrics"]
        assert 0.0 <= first["test_metrics"]["accuracy"] <= 1.0

    def test_steganalysis_models_list_endpoint(self, client):
        res = client.get("/api/steganalysis/models")
        assert res.status_code == 200
        assert isinstance(res.json(), list)

    def test_steganalysis_classify_endpoint(self, client):
        img_bytes = make_test_png_bytes(width=64, height=64)
        res = client.post(
            "/api/steganalysis/classify",
            files={"file": ("test_carrier.png", img_bytes, "image/png")},
            data={"model_type": "random_forest"}
        )
        assert res.status_code == 200
        data = res.json()
        assert data["modality"] == "image"
        assert data["predicted_class"] in ("Cover", "Stego")
        assert 0.0 <= data["stego_probability"] <= 1.0
        assert "Notice" in data["disclaimer"]
        assert len(data["feature_values"]) > 0


class TestComparativeEvaluationAPIEndpoints:
    """Test suite for Phase 8 comparative evaluation API endpoints."""

    def test_get_comparative_results_endpoint(self, client):
        res = client.get("/api/evaluation/comparative-results")
        assert res.status_code == 200
        data = res.json()
        assert "metadata" in data
        assert "summary" in data
        assert "trials" in data
        assert "total_paired_trials" in data["summary"]
        assert "metrics_summary" in data["summary"]

    def test_run_comparative_evaluation_endpoint(self, client):
        res = client.post(
            "/api/evaluation/run",
            json={"num_sources": 2, "use_real_media": False}
        )
        assert res.status_code == 200
        data = res.json()
        assert data["summary"]["total_sources_evaluated"] == 2
        assert data["summary"]["total_paired_trials"] == 6  # 2 sources * 3 brackets
        assert data["summary"]["fixed_recovery_rate"] == 1.0
        assert data["summary"]["adaptive_recovery_rate"] == 1.0



