"""Tests for steganalysis feature extraction across image, audio, and video (Phase 7)."""

import numpy as np
import pytest

from app.steganalysis.features import (
    extract_image_features,
    extract_audio_features,
    extract_video_features,
    FeatureExtractionError,
    IMAGE_FEATURE_NAMES,
    AUDIO_FEATURE_NAMES,
    VIDEO_FEATURE_NAMES,
)
from tests.test_profiler import (
    create_synthetic_png,
    create_synthetic_wav,
    create_synthetic_video,
)


class TestSteganalysisFeatures:
    def test_extract_image_features_shape_and_names(self):
        png_bytes = create_synthetic_png(width=64, height=64, pattern="noise")
        feats, names = extract_image_features(png_bytes)

        assert isinstance(feats, np.ndarray)
        assert feats.shape == (10,)
        assert names == IMAGE_FEATURE_NAMES
        assert not np.isnan(feats).any()
        assert not np.isinf(feats).any()

        # LSB 1-ratio must be in [0.0, 1.0]
        lsb_ratio = feats[names.index("img_lsb_one_ratio")]
        assert 0.0 <= lsb_ratio <= 1.0

    def test_extract_image_features_corrupted_file_raises(self):
        with pytest.raises(FeatureExtractionError):
            extract_image_features(b"corrupted_image_header_not_png")

    def test_extract_audio_features_shape_and_names(self):
        wav_bytes = create_synthetic_wav(duration_sec=0.25, sample_rate=16000, channels=1)
        feats, names = extract_audio_features(wav_bytes)

        assert isinstance(feats, np.ndarray)
        assert feats.shape == (8,)
        assert names == AUDIO_FEATURE_NAMES
        assert not np.isnan(feats).any()
        assert not np.isinf(feats).any()

        # RMS and LSB ratio valid ranges
        lsb_ratio = feats[names.index("aud_lsb_one_ratio")]
        assert 0.0 <= lsb_ratio <= 1.0

    def test_extract_audio_features_corrupted_file_raises(self):
        with pytest.raises(FeatureExtractionError):
            extract_audio_features(b"RIFF\x00\x00\x00\x00WAVEfmt corrupt")

    def test_extract_video_features_shape_and_names(self):
        vid_bytes = create_synthetic_video(num_frames=6, width=48, height=48, moving=True)
        feats, names = extract_video_features(vid_bytes)

        assert isinstance(feats, np.ndarray)
        assert feats.shape == (7,)
        assert names == VIDEO_FEATURE_NAMES
        assert not np.isnan(feats).any()
        assert not np.isinf(feats).any()

    def test_extract_video_features_corrupted_file_raises(self):
        with pytest.raises(FeatureExtractionError):
            extract_video_features(b"corrupt_video_data_stream")

    def test_image_lsb_transition_no_unsigned_underflow(self):
        """Regression test: verify transitions in both directions (0->1 and 1->0) do not underflow."""
        # Create an 8x8 RGB image with alternating LSB pattern [0, 1, 0, 1, 0, 1, 0, 1] across rows
        row_even = np.array([100, 101, 100, 101, 100, 101, 100, 101], dtype=np.uint8)
        img_arr = np.zeros((8, 8, 3), dtype=np.uint8)
        for r in range(8):
            img_arr[r, :, 0] = row_even
            img_arr[r, :, 1] = row_even
            img_arr[r, :, 2] = row_even

        feats, names = extract_image_features(img_arr)
        trans_rate = feats[names.index("img_lsb_transition_rate")]
        # Every adjacent horizontal pixel transitions between 0 and 1.
        # Underflow bug produced ~63.0; correct rate must be exactly 1.0.
        assert 0.0 <= trans_rate <= 1.0
        assert np.isclose(trans_rate, 1.0)

    def test_image_rgb_channel_pov_preservation(self):
        """Verify PoV calculation preserves discrete RGB color channel histogram asymmetry."""
        # Create image where Red channel has exclusively even numbers (LSB = 0)
        # and Green channel has exclusively odd numbers (LSB = 1)
        img_arr = np.zeros((16, 16, 3), dtype=np.uint8)
        img_arr[:, :, 0] = 100  # Even (PoV asymmetry in Red is 1.0)
        img_arr[:, :, 1] = 101  # Odd (PoV asymmetry in Green is 1.0)
        img_arr[:, :, 2] = 50   # Even (PoV asymmetry in Blue is 1.0)

        feats, names = extract_image_features(img_arr)
        pov_asym = feats[names.index("img_pov_asymmetry")]
        assert pov_asym > 0.9  # Pure even/odd channel must exhibit near 1.0 PoV asymmetry

    def test_audio_format_appropriate_pov_and_transitions(self):
        """Verify audio PoV and transition rates for both 16-bit and 8-bit PCM formats."""
        from app.media.audio_stego import save_wav_audio

        # 1. 16-bit PCM test with alternating LSB pattern [0, 1, 0, 1]
        samples_16 = np.array([1000, 1001, 1000, 1001] * 64, dtype=np.int16)
        wav_16 = save_wav_audio(samples_16, {"num_channels": 1, "sample_width": 2, "sample_rate": 8000})
        feats_16, names_16 = extract_audio_features(wav_16)

        trans_rate_16 = feats_16[names_16.index("aud_lsb_transition_rate")]
        assert 0.0 <= trans_rate_16 <= 1.0
        assert np.isclose(trans_rate_16, 1.0)

        # 2. 8-bit PCM test
        samples_8 = np.array([120, 121, 120, 121] * 64, dtype=np.uint8)
        wav_8 = save_wav_audio(samples_8, {"num_channels": 1, "sample_width": 1, "sample_rate": 8000})
        feats_8, names_8 = extract_audio_features(wav_8)

        trans_rate_8 = feats_8[names_8.index("aud_lsb_transition_rate")]
        assert 0.0 <= trans_rate_8 <= 1.0
        assert np.isclose(trans_rate_8, 1.0)
        assert not np.isnan(feats_8[names_8.index("aud_pov_asymmetry")])

    def test_video_interframe_lsb_flips_both_directions(self):
        """Verify video inter-frame LSB flip rates do not underflow when transitioning 1->0."""
        from app.media.video_stego import save_video_to_bytes, detect_available_lossless_codec
        codec_str, ext = detect_available_lossless_codec()

        # Frame 0 has all even pixels (LSB=0)
        # Frame 1 has all odd pixels (LSB=1) -> 0 to 1 transition
        # Frame 2 has all even pixels (LSB=0) -> 1 to 0 transition
        f0 = np.full((16, 16, 3), 100, dtype=np.uint8)
        f1 = np.full((16, 16, 3), 101, dtype=np.uint8)
        f2 = np.full((16, 16, 3), 100, dtype=np.uint8)

        vid_bytes = save_video_to_bytes([f0, f1, f2], fps=10.0, width=16, height=16, fourcc_str=codec_str, ext=ext)
        feats, names = extract_video_features(vid_bytes)

        flip_rate = feats[names.index("vid_interframe_lsb_flip_rate")]
        # Flips occur at 100% of pixels in both directions
        assert 0.0 <= flip_rate <= 1.0
        assert np.isclose(flip_rate, 1.0)
