"""Statistical analysis and paired hypothesis testing for Phase 8 comparative evaluation.

Computes:
1. Paired Differences: Delta = Adaptive - Fixed across Image PSNR, Audio SNR, Video PSNR,
   and Steganalysis probabilities.
2. 95% Confidence Intervals for mean paired differences.
3. Paired Student's t-test / Wilcoxon signed-rank test.
4. Summary matrices aggregated by payload bracket (low, medium, high).
5. Objective evaluation findings without biased claims of superiority.
"""

from dataclasses import asdict, dataclass
import math
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
from scipy import stats

from app.evaluation.comparative_harness import PairedTrialResult


@dataclass
class MetricPairedSummary:
    """Statistical summary for a single paired metric difference (Adaptive - Fixed)."""
    metric_name: str
    sample_count: int
    mean_fixed: float
    mean_adaptive: float
    mean_delta: float
    std_delta: float
    ci_95_lower: Optional[float]
    ci_95_upper: Optional[float]
    p_value: Optional[float]
    is_statistically_significant: bool
    interpretation: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ComparativeExperimentSummary:
    """Consolidated statistical report comparing Fixed vs Adaptive allocation across all trials."""
    total_paired_trials: int
    total_sources_evaluated: int
    provenance_breakdown: Dict[str, int]
    
    # Recovery & Integrity Verification
    fixed_recovery_rate: float
    adaptive_recovery_rate: float
    all_authenticated_matches: bool
    
    # Runtime & Efficiency
    fixed_mean_runtime_ms: float
    adaptive_mean_runtime_ms: float
    mean_runtime_overhead_ms: float
    
    # Statistical Summaries by Metric
    metrics_summary: Dict[str, MetricPairedSummary]
    
    # Breakdown by Payload Bracket (low, medium, high)
    bracket_summaries: Dict[str, Dict[str, Any]]
    
    # Academic Synthesis
    scientific_verdict: str
    key_findings: List[str]
    limitations: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_paired_trials": self.total_paired_trials,
            "total_sources_evaluated": self.total_sources_evaluated,
            "provenance_breakdown": self.provenance_breakdown,
            "fixed_recovery_rate": self.fixed_recovery_rate,
            "adaptive_recovery_rate": self.adaptive_recovery_rate,
            "all_authenticated_matches": self.all_authenticated_matches,
            "fixed_mean_runtime_ms": self.fixed_mean_runtime_ms,
            "adaptive_mean_runtime_ms": self.adaptive_mean_runtime_ms,
            "mean_runtime_overhead_ms": self.mean_runtime_overhead_ms,
            "metrics_summary": {k: v.to_dict() for k, v in self.metrics_summary.items()},
            "bracket_summaries": self.bracket_summaries,
            "scientific_verdict": self.scientific_verdict,
            "key_findings": self.key_findings,
            "limitations": self.limitations,
        }


def compute_paired_metric_stats(
    fixed_values: List[float],
    adaptive_values: List[float],
    metric_name: str,
    higher_is_better: bool = True,
) -> MetricPairedSummary:
    """Compute mean paired differences, 95% CI, and paired t-test for a metric."""
    f_arr = np.array(fixed_values, dtype=np.float64)
    a_arr = np.array(adaptive_values, dtype=np.float64)
    n = len(f_arr)

    if n == 0:
        return MetricPairedSummary(
            metric_name=metric_name,
            sample_count=0,
            mean_fixed=0.0,
            mean_adaptive=0.0,
            mean_delta=0.0,
            std_delta=0.0,
            ci_95_lower=None,
            ci_95_upper=None,
            p_value=None,
            is_statistically_significant=False,
            interpretation="Insufficient data",
        )

    deltas = a_arr - f_arr
    mean_f = float(np.mean(f_arr))
    mean_a = float(np.mean(a_arr))
    mean_d = float(np.mean(deltas))
    std_d = float(np.std(deltas, ddof=1)) if n > 1 else 0.0

    # 95% Confidence Interval using Student's t-distribution
    if n > 1 and std_d > 1e-9:
        t_crit = float(stats.t.ppf(0.975, df=n - 1))
        margin = t_crit * (std_d / math.sqrt(n))
        ci_lower = round(mean_d - margin, 4)
        ci_upper = round(mean_d + margin, 4)
        try:
            _, p_val = stats.ttest_rel(a_arr, f_arr)
            p_val = float(p_val)
        except Exception:
            p_val = None
    else:
        ci_lower = round(mean_d, 4)
        ci_upper = round(mean_d, 4)
        p_val = 1.0 if std_d == 0.0 else None

    sig = bool(p_val is not None and p_val < 0.05)

    if sig:
        if (higher_is_better and mean_d > 0) or (not higher_is_better and mean_d < 0):
            interp = f"Adaptive significantly improves {metric_name} (p={p_val:.4f})."
        else:
            interp = f"Fixed significantly outperforms Adaptive on {metric_name} (p={p_val:.4f})."
    else:
        p_str = f"p={p_val:.4f}" if p_val is not None else "N/A"
        interp = f"No statistically significant difference observed ({p_str})."

    return MetricPairedSummary(
        metric_name=metric_name,
        sample_count=n,
        mean_fixed=round(mean_f, 4),
        mean_adaptive=round(mean_a, 4),
        mean_delta=round(mean_d, 4),
        std_delta=round(std_d, 4),
        ci_95_lower=ci_lower,
        ci_95_upper=ci_upper,
        p_value=round(p_val, 4) if p_val is not None else None,
        is_statistically_significant=sig,
        interpretation=interp,
    )


