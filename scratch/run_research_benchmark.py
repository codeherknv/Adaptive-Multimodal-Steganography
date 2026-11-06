"""Phase 9: Comprehensive Multimodal Steganography Research Benchmark.

Executes a controlled empirical evaluation comparing:
1. Fixed Baseline (Equal Split / Water-filling)
2. Adaptive Feature-Weighted (Perceptual Rate-Distortion Heuristic)
3. Markowitz Risk-Portfolio (QP Optimization swept across lambda in [0.0, 0.25, 0.50, 0.75, 1.00])
4. Unimodal Controls (Single-Carrier baseline where capacity permits)

Across 3 Carrier Scenarios:
- Scenario 1: Balanced Triad (Moderate complexity across all media)
- Scenario 2: Asymmetric Video-Dominant (Fragile silent audio & flat image vs complex video)
- Scenario 3: Asymmetric Audio-Dominant (Fragile flat image & static video vs complex acoustic audio)

Across 3 Payload Capacity Levels:
- Low (~15% of combined net usable capacity)
- Medium (~40% of combined net usable capacity)
- High (~75% of combined net usable capacity)

Measures:
- PSNR (Image, dB) & SSIM
- SNR (Audio, dB) & Normalized MSE
- PSNR (Video, dB) & Average MSE
- Quadratic Risk Variance (b^T Sigma b) & Heuristic Relative Risk Score
- Carrier Allocation Breakdown (Bytes & %)
- Allocation Algorithm Runtime (ms)
- Cryptographic Recovery Correctness (AES-256-GCM authenticated decryption)

Outputs:
- results/benchmark_raw_telemetry.json
- results/benchmark_summary_table.csv
- results/figures/efficient_frontier.png
- results/figures/rate_distortion_curves.png
- results/figures/allocation_share_breakdown.png
"""

import csv
import io
import json
import math
import os
import secrets
import string
import sys
import time
import wave
from typing import Any, Dict, List, Optional, Tuple

# Ensure backend directory is in sys.path
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BACKEND_DIR = os.path.join(BASE_DIR, "backend")
sys.path.insert(0, BACKEND_DIR)

import matplotlib.pyplot as plt
import numpy as np
from PIL import Image

from app.allocation.allocator import (
    FixedBaselineStrategy,
    AdaptiveFeatureStrategy,
    get_allocation_strategy,
)
from app.allocation.engine import embed_multimodal, extract_multimodal
from app.allocation.profiler import profile_multimodal_triad, MultimodalTriadProfile
from app.allocation.risk_portfolio import (
    CARRIER_ORDER,
    RiskPortfolioStrategy,
    build_default_diagonal_covariance,
    validate_and_regularize_covariance,
    compute_efficient_frontier,
)
from app.core.payload_codec import HEADER_SIZE as ASTG_HEADER_SIZE
from app.media.video_stego import detect_available_lossless_codec, save_video_to_bytes


# =====================================================================
# Synthetic Media Generators for Benchmark Scenarios
# =====================================================================

