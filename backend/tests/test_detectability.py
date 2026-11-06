"""Unit tests for independent detectability metrics (Phase 10)."""

import io
import numpy as np
from PIL import Image
import wave
import pytest

from app.metrics.detectability import (
    compute_carrier_embedding_rates,
    analyze_image_chi_square,
    analyze_audio_sample_pairs,
    analyze_video_per_frame_chi_square,
)
from app.media.video_stego import save_video_to_bytes


def test_carrier_embedding_rates():
    rates = compute_carrier_embedding_rates(
        b_I=500,
        b_A=1000,
        b_V=2000,
        image_shape=(100, 100, 3),
        audio_samples=16000,
        video_shape=(20, 64, 64, 3),
    )
    # img_bpp = (500 * 8) / (100 * 100) = 4000 / 10000 = 0.4
    assert rates["image_bpp"] == 0.4
    # img_bpc = 4000 / 30000 = 0.1333
    assert abs(rates["image_bpc"] - 0.1333) < 1e-3
    # aud_bps = (1000 * 8) / 16000 = 8000 / 16000 = 0.5
    assert rates["audio_bps"] == 0.5
    # vid_bppf = (2000 * 8) / (20 * 64 * 64) = 16000 / 81920 ≈ 0.1953
    assert abs(rates["video_bppf"] - 0.1953) < 1e-3


def test_image_chi_square_on_clean_image():
    # Clean natural image with diverse pixel histogram
    rng = np.random.default_rng(42)
    # Generate smooth gradient with random natural noise
    x = np.linspace(20, 220, 128, dtype=np.uint8)
    arr = np.tile(x, (128, 1))
    arr = np.stack([arr, arr, arr], axis=-1)
    img = Image.fromarray(arr, mode="RGB")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    png_bytes = buf.getvalue()

    res = analyze_image_chi_square(png_bytes)
    assert "chi2_stat" in res
    assert "p_value" in res
    assert "stego_prob" in res
    assert 0.0 <= res["stego_prob"] <= 1.0


def test_audio_sample_pairs():
    # Synthetic clean sine audio
    sample_rate = 16000
    t = np.linspace(0, 0.5, int(0.5 * sample_rate), endpoint=False)
    samples = (0.5 * np.sin(2 * np.pi * 440.0 * t) * 32000).astype(np.int16)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(samples.tobytes())
    wav_bytes = buf.getvalue()

    res = analyze_audio_sample_pairs(wav_bytes)
    assert "lsb_one_ratio" in res
    assert "sample_pair_diff_var" in res
    assert "audio_chi2_p_val" in res
    assert 0.0 <= res["lsb_one_ratio"] <= 1.0


def test_video_per_frame_chi_square():
    frames = [np.random.randint(50, 200, (64, 64, 3), dtype=np.uint8) for _ in range(5)]
    vid_bytes = save_video_to_bytes(frames, 25.0, 64, 64, 'FFV1', '.avi')

    res = analyze_video_per_frame_chi_square(vid_bytes)
    assert "video_mean_chi2_stat" in res
    assert "video_mean_p_val" in res
    assert "video_stego_prob" in res
    assert 0.0 <= res["video_stego_prob"] <= 1.0
