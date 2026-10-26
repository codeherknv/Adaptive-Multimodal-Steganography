"""Phase 8 Experiment Runner & Comparative Visualizer.

Executes paired trials comparing Fixed Baseline vs. Adaptive Feature-Weighted allocation.
Saves:
1. Machine-readable JSON results: outputs/experiments/phase8_comparative_results.json
2. Matched comparative plots (PNG):
   - outputs/experiments/phase8_psnr_snr_comparison.png
   - outputs/experiments/phase8_steganalysis_detectability.png
   - outputs/experiments/phase8_allocation_distribution.png
"""

import sys
import os
import json
import argparse
from typing import List

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from app.evaluation.real_media_loader import (
    load_synthetic_triad,
    load_user_real_media_triads,
    CarrierTriadSource,
)
from app.evaluation.comparative_harness import (
    PairedTrialResult,
    run_comparative_experiment_suite,
)
from app.evaluation.statistical_analyzer import (
    ComparativeExperimentSummary,
    analyze_comparative_results,
)

OUTPUTS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "outputs", "experiments"))
os.makedirs(OUTPUTS_DIR, exist_ok=True)


def generate_plots(results: List[PairedTrialResult], summary: ComparativeExperimentSummary) -> None:
    """Generate publication-ready comparative charts comparing Fixed vs Adaptive allocation."""
    brackets = ["low", "medium", "high"]
    
    # -------------------------------------------------------------
    # Plot 1: Perceptual Quality Comparison (Image PSNR, Audio SNR, Video PSNR)
    # -------------------------------------------------------------
    fig, axes = plt.subplots(1, 3, figsize=(16, 5))
    fig.patch.set_facecolor("#18181b")
    for ax in axes:
        ax.set_facecolor("#27272a")
        ax.tick_params(colors="#d4d4d8")
        ax.xaxis.label.set_color("#d4d4d8")
        ax.yaxis.label.set_color("#d4d4d8")
        ax.title.set_color("#f4f4f5")
        ax.grid(True, linestyle="--", alpha=0.3, color="#71717a")

    # Data aggregations
    metrics_data = [
        ("Image PSNR (dB)", "image_psnr", axes[0]),
        ("Audio SNR (dB)", "audio_snr", axes[1]),
        ("Video Average PSNR (dB)", "video_average_psnr", axes[2]),
    ]

    for title, attr, ax in metrics_data:
        fixed_means = []
        adaptive_means = []
        for b in brackets:
            b_trials = [r for r in results if r.target_payload_bracket == b]
            f_vals = [getattr(r.fixed_result, attr) for r in b_trials if getattr(r.fixed_result, attr) is not None]
            a_vals = [getattr(r.adaptive_result, attr) for r in b_trials if getattr(r.adaptive_result, attr) is not None]
            fixed_means.append(np.mean(f_vals) if f_vals else 0.0)
            adaptive_means.append(np.mean(a_vals) if a_vals else 0.0)

        x = np.arange(len(brackets))
        width = 0.32
        ax.bar(x - width/2, fixed_means, width, label="Fixed Baseline", color="#3b82f6", alpha=0.85)
        ax.bar(x + width/2, adaptive_means, width, label="Adaptive Feature", color="#10b981", alpha=0.85)
        ax.set_title(title, fontsize=12, fontweight="bold")
        ax.set_xticks(x)
        ax.set_xticklabels(["Low (15%)", "Medium (35%)", "High (55%)"])
        ax.legend(facecolor="#18181b", edgecolor="#52525b", labelcolor="#e4e4e7")

    plt.tight_layout()
    plot1_path = os.path.join(OUTPUTS_DIR, "phase8_psnr_snr_comparison.png")
    plt.savefig(plot1_path, dpi=200, bbox_inches="tight")
    plt.close()

    # -------------------------------------------------------------
    # Plot 2: Steganalysis Detectability Comparison (P(Stego) across modalities)
    # -------------------------------------------------------------
    fig, axes = plt.subplots(1, 3, figsize=(16, 5))
    fig.patch.set_facecolor("#18181b")
    for ax in axes:
        ax.set_facecolor("#27272a")
        ax.tick_params(colors="#d4d4d8")
        ax.xaxis.label.set_color("#d4d4d8")
        ax.yaxis.label.set_color("#d4d4d8")
        ax.title.set_color("#f4f4f5")
        ax.grid(True, linestyle="--", alpha=0.3, color="#71717a")

    stego_attrs = [
        ("Image Stego Prob", "image_stego_prob", axes[0]),
        ("Audio Stego Prob", "audio_stego_prob", axes[1]),
        ("Video Stego Prob", "video_stego_prob", axes[2]),
    ]

    for title, attr, ax in stego_attrs:
        fixed_means = []
        adaptive_means = []
        for b in brackets:
            b_trials = [r for r in results if r.target_payload_bracket == b]
            f_vals = [getattr(r.fixed_result, attr) for r in b_trials if getattr(r.fixed_result, attr) is not None]
            a_vals = [getattr(r.adaptive_result, attr) for r in b_trials if getattr(r.adaptive_result, attr) is not None]
            fixed_means.append(np.mean(f_vals) if f_vals else 0.0)
            adaptive_means.append(np.mean(a_vals) if a_vals else 0.0)

        x = np.arange(len(brackets))
        width = 0.32
        ax.bar(x - width/2, fixed_means, width, label="Fixed Baseline", color="#f59e0b", alpha=0.85)
        ax.bar(x + width/2, adaptive_means, width, label="Adaptive Feature", color="#8b5cf6", alpha=0.85)
        ax.axhline(0.50, color="#ef4444", linestyle=":", alpha=0.7, label="Decision Threshold (0.50)")
        ax.set_title(title, fontsize=12, fontweight="bold")
        ax.set_ylim(0.0, 1.05)
        ax.set_xticks(x)
        ax.set_xticklabels(["Low (15%)", "Medium (35%)", "High (55%)"])
        ax.legend(facecolor="#18181b", edgecolor="#52525b", labelcolor="#e4e4e7", loc="upper left")

    plt.tight_layout()
    plot2_path = os.path.join(OUTPUTS_DIR, "phase8_steganalysis_detectability.png")
    plt.savefig(plot2_path, dpi=200, bbox_inches="tight")
    plt.close()

    # -------------------------------------------------------------
    # Plot 3: Allocation Distribution (Bytes allocated per carrier)
    # -------------------------------------------------------------
    fig, ax = plt.subplots(figsize=(10, 5))
    fig.patch.set_facecolor("#18181b")
    ax.set_facecolor("#27272a")
    ax.tick_params(colors="#d4d4d8")
    ax.xaxis.label.set_color("#d4d4d8")
    ax.yaxis.label.set_color("#d4d4d8")
    ax.title.set_color("#f4f4f5")
    ax.grid(True, linestyle="--", alpha=0.3, color="#71717a")

    # Sample distribution comparison across trial indices
    sample_indices = np.arange(min(6, len(results)))
    sample_results = results[:len(sample_indices)]

    fixed_img = [r.fixed_result.image_bytes_allocated for r in sample_results]
    fixed_aud = [r.fixed_result.audio_bytes_allocated for r in sample_results]
    fixed_vid = [r.fixed_result.video_bytes_allocated for r in sample_results]

    adapt_img = [r.adaptive_result.image_bytes_allocated for r in sample_results]
    adapt_aud = [r.adaptive_result.audio_bytes_allocated for r in sample_results]
    adapt_vid = [r.adaptive_result.video_bytes_allocated for r in sample_results]

    width = 0.35
    ax.bar(sample_indices - width/2, fixed_img, width, label="Fixed: Image Bytes", color="#38bdf8")
    ax.bar(sample_indices - width/2, fixed_aud, width, bottom=fixed_img, label="Fixed: Audio Bytes", color="#818cf8")
    ax.bar(sample_indices - width/2, fixed_vid, width, bottom=np.array(fixed_img)+np.array(fixed_aud), label="Fixed: Video Bytes", color="#c084fc")

    ax.bar(sample_indices + width/2, adapt_img, width, label="Adaptive: Image Bytes", color="#34d399")
    ax.bar(sample_indices + width/2, adapt_aud, width, bottom=adapt_img, label="Adaptive: Audio Bytes", color="#fbbf24")
    ax.bar(sample_indices + width/2, adapt_vid, width, bottom=np.array(adapt_img)+np.array(adapt_aud), label="Adaptive: Video Bytes", color="#f87171")

    ax.set_title("Carrier Allocation Allocation Breakdown (Fixed vs Adaptive)", fontsize=12, fontweight="bold")
    ax.set_xlabel("Trial Index")
    ax.set_ylabel("Allocated Payload Bytes")
    ax.set_xticks(sample_indices)
    ax.set_xticklabels([f"T{i+1} ({r.target_payload_bracket})" for i, r in enumerate(sample_results)])
    ax.legend(facecolor="#18181b", edgecolor="#52525b", labelcolor="#e4e4e7", bbox_to_anchor=(1.02, 1), loc="upper left")

    plt.tight_layout()
    plot3_path = os.path.join(OUTPUTS_DIR, "phase8_allocation_distribution.png")
    plt.savefig(plot3_path, dpi=200, bbox_inches="tight")
    plt.close()


