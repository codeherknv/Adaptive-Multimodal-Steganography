"""Tests for zero-leakage steganalysis training and evaluation (Phase 7)."""

import os
import tempfile
import numpy as np
import pytest

from app.steganalysis.dataset_generator import generate_modality_dataset
from app.steganalysis.trainer import (
    train_steganalyzer,
    load_steganalyzer,
    TrainedSteganalyzer,
    EvaluationMetrics,
)
from app.steganalysis.classifier import classify_media_file
from tests.test_profiler import create_synthetic_png


class TestSteganalysisTraining:
    @pytest.fixture
    def image_dataset(self):
        # 8 sources to allow clean GroupShuffleSplit
        return generate_modality_dataset("image", num_sources=8, payload_fractions=[0.10, 0.40])

    def test_zero_leakage_group_split(self, image_dataset):
        with tempfile.TemporaryDirectory() as tmp_dir:
            analyzer = train_steganalyzer(
                dataset=image_dataset,
                model_type="random_forest",
                test_size=0.25,
                random_state=42,
                models_dir=tmp_dir,
            )

            assert isinstance(analyzer, TrainedSteganalyzer)
            assert len(analyzer.train_sources) > 0
            assert len(analyzer.test_sources) > 0

            # CRITICAL LEAKAGE INVARIANT: Train sources and test sources must have ZERO intersection
            intersection = set(analyzer.train_sources).intersection(set(analyzer.test_sources))
            assert len(intersection) == 0, f"Data leakage detected! Overlapping sources: {intersection}"

    def test_evaluation_metrics_and_breakdowns(self, image_dataset):
        with tempfile.TemporaryDirectory() as tmp_dir:
            analyzer = train_steganalyzer(
                dataset=image_dataset,
                model_type="random_forest",
                models_dir=tmp_dir,
            )

            metrics = analyzer.test_metrics
            assert isinstance(metrics, EvaluationMetrics)
            assert 0.0 <= metrics.accuracy <= 1.0
            assert 0.0 <= metrics.precision <= 1.0
            assert 0.0 <= metrics.recall <= 1.0
            assert 0.0 <= metrics.f1_score <= 1.0
            assert metrics.total_samples == metrics.true_positives + metrics.true_negatives + metrics.false_positives + metrics.false_negatives

            # Verification of breakdown dictionaries
            assert isinstance(metrics.by_payload_category, dict)
            assert isinstance(metrics.by_allocation_strategy, dict)
            assert "limitations" in metrics.limitations_note.lower()

    def test_logistic_regression_model(self, image_dataset):
        with tempfile.TemporaryDirectory() as tmp_dir:
            analyzer = train_steganalyzer(
                dataset=image_dataset,
                model_type="logistic_regression",
                models_dir=tmp_dir,
            )
            assert analyzer.model_type == "logistic_regression"
            assert 0.0 <= analyzer.test_metrics.accuracy <= 1.0

    def test_model_persistence_and_loading(self, image_dataset):
        with tempfile.TemporaryDirectory() as tmp_dir:
            analyzer = train_steganalyzer(
                dataset=image_dataset,
                model_type="random_forest",
                models_dir=tmp_dir,
            )

            loaded = load_steganalyzer("image", model_type="random_forest", models_dir=tmp_dir)
            assert loaded is not None
            assert loaded.modality == "image"
            assert loaded.model_type == "random_forest"
            assert loaded.feature_names == analyzer.feature_names

    def test_single_file_inference_classification(self):
        png_cover = create_synthetic_png(width=64, height=64, pattern="noise")
        result = classify_media_file(png_cover, filename="sample_cover.png", model_type="random_forest")

        assert result.modality == "image"
        assert result.predicted_class in ("Cover", "Stego")
        assert 0.0 <= result.stego_probability <= 1.0
        assert 0.0 <= result.confidence_percentage <= 100.0
        assert "Notice" in result.disclaimer
        assert len(result.feature_values) > 0

    def test_probability_calibration_and_column_ordering(self, image_dataset):
        """Verify probability calibration is fitted and positive class index is verified."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            analyzer = train_steganalyzer(
                dataset=image_dataset,
                model_type="random_forest",
                models_dir=tmp_dir,
            )
            # Probability calibration flag and method must be populated
            assert isinstance(analyzer.is_calibrated, bool)
            assert analyzer.calibration_method != ""
            assert analyzer.test_metrics.is_calibrated == analyzer.is_calibrated

            # Test prediction probability
            sample_feats = np.array(image_dataset.samples[0].features)
            pred_lbl, prob = analyzer.predict(sample_feats)
            assert pred_lbl in (0, 1)
            assert 0.0 <= prob <= 1.0
            # Consistent decision threshold
            assert pred_lbl == int(prob >= 0.5)
