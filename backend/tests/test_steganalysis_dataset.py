"""Tests for steganalysis dataset generation and leakage prevention metadata (Phase 7)."""

import pytest

from app.steganalysis.dataset_generator import (
    generate_modality_dataset,
    SteganalysisDataset,
    DatasetSample,
)


class TestSteganalysisDataset:
    def test_generate_image_dataset_structure_and_labels(self):
        # 6 independent sources -> Cover (label 0) + multiple Stego (label 1)
        ds = generate_modality_dataset("image", num_sources=6, payload_fractions=[0.10, 0.40])
        assert isinstance(ds, SteganalysisDataset)
        assert ds.modality == "image"
        assert len(ds.samples) > 6

        labels = set(s.label for s in ds.samples)
        assert labels == {0, 1}

        # Check source_id integrity: each source should have 1 cover and multiple stego samples
        source_ids = set(s.source_id for s in ds.samples)
        assert len(source_ids) == 6

        for src in source_ids:
            src_samples = [s for s in ds.samples if s.source_id == src]
            cover_samples = [s for s in src_samples if s.label == 0]
            stego_samples = [s for s in src_samples if s.label == 1]
            assert len(cover_samples) == 1
            assert len(stego_samples) >= 1

    def test_generate_audio_dataset_categories_and_strategies(self):
        ds = generate_modality_dataset("audio", num_sources=5, payload_fractions=[0.10, 0.50])
        assert ds.modality == "audio"

        stego_samples = [s for s in ds.samples if s.label == 1]
        categories = set(s.payload_category for s in stego_samples)
        strategies = set(s.allocation_strategy for s in stego_samples)

        assert "low" in categories or "high" in categories
        assert "fixed" in strategies or "adaptive" in strategies

    def test_dataset_contains_no_cryptographic_secrets(self):
        ds = generate_modality_dataset("image", num_sources=4)
        ds_dict = ds.to_dict()
        ds_str = str(ds_dict).lower()

        # Integrity check: plaintext and keys must never leak into dataset records
        assert "aes" not in ds_str
        assert "private_key" not in ds_str
        assert "password" not in ds_str

    def test_feature_matrix_and_groups_extraction(self):
        ds = generate_modality_dataset("video", num_sources=5, payload_fractions=[0.20])
        X, y, groups = ds.get_feature_matrix_and_labels()

        assert X.ndim == 2
        assert len(X) == len(y) == len(groups)
        assert X.shape[1] == len(ds.feature_names)
        assert set(y).issubset({0, 1})
