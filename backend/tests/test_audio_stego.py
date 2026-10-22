"""Unit tests for WAV Audio Steganography and Audio Quality Metrics (Phase 4).

Tests:
1. Audio distortion metrics: MSE, SNR (including identical audio with infinite SNR).
2. Audio capacity estimation for mono and stereo, 16-bit and 8-bit PCM.
3. Audio parameter preservation: sample rate, channels, bit depth, duration.
4. LSB embedding and extraction round trips for Phase 2 envelopes across mono/stereo audio.
5. Rejection of oversized payloads (insufficient capacity).
6. Rejection of clean non-stego audio (missing WSTG magic signature).
7. Rejection of corrupted stego audio (CRC32 checksum mismatch).
8. Rejection of unsupported or invalid audio inputs (non-WAV, unsupported sample widths).
"""

import io
import math
import struct
import wave
import numpy as np
import pytest

from app.core.crypto_utils import encrypt, generate_key
from app.evaluation.quality_metrics import (
    calculate_audio_mse,
    calculate_audio_snr,
    evaluate_audio_quality,
    validate_audio_pair,
)
from app.media.audio_stego import (
    AUDIO_MAGIC,
    AUDIO_FORMAT_VERSION,
    FRAME_HEADER_SIZE,
    get_audio_capacity,
    embed_in_audio,
    extract_from_audio,
    load_wav_audio,
    save_wav_audio,
    pack_stego_frame,
    bytes_to_bits,
    bits_to_bytes,
    AudioStegoError,
    InsufficientCapacityError,
    CarrierExtractionError,
    UnsupportedAudioFormatError,
)


def make_synthetic_wav(
    channels: int = 1,
    sample_rate: int = 44100,
    duration_seconds: float = 0.5,
    sample_width: int = 2,
    freq: float = 440.0
) -> bytes:
    """Helper to synthesize valid in-memory PCM WAV audio files for testing."""
    num_frames = int(sample_rate * duration_seconds)
    t = np.linspace(0, duration_seconds, num_frames, endpoint=False)

    if sample_width == 2:
        # 16-bit signed PCM
        amplitude = 16000.0
        if channels == 1:
            raw_data = (np.sin(2 * np.pi * freq * t) * amplitude).astype(np.int16).tobytes()
        elif channels == 2:
            left = (np.sin(2 * np.pi * freq * t) * amplitude).astype(np.int16)
            right = (np.cos(2 * np.pi * freq * t) * amplitude).astype(np.int16)
            interleaved = np.empty((num_frames * 2,), dtype=np.int16)
            interleaved[0::2] = left
            interleaved[1::2] = right
            raw_data = interleaved.tobytes()
        else:
            raise ValueError(f"Unsupported channel count {channels}")
    elif sample_width == 1:
        # 8-bit unsigned PCM (128 is center/silence)
        if channels == 1:
            raw_data = (128 + np.sin(2 * np.pi * freq * t) * 60).astype(np.uint8).tobytes()
        elif channels == 2:
            left = (128 + np.sin(2 * np.pi * freq * t) * 60).astype(np.uint8)
            right = (128 + np.cos(2 * np.pi * freq * t) * 60).astype(np.uint8)
            interleaved = np.empty((num_frames * 2,), dtype=np.uint8)
            interleaved[0::2] = left
            interleaved[1::2] = right
            raw_data = interleaved.tobytes()
        else:
            raise ValueError(f"Unsupported channel count {channels}")
    else:
        raise ValueError(f"Unsupported sample width {sample_width}")

    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(sample_width)
        wf.setframerate(sample_rate)
        wf.writeframes(raw_data)
    return buf.getvalue()


# =========================================================
# 1. Audio Quality Metrics Tests
# =========================================================