def run_experiment(num_sources: int = 8, smoke_test: bool = False) -> None:
    """Execute comparative experiment suite, analyze statistics, and save artifacts."""
    print("=" * 80)
    print("PHASE 8: COMPARATIVE EVALUATION HARNESS (FIXED VS ADAPTIVE ALLOCATION)")
    print("=" * 80)

    # 1. Load Sources
    sources: List[CarrierTriadSource] = []
    
    # Check for real user media
    real_sources = load_user_real_media_triads()
    if real_sources:
        print(f"Loaded {len(real_sources)} user-provided real media triad(s).")
        sources.extend(real_sources)
    else:
        print("Notice: No real user media found in data/real_media/. Using synthetic procedural carriers.")

    # Fill / supplement with synthetic sources
    sources_to_generate = 2 if smoke_test else num_sources
    for i in range(sources_to_generate):
        sources.append(load_synthetic_triad(source_index=i))

    print(f"Total Sources for Evaluation: {len(sources)}")
    print(f"Provenance breakdown: {sum(1 for s in sources if s.provenance == 'user_provided_real')} Real, "
          f"{sum(1 for s in sources if s.provenance == 'synthetic_procedural')} Synthetic")

    # 2. Run Comparative Trials
    brackets = {"low": 0.15, "medium": 0.35, "high": 0.55}
    if smoke_test:
        brackets = {"low": 0.15, "medium": 0.35}

    print(f"\nExecuting paired trials across {len(brackets)} payload bracket(s)...")
    results = run_comparative_experiment_suite(sources=sources, payload_brackets=brackets)
    print(f"Completed {len(results)} paired trials ({len(results) * 2} total strategy executions).")

    # 3. Statistical Analysis
    print("\nComputing paired statistics, confidence intervals, and hypothesis tests...")
    summary = analyze_comparative_results(results)

    # 4. Save JSON Results
    results_json_path = os.path.join(OUTPUTS_DIR, "phase8_comparative_results.json")
    full_output = {
        "metadata": {
            "experiment_timestamp": str(np.datetime64("now")),
            "total_paired_trials": len(results),
            "smoke_test": smoke_test,
        },
        "summary": summary.to_dict(),
        "trials": [r.to_dict() for r in results],
    }
    with open(results_json_path, "w", encoding="utf-8") as f:
        json.dump(full_output, f, indent=2)
    print(f"Saved machine-readable results to: {results_json_path}")

    # 5. Generate Matplotlib Comparison Plots
    print("Generating matched comparison plots in outputs/experiments/...")
    generate_plots(results, summary)
    print("  - Saved phase8_psnr_snr_comparison.png")
    print("  - Saved phase8_steganalysis_detectability.png")
    print("  - Saved phase8_allocation_distribution.png")

    # 6. Print Formatted Terminal Summary
    print("\n" + "=" * 80)
    print("PHASE 8 COMPARATIVE SUMMARY SCORECARD")
    print("=" * 80)
    print(f"Total Paired Trials:        {summary.total_paired_trials}")
    print(f"Authenticated Recovery:     Fixed: {summary.fixed_recovery_rate:.1%} | Adaptive: {summary.adaptive_recovery_rate:.1%}")
    print(f"Mean Execution Runtime:     Fixed: {summary.fixed_mean_runtime_ms:.1f} ms | Adaptive: {summary.adaptive_mean_runtime_ms:.1f} ms (Overhead: {summary.mean_runtime_overhead_ms:+.1f} ms)")
    print("\nPaired Metric Differences (Adaptive - Fixed):")
    print(f"{'Metric':<25} | {'Fixed Mean':<11} | {'Adaptive Mean':<13} | {'Delta':<10} | {'95% CI':<18} | {'p-value':<8}")
    print("-" * 95)
    for k, s in summary.metrics_summary.items():
        ci_str = f"[{s.ci_95_lower}, {s.ci_95_upper}]" if s.ci_95_lower is not None else "N/A"
        p_str = f"{s.p_value:.4f}" if s.p_value is not None else "N/A"
        print(f"{s.metric_name:<25} | {s.mean_fixed:<11.2f} | {s.mean_adaptive:<13.2f} | {s.mean_delta:<+10.2f} | {ci_str:<18} | {p_str:<8}")

    print("\nBreakdown by Payload Bracket:")
    for b, b_data in summary.bracket_summaries.items():
        print(f"  [{b.upper()}] (Trials: {b_data['trial_count']}): "
              f"Img PSNR F={b_data['mean_fixed_image_psnr']}dB / A={b_data['mean_adaptive_image_psnr']}dB | "
              f"Aud SNR F={b_data['mean_fixed_audio_snr']}dB / A={b_data['mean_adaptive_audio_snr']}dB | "
              f"Vid PSNR F={b_data['mean_fixed_video_psnr']}dB / A={b_data['mean_adaptive_video_psnr']}dB")

    print("\nKey Scientific Findings:")
    for f in summary.key_findings:
        print(f"  - {f}")

    print("\nMethodological Limitations & Caveats:")
    for l in summary.limitations:
        print(f"  - {l}")

    print("\n[PHASE 8 EXPERIMENT RUN COMPLETE]")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Phase 8 Comparative Experiment Runner")
    parser.add_argument("--smoke-test", action="store_true", help="Run quick 2-source smoke test")
    parser.add_argument("--sources", type=int, default=8, help="Number of sources to evaluate")
    args = parser.parse_args()

    run_experiment(num_sources=args.sources, smoke_test=args.smoke_test)
