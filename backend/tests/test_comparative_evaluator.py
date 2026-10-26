"""Unit and regression tests for Phase 8 Comparative Evaluation harness and statistical analyzer."""

import pytest
import numpy as np

from app.evaluation.real_media_loader import (
    load_synthetic_triad,
    load_user_real_media_triads,
    CarrierTriadSource,
)
from app.evaluation.comparative_harness import (
    evaluate_single_strategy_on_triad,
    run_comparative_trial,
    run_comparative_experiment_suite,
)
from app.evaluation.statistical_analyzer import (
    compute_paired_metric_stats,
    analyze_comparative_results,
)
from app.core.crypto_utils import generate_key, encrypt


class TestComparativeEvaluationHarness:
    """Test suite for Phase 8 comparative evaluation harness."""

    def test_load_synthetic_triad_provenance_and_metadata(self):
        triad = load_synthetic_triad(source_index=10)
        assert triad.source_id == "syn_src_010"
        assert triad.provenance == "synthetic_procedural"
        assert len(triad.image_bytes) > 0
        assert len(triad.audio_bytes) > 0
        assert len(triad.video_bytes) > 0
        assert "max_usable_payload_bytes" in triad.image_metadata
        assert "max_usable_payload_bytes" in triad.audio_metadata
        assert "max_usable_payload_bytes" in triad.video_metadata

    def test_load_user_real_media_graceful_on_missing_dir(self, tmp_path):
        empty_dir = str(tmp_path / "nonexistent")
        triads = load_user_real_media_triads(empty_dir)
        assert triads == []

    def test_comparative_trial_paired_fairness(self):
        """Verify identical inputs, authenticated plaintext recovery, and delta computation."""
        triad = load_synthetic_triad(source_index=3)
        trial = run_comparative_trial(
            triad=triad,
            trial_index=1,
            payload_bracket="low",
            payload_fraction=0.15,
            plaintext_seed="FairComparisonMessage",
        )

        assert trial.source_id == triad.source_id
        assert trial.provenance == "synthetic_procedural"
        assert trial.target_payload_bracket == "low"

        f = trial.fixed_result
        a = trial.adaptive_result

        # Both must succeed and authenticate 100% exact original plaintext
        assert f.success is True
        assert a.success is True
        assert f.recovered_plaintext_matches is True
        assert a.recovered_plaintext_matches is True

        # Total allocated bytes across carriers must match
        f_total = f.image_bytes_allocated + f.audio_bytes_allocated + f.video_bytes_allocated
        a_total = a.image_bytes_allocated + a.audio_bytes_allocated + a.video_bytes_allocated
        assert f_total == a_total, f"Fixed total ({f_total}) must equal Adaptive total ({a_total})"

        # Quality metrics must be present
        assert f.image_psnr is not None and a.image_psnr is not None
        assert f.audio_snr is not None and a.audio_snr is not None
        assert f.video_average_psnr is not None and a.video_average_psnr is not None

        # Deltas must be calculated
        assert trial.delta_image_psnr == round(a.image_psnr - f.image_psnr, 4)
        assert trial.delta_audio_snr == round(a.audio_snr - f.audio_snr, 4)
        assert trial.delta_video_psnr == round(a.video_average_psnr - f.video_average_psnr, 4)

    def test_overcapacity_failure_recorded_explicitly(self):
        """Verify that over-capacity trials fail explicitly with error reasons and are never dropped."""
        triad = load_synthetic_triad(source_index=4)
        huge_secret = "HugeSecretExceedingCapacity" * 5000
        huge_env = encrypt(huge_secret.encode("utf-8"), generate_key())

        # Attempt evaluation with payload guaranteed to exceed net capacity
        res = evaluate_single_strategy_on_triad(
            triad=triad,
            strategy_name="fixed",
            plaintext_msg=huge_secret,
            pre_encrypted_envelope=huge_env,
            secret_key=generate_key(),
        )

        assert res.success is False
        assert res.error_reason is not None
        assert "exceeds" in res.error_reason.lower() or "capacity" in res.error_reason.lower()
        assert res.recovered_plaintext_matches is False

    def test_statistical_analyzer_computations(self):
        """Verify paired t-test, mean delta, and 95% confidence intervals."""
        fixed_vals = [50.0, 52.0, 54.0, 51.0, 53.0]
        adaptive_vals = [51.5, 53.0, 55.5, 52.0, 54.5]

        stats_summary = compute_paired_metric_stats(
            fixed_values=fixed_vals,
            adaptive_values=adaptive_vals,
            metric_name="Image PSNR",
            higher_is_better=True,
        )

        assert stats_summary.sample_count == 5
        assert stats_summary.mean_fixed == 52.0
        assert stats_summary.mean_adaptive == 53.3
        assert stats_summary.mean_delta == 1.3
        assert stats_summary.ci_95_lower is not None
        assert stats_summary.ci_95_upper is not None
        assert stats_summary.ci_95_lower < stats_summary.mean_delta < stats_summary.ci_95_upper
        assert stats_summary.is_statistically_significant is True