class TestAudioQualityMetrics:
    """Test suite for MSE and SNR audio distortion metric functions."""

    def test_identical_audio_metrics(self):
        """Identical audio samples must have MSE == 0.0 and SNR == inf."""
        samples = np.array([1000, -2000, 3000, -4000], dtype=np.int16)
        mse = calculate_audio_mse(samples, samples, sampwidth=2)
        snr = calculate_audio_snr(samples, samples)
        assert mse == 0.0
        assert math.isinf(snr)
        assert snr > 0

    def test_known_mathematical_mse_and_snr(self):
        """Verify MSE and SNR against hand-calculated values."""
        # 16-bit audio: cover = [1000, 1000], stego = [1001, 999]
        # Diff = [1, -1], diff^2 = [1, 1], mean diff^2 = 1.0
        # Normalized: 1 / 32768.0 -> diff^2 = (1 / 32768)^2 ≈ 9.313e-10
        cover = np.array([1000, 1000], dtype=np.int16)
        stego = np.array([1001, 999], dtype=np.int16)

        mse = calculate_audio_mse(cover, stego, sampwidth=2)
        expected_mse = 1.0 / (32768.0 ** 2)
        assert pytest.approx(mse, rel=1e-5) == expected_mse

        # Signal power = (1000^2 + 1000^2) / 2 = 1,000,000
        # Noise power = (1^2 + (-1)^2) / 2 = 1.0
        # SNR = 10 * log10(1,000,000 / 1.0) = 10 * 6 = 60.0 dB
        snr = calculate_audio_snr(cover, stego)
        assert pytest.approx(snr, rel=1e-5) == 60.0

    def test_silent_cover_audio_snr(self):
        """When cover audio is completely silent, SNR returns -inf if noise exists."""
        cover = np.zeros(100, dtype=np.int16)
        stego = np.ones(100, dtype=np.int16)
        snr = calculate_audio_snr(cover, stego)
        assert math.isinf(snr)
        assert snr < 0  # -inf

    def test_shape_mismatch_raises_value_error(self):
        """Audio arrays of differing lengths must raise ValueError."""
        a = np.zeros(100, dtype=np.int16)
        b = np.zeros(200, dtype=np.int16)
        with pytest.raises(ValueError, match="Audio sample dimensions must match"):
            validate_audio_pair(a, b)

    def test_empty_audio_raises_value_error(self):
        """Empty audio sample arrays must raise ValueError."""
        empty = np.array([], dtype=np.int16)
        with pytest.raises(ValueError, match="Audio sample arrays cannot be empty"):
            validate_audio_pair(empty, empty)

    def test_non_numpy_raises_type_error(self):
        """Non-numpy inputs must raise TypeError."""
        with pytest.raises(TypeError, match="must be numpy ndarrays"):
            validate_audio_pair([1, 2, 3], [1, 2, 3])

    def test_evaluate_audio_quality_dictionary(self):
        """evaluate_audio_quality returns expected dict structure and types."""
        cover = np.array([5000, -5000], dtype=np.int16)
        stego = np.array([5001, -4999], dtype=np.int16)
        res = evaluate_audio_quality(cover, stego, sampwidth=2)
        assert "mse" in res
        assert "snr" in res
        assert "snr_display" in res
        assert "dB" in res["snr_display"]


# =========================================================
# 2. Audio Capacity Estimation Tests
# =========================================================