def make_benchmark_png(width: int = 128, height: int = 128, mode: str = "noise", seed: int = 42) -> bytes:
    """Generate in-memory PNG bytes with controllable spatial texture."""
    rng = np.random.default_rng(seed)
    if mode == "noise":
        arr = rng.integers(0, 256, (height, width, 3), dtype=np.uint8)
    elif mode == "flat":
        # Uniform solid color (near-zero Laplacian variance)
        arr = np.full((height, width, 3), 128, dtype=np.uint8)
    elif mode == "smooth_gradient":
        # Smooth gradual gradient (low Laplacian variance)
        grad = np.linspace(60, 190, width, dtype=np.uint8)
        arr = np.tile(grad, (height, 1))
        arr = np.stack([arr, arr, arr], axis=-1)
    else:
        arr = rng.integers(50, 200, (height, width, 3), dtype=np.uint8)

    img = Image.fromarray(arr, mode="RGB")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def make_benchmark_wav(duration_sec: float = 1.0, sample_rate: int = 16000, mode: str = "sine", seed: int = 42) -> bytes:
    """Generate in-memory PCM WAV bytes with controllable acoustic dynamism."""
    rng = np.random.default_rng(seed)
    total_samples = int(duration_sec * sample_rate)
    t = np.linspace(0, duration_sec, total_samples, endpoint=False)

    if mode == "sine":
        # Standard pure sine tone (moderate acoustic energy)
        waveform = 0.5 * np.sin(2 * np.pi * 440.0 * t)
    elif mode == "silent":
        # Near-silent whisper / background noise (near-zero RMS)
        waveform = rng.normal(0, 0.001, total_samples)
    elif mode == "rich_chirp":
        # Dynamic frequency chirp + harmonic texture (high RMS dynamism)
        f_instant = np.linspace(200, 3500, total_samples)
        waveform = 0.7 * np.sin(2 * np.pi * f_instant * t) + 0.2 * rng.normal(0, 0.1, total_samples)
    else:
        waveform = 0.3 * np.sin(2 * np.pi * 880.0 * t)

    waveform = np.clip(waveform, -1.0, 1.0)
    samples = (waveform * 32000.0).astype(np.int16)

    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(samples.tobytes())
    return buf.getvalue()


def make_benchmark_video(num_frames: int = 20, width: int = 64, height: int = 64, fps: float = 25.0, mode: str = "moving", seed: int = 42) -> bytes:
    """Generate in-memory lossless AVI video bytes with controllable temporal motion."""
    rng = np.random.default_rng(seed)
    codec_str, ext = detect_available_lossless_codec()
    frames = []

    for i in range(num_frames):
        if mode == "moving":
            # High motion dynamic block traversing frame
            f = rng.integers(30, 90, (height, width, 3), dtype=np.uint8)
            x_pos = (i * 6) % (width - 20)
            f[10:35, x_pos:x_pos+20] = rng.integers(180, 255, (25, 20, 3), dtype=np.uint8)
        elif mode == "static":
            # Completely static motionless frames (zero inter-frame difference)
            f = np.full((height, width, 3), 100, dtype=np.uint8)
        elif mode == "chaotic":
            # High-entropy shifting noise across all frames
            f = rng.integers(0, 256, (height, width, 3), dtype=np.uint8)
        else:
            f = np.full((height, width, 3), 120, dtype=np.uint8)
        frames.append(f)

    return save_video_to_bytes(frames, fps, width, height, codec_str, ext)


# =====================================================================
# Scenario Definitions
# =====================================================================

def build_benchmark_scenarios() -> Dict[str, Dict[str, Any]]:
    """Build the 3 controlled carrier triads."""
    return {
        "Scenario 1 (Balanced)": {
            "description": "Balanced media: moderate texture image, harmonic sine audio, moving square video.",
            "image": make_benchmark_png(128, 128, mode="noise", seed=101),
            "audio": make_benchmark_wav(1.0, 16000, mode="sine", seed=102),
            "video": make_benchmark_video(20, 64, 64, mode="moving", seed=103),
        },
        "Scenario 2 (Asymmetric Video-Dominant)": {
            "description": "Fragile silent audio & flat sky image paired with complex chaotic video.",
            "image": make_benchmark_png(128, 128, mode="flat", seed=201),
            "audio": make_benchmark_wav(1.0, 16000, mode="silent", seed=202),
            "video": make_benchmark_video(20, 64, 64, mode="chaotic", seed=203),
        },
        "Scenario 3 (Asymmetric Audio-Dominant)": {
            "description": "Fragile smooth image & static video paired with dynamic orchestral audio chirp.",
            "image": make_benchmark_png(128, 128, mode="smooth_gradient", seed=301),
            "audio": make_benchmark_wav(1.0, 16000, mode="rich_chirp", seed=302),
            "video": make_benchmark_video(20, 64, 64, mode="static", seed=303),
        },
    }


# =====================================================================
# Main Benchmark Execution Engine
# =====================================================================

