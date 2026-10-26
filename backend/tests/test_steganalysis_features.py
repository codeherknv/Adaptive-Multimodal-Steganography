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