class TestAudioSteganographyCapacity:
    """Test suite for WAV audio carrier capacity calculation."""

    def test_mono_capacity_calculation(self):
        """Mono audio: 1 sample per frame -> capacity = (num_frames // 8) - 14 bytes."""
        wav_bytes = make_synthetic_wav(channels=1, sample_rate=44100, duration_seconds=1.0)
        cap = get_audio_capacity(wav_bytes)

        assert cap["num_channels"] == 1
        assert cap["channel_layout"] == "Mono"
        assert cap["sample_rate"] == 44100
        assert cap["sample_width"] == 2
        assert cap["bits_per_sample"] == 16
        assert cap["num_frames"] == 44100
        assert cap["total_samples"] == 44100
        assert cap["total_carrier_bits"] == 44100
        assert cap["total_carrier_bytes"] == 44100 // 8  # 5512 bytes
        assert cap["header_overhead_bytes"] == FRAME_HEADER_SIZE  # 14 bytes
        assert cap["max_usable_payload_bytes"] == (44100 // 8) - 14  # 5498 bytes

    def test_stereo_capacity_calculation(self):
        """Stereo audio: 2 samples per frame -> capacity = (num_frames * 2 // 8) - 14 bytes."""
        wav_bytes = make_synthetic_wav(channels=2, sample_rate=44100, duration_seconds=1.0)
        cap = get_audio_capacity(wav_bytes)

        assert cap["num_channels"] == 2
        assert cap["channel_layout"] == "Stereo"
        assert cap["num_frames"] == 44100
        assert cap["total_samples"] == 44100 * 2  # 88200 samples
        assert cap["total_carrier_bytes"] == 88200 // 8  # 11025 bytes
        assert cap["max_usable_payload_bytes"] == (88200 // 8) - 14  # 11011 bytes

    def test_short_audio_zero_capacity(self):
        """Very short audio (< 112 samples) must report 0 usable payload bytes."""
        # 50 frames mono = 50 samples < 112 bits required for 14-byte header
        wav_bytes = make_synthetic_wav(channels=1, sample_rate=1000, duration_seconds=0.05)
        cap = get_audio_capacity(wav_bytes)
        assert cap["max_usable_payload_bytes"] == 0


# =========================================================
# 3. Audio Steganography Round-Trip Tests
# =========================================================

class TestAudioSteganographyRoundTrip:
    """Test suite for full embedding and extraction round trips."""

    def test_mono_16bit_round_trip_with_encrypted_envelope(self):
        """Encrypt message with Phase 2 AES-GCM, embed into mono WAV, reload, extract, and decrypt."""
        wav_bytes = make_synthetic_wav(channels=1, sample_rate=44100, duration_seconds=0.5)

        # 1. Create realistic Phase 2 encrypted envelope
        key = generate_key()
        secret_plaintext = b"Audio Steganography Secret Research Payload 2026."
        envelope = encrypt(secret_plaintext, key)

        # 2. Embed into mono WAV
        stego_wav_bytes, metrics = embed_in_audio(wav_bytes, envelope)
        assert len(stego_wav_bytes) > 0
        assert metrics["embedded_bytes"] == len(envelope)
        assert metrics["framed_bytes"] == len(envelope) + FRAME_HEADER_SIZE
        assert metrics["snr"] > 50.0  # High physical fidelity

        # 3. Extract from stego WAV
        extracted_envelope = extract_from_audio(stego_wav_bytes)

        # 4. Verify exact byte identity
        assert extracted_envelope == envelope

    def test_stereo_16bit_round_trip(self):
        """Stereo audio: interleaved L/R samples must embed and recover exact payload."""
        wav_bytes = make_synthetic_wav(channels=2, sample_rate=48000, duration_seconds=0.5)

        payload = b"Stereo interleaved audio steganography payload verification!"
        stego_wav_bytes, metrics = embed_in_audio(wav_bytes, payload)

        extracted = extract_from_audio(stego_wav_bytes)
        assert extracted == payload
        assert metrics["capacity_used_ratio"] < 0.1

    def test_8bit_pcm_audio_round_trip(self):
        """8-bit unsigned PCM WAV files must embed and recover exact payload."""
        wav_bytes = make_synthetic_wav(channels=1, sample_rate=22050, duration_seconds=0.5, sample_width=1)

        payload = b"8-bit PCM audio payload."
        stego_wav_bytes, metrics = embed_in_audio(wav_bytes, payload)

        extracted = extract_from_audio(stego_wav_bytes)
        assert extracted == payload

    def test_empty_payload_round_trip(self):
        """Embedding an empty payload (b'') must succeed and recover b''."""
        wav_bytes = make_synthetic_wav(channels=1, sample_rate=44100, duration_seconds=0.1)

        stego_wav_bytes, metrics = embed_in_audio(wav_bytes, b"")
        extracted = extract_from_audio(stego_wav_bytes)
        assert extracted == b""
        assert metrics["embedded_bytes"] == 0
        assert metrics["framed_bytes"] == FRAME_HEADER_SIZE

    def test_audio_metadata_preservation(self):
        """Verify that sample rate, channel count, sample width, and frame count are untouched."""
        cover_wav_bytes = make_synthetic_wav(channels=2, sample_rate=44100, duration_seconds=0.25, sample_width=2)
        payload = b"Metadata preservation check."

        stego_wav_bytes, _ = embed_in_audio(cover_wav_bytes, payload)

        # Inspect cover parameters
        with wave.open(io.BytesIO(cover_wav_bytes), "rb") as wf_cover:
            c_channels = wf_cover.getnchannels()
            c_width = wf_cover.getsampwidth()
            c_rate = wf_cover.getframerate()
            c_frames = wf_cover.getnframes()

        # Inspect stego parameters
        with wave.open(io.BytesIO(stego_wav_bytes), "rb") as wf_stego:
            s_channels = wf_stego.getnchannels()
            s_width = wf_stego.getsampwidth()
            s_rate = wf_stego.getframerate()
            s_frames = wf_stego.getnframes()

        assert c_channels == s_channels == 2
        assert c_width == s_width == 2
        assert c_rate == s_rate == 44100
        assert c_frames == s_frames


# =========================================================
# 4. Audio Steganography Rejection & Error Handling Tests
# =========================================================

class TestAudioSteganographyRejection:
    """Test suite for negative scenarios, error handling, and safe rejection."""

    def test_insufficient_capacity_rejected(self):
        """Payload exceeding audio capacity must raise InsufficientCapacityError."""
        # 100 frames mono = 100 samples < 112 bits for header alone
        short_wav = make_synthetic_wav(channels=1, sample_rate=1000, duration_seconds=0.1)
        payload = b"This payload is much too large for 100 samples!"

        with pytest.raises(InsufficientCapacityError, match="exceeds audio carrier capacity"):
            embed_in_audio(short_wav, payload)

    def test_clean_cover_audio_has_no_wstg_signature(self):
        """Attempting to extract from an unmodified audio file must raise CarrierExtractionError."""
        clean_wav = make_synthetic_wav(channels=1, sample_rate=44100, duration_seconds=0.5)

        with pytest.raises(CarrierExtractionError, match="Invalid audio steganography signature"):
            extract_from_audio(clean_wav)

    def test_corrupted_payload_crc32_rejected(self):
        """Flipping a bit in the audio sample payload region must trigger CRC32 mismatch."""
        wav_bytes = make_synthetic_wav(channels=1, sample_rate=44100, duration_seconds=0.5)
        payload = b"A confidential secret payload destined to be corrupted in transit."

        stego_wav_bytes, _ = embed_in_audio(wav_bytes, payload)

        # Load samples, corrupt a bit in the payload region (after 112 header bits)
        stego_samples, params = load_wav_audio(stego_wav_bytes)
        stego_samples[150] ^= 1  # Flip LSB of sample 150
        corrupted_wav_bytes = save_wav_audio(stego_samples, params)

        with pytest.raises(CarrierExtractionError, match="Payload CRC32 checksum mismatch"):
            extract_from_audio(corrupted_wav_bytes)

    def test_invalid_audio_bytes_rejected(self):
        """Random junk bytes must raise UnsupportedAudioFormatError."""
        junk = b"NOT_A_WAV_FILE_GARBAGE_BYTES_1234567890"

        with pytest.raises(UnsupportedAudioFormatError):
            load_wav_audio(junk)

        with pytest.raises(UnsupportedAudioFormatError):
            extract_from_audio(junk)

        with pytest.raises(UnsupportedAudioFormatError):
            embed_in_audio(junk, b"payload")

    def test_unsupported_sample_width_rejected(self):
        """Simulate an unsupported 24-bit PCM WAV (sampwidth=3) and ensure clean rejection."""
        # Synthesize a dummy WAV header with sampwidth=3
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(3)  # 24-bit PCM
            wf.setframerate(44100)
            wf.writeframes(b"\x00\x00\x00" * 100)

        raw_24bit_wav = buf.getvalue()

        with pytest.raises(UnsupportedAudioFormatError, match="only 16-bit and 8-bit PCM WAV are supported"):
            load_wav_audio(raw_24bit_wav)