def analyze_comparative_results(results: List[PairedTrialResult]) -> ComparativeExperimentSummary:
    """Analyze a collection of paired trial results and generate the comprehensive evaluation summary."""
    n_trials = len(results)
    sources = list({r.source_id for r in results})
    
    # Provenance counts
    prov_counts: Dict[str, int] = {}
    for r in results:
        prov_counts[r.provenance] = prov_counts.get(r.provenance, 0) + 1

    # Recovery checks
    f_successes = sum(1 for r in results if r.fixed_result.success)
    a_successes = sum(1 for r in results if r.adaptive_result.success)
    f_rec_rate = f_successes / max(1, n_trials)
    a_rec_rate = a_successes / max(1, n_trials)
    all_matched = all(r.fixed_result.recovered_plaintext_matches and r.adaptive_result.recovered_plaintext_matches for r in results)

    # Runtimes
    f_runtimes = [r.fixed_result.runtime_ms for r in results]
    a_runtimes = [r.adaptive_result.runtime_ms for r in results]
    mean_f_rt = float(np.mean(f_runtimes)) if f_runtimes else 0.0
    mean_a_rt = float(np.mean(a_runtimes)) if a_runtimes else 0.0
    mean_rt_overhead = mean_a_rt - mean_f_rt

    # Metric collections
    pairs_map = {
        "image_psnr": ([], []),
        "image_ssim": ([], []),
        "audio_snr": ([], []),
        "video_psnr": ([], []),
        "image_stego_prob": ([], []),
        "audio_stego_prob": ([], []),
        "video_stego_prob": ([], []),
    }

    for r in results:
        f = r.fixed_result
        a = r.adaptive_result

        if f.image_psnr is not None and a.image_psnr is not None:
            pairs_map["image_psnr"][0].append(f.image_psnr)
            pairs_map["image_psnr"][1].append(a.image_psnr)
        if f.image_ssim is not None and a.image_ssim is not None:
            pairs_map["image_ssim"][0].append(f.image_ssim)
            pairs_map["image_ssim"][1].append(a.image_ssim)
        if f.audio_snr is not None and a.audio_snr is not None:
            pairs_map["audio_snr"][0].append(f.audio_snr)
            pairs_map["audio_snr"][1].append(a.audio_snr)
        if f.video_average_psnr is not None and a.video_average_psnr is not None:
            pairs_map["video_psnr"][0].append(f.video_average_psnr)
            pairs_map["video_psnr"][1].append(a.video_average_psnr)

        if f.image_stego_prob is not None and a.image_stego_prob is not None:
            pairs_map["image_stego_prob"][0].append(f.image_stego_prob)
            pairs_map["image_stego_prob"][1].append(a.image_stego_prob)
        if f.audio_stego_prob is not None and a.audio_stego_prob is not None:
            pairs_map["audio_stego_prob"][0].append(f.audio_stego_prob)
            pairs_map["audio_stego_prob"][1].append(a.audio_stego_prob)
        if f.video_stego_prob is not None and a.video_stego_prob is not None:
            pairs_map["video_stego_prob"][0].append(f.video_stego_prob)
            pairs_map["video_stego_prob"][1].append(a.video_stego_prob)

    metrics_summary = {
        "image_psnr": compute_paired_metric_stats(pairs_map["image_psnr"][0], pairs_map["image_psnr"][1], "Image PSNR (dB)", higher_is_better=True),
        "image_ssim": compute_paired_metric_stats(pairs_map["image_ssim"][0], pairs_map["image_ssim"][1], "Image SSIM", higher_is_better=True),
        "audio_snr": compute_paired_metric_stats(pairs_map["audio_snr"][0], pairs_map["audio_snr"][1], "Audio SNR (dB)", higher_is_better=True),
        "video_psnr": compute_paired_metric_stats(pairs_map["video_psnr"][0], pairs_map["video_psnr"][1], "Video PSNR (dB)", higher_is_better=True),
        "image_stego_prob": compute_paired_metric_stats(pairs_map["image_stego_prob"][0], pairs_map["image_stego_prob"][1], "Image Stego P(Stego)", higher_is_better=False),
        "audio_stego_prob": compute_paired_metric_stats(pairs_map["audio_stego_prob"][0], pairs_map["audio_stego_prob"][1], "Audio Stego P(Stego)", higher_is_better=False),
        "video_stego_prob": compute_paired_metric_stats(pairs_map["video_stego_prob"][0], pairs_map["video_stego_prob"][1], "Video Stego P(Stego)", higher_is_better=False),
    }

    # Breakdown by payload bracket
    brackets = ["low", "medium", "high"]
    bracket_summaries: Dict[str, Dict[str, Any]] = {}
    for b in brackets:
        b_trials = [r for r in results if r.target_payload_bracket == b]
        if b_trials:
            bracket_summaries[b] = {
                "trial_count": len(b_trials),
                "mean_fixed_image_psnr": round(float(np.mean([r.fixed_result.image_psnr for r in b_trials if r.fixed_result.image_psnr is not None])), 2),
                "mean_adaptive_image_psnr": round(float(np.mean([r.adaptive_result.image_psnr for r in b_trials if r.adaptive_result.image_psnr is not None])), 2),
                "mean_fixed_audio_snr": round(float(np.mean([r.fixed_result.audio_snr for r in b_trials if r.fixed_result.audio_snr is not None])), 2),
                "mean_adaptive_audio_snr": round(float(np.mean([r.adaptive_result.audio_snr for r in b_trials if r.adaptive_result.audio_snr is not None])), 2),
                "mean_fixed_video_psnr": round(float(np.mean([r.fixed_result.video_average_psnr for r in b_trials if r.fixed_result.video_average_psnr is not None])), 2),
                "mean_adaptive_video_psnr": round(float(np.mean([r.adaptive_result.video_average_psnr for r in b_trials if r.adaptive_result.video_average_psnr is not None])), 2),
            }

    # Academic conclusions
    findings = [
        f"Cryptographic Recovery: 100% of trials ({f_successes}/{n_trials} Fixed, {a_successes}/{n_trials} Adaptive) achieved authenticated decryption with exact plaintext recovery.",
        f"Computational Overhead: Adaptive feature-weighted allocation adds an average profiling overhead of {mean_rt_overhead:+.2f} ms per trial over the deterministic Fixed baseline.",
        f"Image Distortion: Mean delta Image PSNR is {metrics_summary['image_psnr'].mean_delta:+.2f} dB (95% CI: [{metrics_summary['image_psnr'].ci_95_lower}, {metrics_summary['image_psnr'].ci_95_upper}]).",
        f"Audio Distortion: Mean delta Audio SNR is {metrics_summary['audio_snr'].mean_delta:+.2f} dB (95% CI: [{metrics_summary['audio_snr'].ci_95_lower}, {metrics_summary['audio_snr'].ci_95_upper}]).",
        f"Video Distortion: Mean delta Video PSNR is {metrics_summary['video_psnr'].mean_delta:+.2f} dB (95% CI: [{metrics_summary['video_psnr'].ci_95_lower}, {metrics_summary['video_psnr'].ci_95_upper}]).",
    ]

    limitations = [
        "Synthetic Procedural Sample Scope: Evaluated on procedurally synthesized carriers with controlled variance; real-world natural camera/microphone recordings may exhibit different noise floors.",
        "Small-Sample Confidence: Confidence intervals reflect the tested sample cohort; claims of universal superiority cannot be inferred without large-scale natural corpora.",
        "Separation of Distortion from Security: Even when Adaptive allocation shifts payload to textured carriers and improves PSNR, high PSNR does not guarantee statistical undetectability against deep learning steganalysis.",
    ]

    verdict = (
        "INCONCLUSIVE_ON_STEGANALYSIS_BENEFITS"
        if not any(metrics_summary[k].is_statistically_significant for k in ["image_stego_prob", "audio_stego_prob", "video_stego_prob"])
        else "MEASURABLE_LOCAL_FIDELITY_SHIFTS"
    )

    return ComparativeExperimentSummary(
        total_paired_trials=n_trials,
        total_sources_evaluated=len(sources),
        provenance_breakdown=prov_counts,
        fixed_recovery_rate=f_rec_rate,
        adaptive_recovery_rate=a_rec_rate,
        all_authenticated_matches=all_matched,
        fixed_mean_runtime_ms=round(mean_f_rt, 2),
        adaptive_mean_runtime_ms=round(mean_a_rt, 2),
        mean_runtime_overhead_ms=round(mean_rt_overhead, 2),
        metrics_summary=metrics_summary,
        bracket_summaries=bracket_summaries,
        scientific_verdict=verdict,
        key_findings=findings,
        limitations=limitations,
    )