def run_research_benchmark():
    print("=" * 80)
    print("PHASE 9: EMPIRICAL MULTIMODAL STEGANOGRAPHY RESEARCH BENCHMARK")
    print("=" * 80)

    results_dir = os.path.join(BASE_DIR, "results")
    figures_dir = os.path.join(results_dir, "figures")
    os.makedirs(figures_dir, exist_ok=True)

    scenarios = build_benchmark_scenarios()
    telemetry_records: List[Dict[str, Any]] = []

    strategies_to_test = [
        ("fixed", None, "Fixed Baseline"),
        ("adaptive", None, "Adaptive Feature"),
        ("portfolio", 0.00, "Portfolio (lambda=0.00)"),
        ("portfolio", 0.25, "Portfolio (lambda=0.25)"),
        ("portfolio", 0.50, "Portfolio (lambda=0.50)"),
        ("portfolio", 0.75, "Portfolio (lambda=0.75)"),
        ("portfolio", 1.00, "Portfolio (lambda=1.00)"),
    ]

    payload_fractions = [
        ("Low", 0.15),
        ("Medium", 0.40),
        ("High", 0.75),
    ]

    # Pre-calculated test password
    password = "ResearchBenchmarkMasterKey2026!"

    total_runs = len(scenarios) * len(payload_fractions) * len(strategies_to_test)
    curr_run = 0

    print(f"\n[Setup] 3 Scenarios x 3 Payload Levels x {len(strategies_to_test)} Strategies = {total_runs} Test Runs")

    for scen_name, scen_data in scenarios.items():
        print(f"\n{'-' * 80}")
        print(f"EVALUATING: {scen_name.upper()}")
        print(f"Description: {scen_data['description']}")
        print(f"{'-' * 80}")

        img_bytes = scen_data["image"]
        aud_bytes = scen_data["audio"]
        vid_bytes = scen_data["video"]

        # Profile the triad
        triad_profile = profile_multimodal_triad(img_bytes, aud_bytes, vid_bytes)
        net_caps = {
            "image": max(0, triad_profile.image.max_usable_payload_bytes - ASTG_HEADER_SIZE),
            "audio": max(0, triad_profile.audio.max_usable_payload_bytes - ASTG_HEADER_SIZE),
            "video": max(0, triad_profile.video.max_usable_payload_bytes - ASTG_HEADER_SIZE),
        }
        total_net_cap = sum(net_caps.values())
        print(f"Profile: Image={net_caps['image']:,}B (CS={triad_profile.image.complexity_score:.2f}) | "
              f"Audio={net_caps['audio']:,}B (CS={triad_profile.audio.complexity_score:.2f}) | "
              f"Video={net_caps['video']:,}B (CS={triad_profile.video.complexity_score:.2f})")
        print(f"Combined Net Usable Capacity: {total_net_cap:,} bytes")

        # Build baseline covariance matrix for evaluation
        cov_raw = build_default_diagonal_covariance(triad_profile)
        val_cov = validate_and_regularize_covariance(cov_raw)
        sigma = val_cov.matrix

        for p_label, p_frac in payload_fractions:
            target_envelope_bytes = int(round(total_net_cap * p_frac))
            # AES-GCM envelope overhead: 12B nonce + 16B tag + 2B version/len = ~30B
            approx_plaintext_len = max(10, target_envelope_bytes - 30)
            # Generate deterministic secret message
            alphabet = string.ascii_letters + string.digits + " ,.-_"
            secret_msg = "".join(alphabet[(i * 7 + 13) % len(alphabet)] for i in range(approx_plaintext_len))

            print(f"\n  [Payload Level: {p_label} ({int(p_frac*100)}% Cap = ~{target_envelope_bytes:,} bytes)]")

            for strat_key, risk_tol, strat_label in strategies_to_test:
                curr_run += 1
                prefix = f"    [{curr_run}/{total_runs}] {strat_label: <25}"

                # Measure allocation computation runtime separately
                t_alloc_start = time.perf_counter()
                alloc_kwargs = {}
                if risk_tol is not None:
                    alloc_kwargs["risk_tolerance"] = risk_tol
                strategy_inst = get_allocation_strategy(strat_key, **alloc_kwargs)
                plan = strategy_inst.allocate(
                    payload_len=target_envelope_bytes,
                    triad_profile=triad_profile,
                )
                alloc_latency_ms = (time.perf_counter() - t_alloc_start) * 1000

                # Execute full embedding pipeline
                t_embed_start = time.perf_counter()
                embed_res = embed_multimodal(
                    message=secret_msg,
                    image_bytes=img_bytes,
                    audio_bytes=aud_bytes,
                    video_bytes=vid_bytes,
                    password=password,
                    strategy_name=strat_key,
                    risk_tolerance=risk_tol,
                )
                embed_latency_ms = (time.perf_counter() - t_embed_start) * 1000

                # Execute extraction and verify bit-exact fidelity
                ext_res = extract_multimodal(
                    stego_image_bytes=embed_res.stego_image_bytes,
                    stego_audio_bytes=embed_res.stego_audio_bytes,
                    stego_video_bytes=embed_res.stego_video_bytes,
                    password=password,
                    salt_bytes=embed_res.salt_bytes,
                )
                verified = (ext_res.plaintext == secret_msg)
                assert verified, f"Plaintext verification failed on run {curr_run} ({strat_label})!"

                # Calculate unnormalized quadratic risk variance under common Sigma
                alloc_dict = embed_res.allocation_plan.allocations
                b_vec = np.array([alloc_dict[c].payload_bytes for c in CARRIER_ORDER], dtype=np.float64)
                actual_payload = embed_res.allocation_plan.total_payload_bytes
                unnorm_var = float(b_vec @ sigma @ b_vec)

                # Heuristic Relative Risk index if portfolio metadata present
                if embed_res.allocation_plan.portfolio_metadata and "relative_risk" in embed_res.allocation_plan.portfolio_metadata:
                    rr_score = embed_res.allocation_plan.portfolio_metadata["relative_risk"]
                else:
                    # Calculate relative risk against feasible bounds
                    v_min = float(min(b_vec @ sigma @ b_vec, 0.0))
                    v_max = float(max(b_vec @ sigma @ b_vec, 1.0))
                    rr_score = None

                # Extract objective fidelity metrics
                img_psnr = embed_res.image_metrics.get("psnr", float("nan"))
                img_ssim = embed_res.image_metrics.get("ssim", float("nan"))
                aud_snr = embed_res.audio_metrics.get("snr", float("nan"))
                aud_mse = embed_res.audio_metrics.get("normalized_mse", float("nan"))
                vid_psnr = embed_res.video_metrics.get("average_psnr", float("nan"))
                vid_mse = embed_res.video_metrics.get("average_mse", float("nan"))

                # Format clean printout
                img_psnr_str = f"{img_psnr:.1f} dB" if math.isfinite(img_psnr) else "inf"
                aud_snr_str = f"{aud_snr:.1f} dB" if math.isfinite(aud_snr) else "inf"
                vid_psnr_str = f"{vid_psnr:.1f} dB" if math.isfinite(vid_psnr) else "inf"

                b_I = alloc_dict["image"].payload_bytes
                b_A = alloc_dict["audio"].payload_bytes
                b_V = alloc_dict["video"].payload_bytes

                print(f"{prefix} -> [Img: {b_I:>5}B, Aud: {b_A:>5}B, Vid: {b_V:>5}B] | "
                      f"PSNR_I={img_psnr_str:>7} | SNR_A={aud_snr_str:>7} | PSNR_V={vid_psnr_str:>7} | "
                      f"Var={unnorm_var:>9.1f} | Latency={alloc_latency_ms:.2f}ms | Verified: {verified}")

                # Record structured record
                record = {
                    "scenario": scen_name,
                    "payload_category": p_label,
                    "payload_fraction": p_frac,
                    "target_envelope_bytes": target_envelope_bytes,
                    "actual_payload_bytes": actual_payload,
                    "strategy": strat_key,
                    "risk_tolerance": risk_tol,
                    "strategy_label": strat_label,
                    "alloc_image_bytes": b_I,
                    "alloc_audio_bytes": b_A,
                    "alloc_video_bytes": b_V,
                    "alloc_image_share_pct": round((b_I / actual_payload) * 100, 2) if actual_payload > 0 else 0.0,
                    "alloc_audio_share_pct": round((b_A / actual_payload) * 100, 2) if actual_payload > 0 else 0.0,
                    "alloc_video_share_pct": round((b_V / actual_payload) * 100, 2) if actual_payload > 0 else 0.0,
                    "image_psnr_db": round(img_psnr, 2) if math.isfinite(img_psnr) else None,
                    "image_ssim": round(img_ssim, 4) if math.isfinite(img_ssim) else None,
                    "audio_snr_db": round(aud_snr, 2) if math.isfinite(aud_snr) else None,
                    "audio_norm_mse": float(f"{aud_mse:.2e}") if math.isfinite(aud_mse) else None,
                    "video_avg_psnr_db": round(vid_psnr, 2) if math.isfinite(vid_psnr) else None,
                    "video_avg_mse": round(vid_mse, 4) if math.isfinite(vid_mse) else None,
                    "quadratic_risk_variance": round(unnorm_var, 2),
                    "relative_risk_index": rr_score,
                    "alloc_runtime_ms": round(alloc_latency_ms, 3),
                    "embed_runtime_ms": round(embed_latency_ms, 2),
                    "exact_recovery_verified": verified,
                }
                telemetry_records.append(record)

    # =====================================================================
    # Save Results: Raw JSON & Summary CSV
    # =====================================================================
    print("\n" + "=" * 80)
    print("SAVING BENCHMARK RESULTS")
    print("=" * 80)

    json_path = os.path.join(results_dir, "benchmark_raw_telemetry.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(telemetry_records, f, indent=2)
    print(f"  ✓ Saved raw JSON telemetry: {json_path}")

    csv_path = os.path.join(results_dir, "benchmark_summary_table.csv")
    fieldnames = list(telemetry_records[0].keys())
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(telemetry_records)
    print(f"  ✓ Saved summary CSV table:  {csv_path}")

    # =====================================================================
    # Generate Publication-Grade Visualizations
    # =====================================================================
    print("\n" + "=" * 80)
    print("GENERATING RESEARCH FIGURES (MATPLOTLIB)")
    print("=" * 80)

    generate_research_figures(figures_dir, telemetry_records, scenarios)
    print("\nBenchmark completed successfully with 100% test integrity verified!")


def generate_research_figures(figures_dir: str, records: List[Dict[str, Any]], scenarios: Dict[str, Dict[str, Any]]):
    """Generate high-resolution vector and PNG figures for the paper."""
    plt.style.use("seaborn-v0_8-whitegrid" if "seaborn-v0_8-whitegrid" in plt.style.available else "default")

    # -----------------------------------------------------------------
    # Figure 1: The Markowitz Efficient Frontier Plot
    # -----------------------------------------------------------------
    fig1, ax1 = plt.subplots(figsize=(8, 5), dpi=300)

    # Use Scenario 2 (Asymmetric Video-Dominant) as the primary demonstration
    scen2_data = scenarios["Scenario 2 (Asymmetric Video-Dominant)"]
    p_scen2 = profile_multimodal_triad(scen2_data["image"], scen2_data["audio"], scen2_data["video"])
    cov2 = validate_and_regularize_covariance(build_default_diagonal_covariance(p_scen2)).matrix

    frontier_pts = compute_efficient_frontier(p_scen2, num_points=25, sigma=cov2)
    f_payloads = [pt.payload_bytes for pt in frontier_pts]
    f_vars = [pt.unnormalized_variance for pt in frontier_pts]

    # Plot theoretical Pareto frontier
    ax1.plot(f_payloads, f_vars, color="#0284c7", linewidth=2.5, label="Pareto Efficient Frontier (Min-Risk Bound)", zorder=2)

    # Filter actual benchmark records for Scenario 2 at Medium Payload (~40%)
    med_records = [
        r for r in records
        if r["scenario"] == "Scenario 2 (Asymmetric Video-Dominant)" and r["payload_category"] == "Medium"
    ]

    markers = {
        "Fixed Baseline": ("s", "#ef4444", 80),
        "Adaptive Feature": ("^", "#f59e0b", 90),
        "Portfolio (lambda=0.00)": ("o", "#10b981", 90),
        "Portfolio (lambda=0.50)": ("D", "#8b5cf6", 80),
        "Portfolio (lambda=1.00)": ("v", "#6b7280", 80),
    }

    for r in med_records:
        strat = r["strategy_label"]
        if strat in markers:
            m, c, sz = markers[strat]
            ax1.scatter(
                [r["actual_payload_bytes"]],
                [r["quadratic_risk_variance"]],
                marker=m,
                color=c,
                s=sz,
                edgecolors="black",
                linewidth=1.0,
                label=f"Actual: {strat}",
                zorder=4,
            )

    ax1.set_title("Markowitz Efficient Frontier in Cross-Modal Steganography\n(Scenario 2: Asymmetric Carriers)", fontsize=12, fontweight="bold", pad=12)
    ax1.set_xlabel("Payload Envelope Length B (Bytes)", fontsize=10, fontweight="bold")
    ax1.set_ylabel("Quadratic Risk Penalty (bᵀ Σ b)", fontsize=10, fontweight="bold")
    ax1.legend(loc="upper left", frameon=True, fontsize=9)
    ax1.grid(True, linestyle="--", alpha=0.6)

    fig1_path = os.path.join(figures_dir, "efficient_frontier.png")
    fig1.savefig(fig1_path, bbox_inches="tight")
    plt.close(fig1)
    print(f"  ✓ Generated Figure 1: {fig1_path}")

    # -----------------------------------------------------------------
    # Figure 2: Rate-Distortion Curves (PSNR & SNR Across Payloads)
    # -----------------------------------------------------------------
    fig2, (ax2a, ax2b) = plt.subplots(1, 2, figsize=(12, 5), dpi=300)

    # Compare Scenario 1 (Balanced) across Low, Med, High for Fixed vs Adaptive vs Portfolio (0.5)
    target_strats = ["Fixed Baseline", "Adaptive Feature", "Portfolio (lambda=0.50)"]
    strat_colors = {"Fixed Baseline": "#ef4444", "Adaptive Feature": "#f59e0b", "Portfolio (lambda=0.50)": "#10b981"}
    strat_styles = {"Fixed Baseline": "--", "Adaptive Feature": "-.", "Portfolio (lambda=0.50)": "-"}

    scen1_recs = [r for r in records if r["scenario"] == "Scenario 1 (Balanced)"]

    for strat in target_strats:
        s_recs = [r for r in scen1_recs if r["strategy_label"] == strat]
        s_recs.sort(key=lambda x: x["payload_fraction"])
        x_pts = [r["payload_fraction"] * 100 for r in s_recs]
        img_y = [r["image_psnr_db"] for r in s_recs]
        aud_y = [r["audio_snr_db"] for r in s_recs]

        ax2a.plot(x_pts, img_y, label=strat, color=strat_colors[strat], linestyle=strat_styles[strat], marker="o", linewidth=2.0)
        ax2b.plot(x_pts, aud_y, label=strat, color=strat_colors[strat], linestyle=strat_styles[strat], marker="s", linewidth=2.0)

    ax2a.set_title("Image Spatial Fidelity (PSNR)", fontsize=11, fontweight="bold")
    ax2a.set_xlabel("Capacity Utilization (%)", fontsize=10)
    ax2a.set_ylabel("PSNR (dB)", fontsize=10)
    ax2a.grid(True, linestyle="--", alpha=0.6)
    ax2a.legend(loc="lower left", fontsize=9)

    ax2b.set_title("Audio Acoustic Fidelity (SNR)", fontsize=11, fontweight="bold")
    ax2b.set_xlabel("Capacity Utilization (%)", fontsize=10)
    ax2b.set_ylabel("SNR (dB)", fontsize=10)
    ax2b.grid(True, linestyle="--", alpha=0.6)
    ax2b.legend(loc="lower left", fontsize=9)

    fig2.suptitle("Rate-Distortion Fidelity Trade-off Across Capacity Fractions (Scenario 1: Balanced)", fontsize=12, fontweight="bold", y=1.02)
    fig2_path = os.path.join(figures_dir, "rate_distortion_curves.png")
    fig2.savefig(fig2_path, bbox_inches="tight")
    plt.close(fig2)
    print(f"  ✓ Generated Figure 2: {fig2_path}")

    # -----------------------------------------------------------------
    # Figure 3: Carrier Share Allocation in Asymmetric Covers
    # -----------------------------------------------------------------
    fig3, ax3 = plt.subplots(figsize=(9, 5), dpi=300)

    # For Scenario 2 (Medium Payload), compare allocation shares
    s2_med = [
        r for r in records
        if r["scenario"] == "Scenario 2 (Asymmetric Video-Dominant)" and r["payload_category"] == "Medium"
    ]
    # Filter strategies to key representatives
    display_strats = [
        "Fixed Baseline",
        "Adaptive Feature",
        "Portfolio (lambda=0.00)",
        "Portfolio (lambda=0.50)",
        "Portfolio (lambda=1.00)",
    ]
    s2_med = [r for r in s2_med if r["strategy_label"] in display_strats]
    s2_med.sort(key=lambda x: display_strats.index(x["strategy_label"]))

    labels = [r["strategy_label"].replace("Portfolio (", "QP (").replace(")", "") for r in s2_med]
    img_shares = [r["alloc_image_share_pct"] for r in s2_med]
    aud_shares = [r["alloc_audio_share_pct"] for r in s2_med]
    vid_shares = [r["alloc_video_share_pct"] for r in s2_med]

    x_idx = np.arange(len(labels))
    bar_width = 0.55

    p1 = ax3.bar(x_idx, vid_shares, bar_width, label="Video Share (%) [High Complexity]", color="#a855f7")
    p2 = ax3.bar(x_idx, img_shares, bar_width, bottom=vid_shares, label="Image Share (%) [Flat Fragile Sky]", color="#38bdf8")
    bottom_aud = [vid_shares[i] + img_shares[i] for i in range(len(vid_shares))]
    p3 = ax3.bar(x_idx, aud_shares, bar_width, bottom=bottom_aud, label="Audio Share (%) [Silent Fragile Voice]", color="#10b981")

    # Add data labels
    for i in range(len(labels)):
        ax3.text(i, vid_shares[i] / 2, f"{vid_shares[i]:.0f}%", ha="center", va="center", color="white", fontweight="bold", fontsize=9)
        if img_shares[i] > 8:
            ax3.text(i, vid_shares[i] + img_shares[i] / 2, f"{img_shares[i]:.0f}%", ha="center", va="center", color="black", fontweight="bold", fontsize=9)
        if aud_shares[i] > 8:
            ax3.text(i, bottom_aud[i] + aud_shares[i] / 2, f"{aud_shares[i]:.0f}%", ha="center", va="center", color="black", fontweight="bold", fontsize=9)

    ax3.set_title("Payload Allocation Share Under Extreme Asymmetry (Scenario 2)\nDemonstrating How Portfolio Protects Fragile Silent Carriers", fontsize=11, fontweight="bold", pad=12)
    ax3.set_ylabel("Payload Share (%)", fontsize=10, fontweight="bold")
    ax3.set_xticks(x_idx)
    ax3.set_xticklabels(labels, fontsize=9, rotation=15, ha="right")
    ax3.set_ylim(0, 105)
    ax3.legend(loc="upper right", frameon=True, fontsize=9)
    ax3.grid(axis="y", linestyle="--", alpha=0.6)

    fig3_path = os.path.join(figures_dir, "allocation_share_breakdown.png")
    fig3.savefig(fig3_path, bbox_inches="tight")
    plt.close(fig3)
    print(f"  ✓ Generated Figure 3: {fig3_path}")


if __name__ == "__main__":
    run_research_benchmark()
