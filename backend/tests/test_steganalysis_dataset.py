"""Tests for steganalysis dataset generation and leakage prevention metadata (Phase 7)."""

import pytest

from app.steganalysis.dataset_generator import (
    generate_modality_dataset,
    generate_multimodal_allocation_comparison_dataset,
    SteganalysisDataset,
    DatasetSample,
)


class TestSteganalysisDataset:
    def test_generate_image_dataset_exact_1_to_1_balance(self):
        """Verify that dataset generation produces exact 1:1 balance between cover and stego."""
        num_sources = 6
        ds = generate_modality_dataset("image", num_sources=num_sources, payload_fractions=[0.15, 0.40])
        assert isinstance(ds, SteganalysisDataset)
        assert ds.modality == "image"
        # Exact 1:1 balance: 1 cover + 1 stego per source
        assert len(ds.samples) == 2 * num_sources

        cover_count = sum(1 for s in ds.samples if s.label == 0)
        stego_count = sum(1 for s in ds.samples if s.label == 1)
        assert cover_count == stego_count == num_sources

        # Check source_id integrity: each source should have exactly 1 cover and 1 stego
        source_ids = set(s.source_id for s in ds.samples)
        assert len(source_ids) == num_sources

        for src in source_ids:
            src_samples = [s for s in ds.samples if s.source_id == src]
            assert len(src_samples) == 2
            cover_samples = [s for s in src_samples if s.label == 0]
            stego_samples = [s for s in src_samples if s.label == 1]
            assert len(cover_samples) == 1
            assert len(stego_samples) == 1

    def test_generate_audio_dataset_categories_and_strategies(self):
        ds = generate_modality_dataset("audio", num_sources=6, payload_fractions=[0.15, 0.50])
        assert ds.modality == "audio"
        assert len(ds.samples) == 12

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
        ds = generate_modality_dataset("video", num_sources=4, payload_fractions=[0.20])
        X, y, groups = ds.get_feature_matrix_and_labels()

        assert X.ndim == 2
        assert len(X) == len(y) == len(groups)
        assert X.shape[1] == len(ds.feature_names)
        assert set(y) == {0, 1}
        # Equal distribution in y
        assert (y == 0).sum() == (y == 1).sum()

    def test_multimodal_allocation_comparison_pipeline(self):
        """Verify that genuine Fixed and Adaptive allocation is executed across triads."""
        comp = generate_multimodal_allocation_comparison_dataset(num_triads=3, message_length=60)
        assert comp["num_triads_evaluated"] > 0
        for triad in comp["triads"]:
            assert "fixed_allocation" in triad
            assert "adaptive_allocation" in triad
            # Allocation plans must allocate bytes
            fixed_total = sum(triad["fixed_allocation"].values())
            adaptive_total = sum(triad["adaptive_allocation"].values())
            assert fixed_total == triad["message_length"]
            assert adaptive_total == triad["message_length"]
