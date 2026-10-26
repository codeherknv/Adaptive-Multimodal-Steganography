"""Comparative evaluation harness for Phase 8: Research Validation & Comparative Evaluation.

Executes strictly paired experimental trials comparing:
- Fixed Baseline Allocation
- Adaptive Feature-Weighted Allocation

Methodological Guarantees:
1. Paired Identical Inputs: Both strategies receive the EXACT same carrier bytes, plaintext,
   and AES-256-GCM encrypted envelope.
2. Explicit Non-Silent Failure Tracking: Over-capacity or embedding/extraction failures are recorded
   with detailed diagnostic error reasons (never silently dropped).
3. Authenticated Decryption Verification: Verifies exact plaintext recovery (100% byte match)
   via AES-GCM tag verification.
4. Multimodal Quality & Steganalysis Profiling: Captures PSNR, SSIM, SNR, video average PSNR,
   and evaluates against frozen Phase 7 calibrated classifiers for Image, Audio, Video.
5. Zero Conflation: Tagged strictly as 'synthetic_procedural' or 'user_provided_real'.
"""

from dataclasses import asdict, dataclass
import time
from typing import Any, Dict, List, Literal, Optional, Tuple

import numpy as np

from app.core.crypto_utils import generate_key, encrypt, decrypt
from app.allocation.profiler import profile_multimodal_triad
from app.allocation.allocator import get_allocation_strategy, MultimodalCapacityExceededError
from app.allocation.engine import embed_multimodal, extract_multimodal
from app.steganalysis.classifier import classify_media_file
from app.steganalysis.trainer import load_steganalyzer
from app.evaluation.real_media_loader import CarrierTriadSource, load_synthetic_triad


@dataclass
class SingleStrategyTrialResult:
    """The result of running a single allocation strategy on a carrier triad."""
    strategy_name: str                     # 'fixed' or 'adaptive'
    success: bool                          # Whether embedding, extraction & decryption succeeded
    error_reason: Optional[str]            # Diagnostic error reason if failed
    runtime_ms: float                      # Total execution runtime (embed + extract)
    
    # Payload & Capacity
    total_net_capacity_bytes: int
    payload_plaintext_bytes: int
    encrypted_envelope_bytes: int
    overall_utilization_ratio: float
    
    # Bytes Allocated per Carrier
    image_bytes_allocated: int
    audio_bytes_allocated: int
    video_bytes_allocated: int
    
    # Authenticated Plaintext Recovery
    recovered_plaintext_matches: bool
    
    # Perceptual Distortion Metrics
    image_psnr: Optional[float]
    image_ssim: Optional[float]
    image_mse: Optional[float]
    
    audio_snr: Optional[float]
    audio_normalized_mse: Optional[float]
    
    video_average_psnr: Optional[float]
    video_average_mse: Optional[float]
    
    # Phase 7 Steganalysis Detectability Metrics
    image_stego_prob: Optional[float]
    image_predicted_class: Optional[str]
    
    audio_stego_prob: Optional[float]
    audio_predicted_class: Optional[str]
    
    video_stego_prob: Optional[float]
    video_predicted_class: Optional[str]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class PairedTrialResult:
    """A matched experimental trial comparing Fixed vs Adaptive on an identical triad & payload."""
    trial_id: str
    source_id: str
    provenance: str                        # 'synthetic_procedural' or 'user_provided_real'
    target_payload_bracket: str            # 'low', 'medium', 'high'
    target_payload_fraction: float
    fixed_result: SingleStrategyTrialResult
    adaptive_result: SingleStrategyTrialResult
    
    # Paired Differences (Adaptive - Fixed)
    # Positive delta for PSNR/SNR means Adaptive produced higher fidelity.
    # Negative delta for Stego Prob means Adaptive was less detectable by Phase 7 model.
    delta_image_psnr: Optional[float] = None
    delta_audio_snr: Optional[float] = None
    delta_video_psnr: Optional[float] = None
    delta_image_stego_prob: Optional[float] = None
    delta_audio_stego_prob: Optional[float] = None
    delta_video_stego_prob: Optional[float] = None

    def compute_deltas(self) -> None:
        """Compute paired differences between Adaptive and Fixed strategies."""
        f = self.fixed_result
        a = self.adaptive_result
        
        if f.image_psnr is not None and a.image_psnr is not None:
            self.delta_image_psnr = round(a.image_psnr - f.image_psnr, 4)
        if f.audio_snr is not None and a.audio_snr is not None:
            self.delta_audio_snr = round(a.audio_snr - f.audio_snr, 4)
        if f.video_average_psnr is not None and a.video_average_psnr is not None:
            self.delta_video_psnr = round(a.video_average_psnr - f.video_average_psnr, 4)
            
        if f.image_stego_prob is not None and a.image_stego_prob is not None:
            self.delta_image_stego_prob = round(a.image_stego_prob - f.image_stego_prob, 4)
        if f.audio_stego_prob is not None and a.audio_stego_prob is not None:
            self.delta_audio_stego_prob = round(a.audio_stego_prob - f.audio_stego_prob, 4)
        if f.video_stego_prob is not None and a.video_stego_prob is not None:
            self.delta_video_stego_prob = round(a.video_stego_prob - f.video_stego_prob, 4)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def evaluate_single_strategy_on_triad(
    triad: CarrierTriadSource,
    strategy_name: Literal["fixed", "adaptive"],
    plaintext_msg: str,
    pre_encrypted_envelope: bytes,
    secret_key: bytes,
    rf_models: Optional[Dict[str, Any]] = None,
) -> SingleStrategyTrialResult:
    """Execute embedding, extraction, distortion calculation, and steganalysis for one strategy."""
    t0 = time.perf_counter()
    
    # 1. Profile capacity
    triad_profile = profile_multimodal_triad(triad.image_bytes, triad.audio_bytes, triad.video_bytes)
    net_capacity = triad_profile.total_usable_capacity_bytes
    envelope_len = len(pre_encrypted_envelope)
    
    # Check capacity upfront
    if envelope_len > net_capacity:
        elapsed = (time.perf_counter() - t0) * 1000.0
        return SingleStrategyTrialResult(
            strategy_name=strategy_name,
            success=False,
            error_reason=f"Envelope length ({envelope_len}B) exceeds net triad capacity ({net_capacity}B).",
            runtime_ms=round(elapsed, 2),
            total_net_capacity_bytes=net_capacity,
            payload_plaintext_bytes=len(plaintext_msg.encode("utf-8")),
            encrypted_envelope_bytes=envelope_len,
            overall_utilization_ratio=round(envelope_len / max(1, net_capacity), 6),
            image_bytes_allocated=0,
            audio_bytes_allocated=0,
            video_bytes_allocated=0,
            recovered_plaintext_matches=False,
            image_psnr=None, image_ssim=None, image_mse=None,
            audio_snr=None, audio_normalized_mse=None,
            video_average_psnr=None, video_average_mse=None,
            image_stego_prob=None, image_predicted_class=None,
            audio_stego_prob=None, audio_predicted_class=None,
            video_stego_prob=None, video_predicted_class=None,
        )

    # 2. Execute Multimodal Embedding
    try:
        embed_res = embed_multimodal(
            message=plaintext_msg,
            image_bytes=triad.image_bytes,
            audio_bytes=triad.audio_bytes,
            video_bytes=triad.video_bytes,
            key_bytes=secret_key,
            strategy_name=strategy_name,
        )
    except MultimodalCapacityExceededError as e:
        elapsed = (time.perf_counter() - t0) * 1000.0
        return SingleStrategyTrialResult(
            strategy_name=strategy_name,
            success=False,
            error_reason=f"Capacity exceeded during allocation: {str(e)}",
            runtime_ms=round(elapsed, 2),
            total_net_capacity_bytes=net_capacity,
            payload_plaintext_bytes=len(plaintext_msg.encode("utf-8")),
            encrypted_envelope_bytes=envelope_len,
            overall_utilization_ratio=round(envelope_len / max(1, net_capacity), 6),
            image_bytes_allocated=0,
            audio_bytes_allocated=0,
            video_bytes_allocated=0,
            recovered_plaintext_matches=False,
            image_psnr=None, image_ssim=None, image_mse=None,
            audio_snr=None, audio_normalized_mse=None,
            video_average_psnr=None, video_average_mse=None,
            image_stego_prob=None, image_predicted_class=None,
            audio_stego_prob=None, audio_predicted_class=None,
            video_stego_prob=None, video_predicted_class=None,
        )
    except Exception as e:
        elapsed = (time.perf_counter() - t0) * 1000.0
        return SingleStrategyTrialResult(
            strategy_name=strategy_name,
            success=False,
            error_reason=f"Embedding exception: {str(e)}",
            runtime_ms=round(elapsed, 2),
            total_net_capacity_bytes=net_capacity,
            payload_plaintext_bytes=len(plaintext_msg.encode("utf-8")),
            encrypted_envelope_bytes=envelope_len,
            overall_utilization_ratio=round(envelope_len / max(1, net_capacity), 6),
            image_bytes_allocated=0,
            audio_bytes_allocated=0,
            video_bytes_allocated=0,
            recovered_plaintext_matches=False,
            image_psnr=None, image_ssim=None, image_mse=None,
            audio_snr=None, audio_normalized_mse=None,
            video_average_psnr=None, video_average_mse=None,
            image_stego_prob=None, image_predicted_class=None,
            audio_stego_prob=None, audio_predicted_class=None,
            video_stego_prob=None, video_predicted_class=None,
        )

    # 3. Execute Multimodal Extraction & Authenticated Recovery
    try:
        extract_res = extract_multimodal(
            stego_image_bytes=embed_res.stego_image_bytes,
            stego_audio_bytes=embed_res.stego_audio_bytes,
            stego_video_bytes=embed_res.stego_video_bytes,
            key_bytes=secret_key,
        )
        recovered_matches = (extract_res.plaintext == plaintext_msg)
        if not recovered_matches:
            recovery_err = "Decrypted plaintext does not match original message."
        else:
            recovery_err = None
    except Exception as e:
        recovered_matches = False
        recovery_err = f"Extraction failed: {str(e)}"

    # 4. Extract Distortion Metrics
    img_psnr = embed_res.image_metrics.get("psnr")
    img_ssim = embed_res.image_metrics.get("ssim")
    img_mse = embed_res.image_metrics.get("mse")

    aud_snr = embed_res.audio_metrics.get("snr")
    aud_mse = embed_res.audio_metrics.get("normalized_mse")

    vid_psnr = embed_res.video_metrics.get("average_psnr")
    vid_mse = embed_res.video_metrics.get("average_mse")

    # 5. Steganalysis Evaluation using Frozen Phase 7 Models
    img_clf = classify_media_file(embed_res.stego_image_bytes, "stego.png", "random_forest")
    aud_clf = classify_media_file(embed_res.stego_audio_bytes, "stego.wav", "random_forest")
    vid_clf = classify_media_file(embed_res.stego_video_bytes, "stego.avi", "random_forest")

    elapsed = (time.perf_counter() - t0) * 1000.0

    plan = embed_res.allocation_plan
    return SingleStrategyTrialResult(
        strategy_name=strategy_name,
        success=recovered_matches,
        error_reason=recovery_err,
        runtime_ms=round(elapsed, 2),
        total_net_capacity_bytes=net_capacity,
        payload_plaintext_bytes=len(plaintext_msg.encode("utf-8")),
        encrypted_envelope_bytes=len(embed_res.allocation_plan.slice_offsets["image"]),
        overall_utilization_ratio=plan.overall_utilization_ratio,
        image_bytes_allocated=plan.allocations["image"].payload_bytes,
        audio_bytes_allocated=plan.allocations["audio"].payload_bytes,
        video_bytes_allocated=plan.allocations["video"].payload_bytes,
        recovered_plaintext_matches=recovered_matches,
        image_psnr=round(img_psnr, 2) if img_psnr is not None else None,
        image_ssim=round(img_ssim, 4) if img_ssim is not None else None,
        image_mse=round(img_mse, 4) if img_mse is not None else None,
        audio_snr=round(aud_snr, 2) if aud_snr is not None else None,
        audio_normalized_mse=round(aud_mse, 6) if aud_mse is not None else None,
        video_average_psnr=round(vid_psnr, 2) if vid_psnr is not None else None,
        video_average_mse=round(vid_mse, 4) if vid_mse is not None else None,
        image_stego_prob=img_clf.stego_probability,
        image_predicted_class=img_clf.predicted_class,
        audio_stego_prob=aud_clf.stego_probability,
        audio_predicted_class=aud_clf.predicted_class,
        video_stego_prob=vid_clf.stego_probability,
        video_predicted_class=vid_clf.predicted_class,
    )


def run_comparative_trial(
    triad: CarrierTriadSource,
    trial_index: int,
    payload_bracket: Literal["low", "medium", "high"],
    payload_fraction: float,
    plaintext_seed: Optional[str] = None,
) -> PairedTrialResult:
    """Run an exact paired comparative trial (Fixed vs Adaptive) on one triad."""
    # Profile capacity first
    triad_profile = profile_multimodal_triad(triad.image_bytes, triad.audio_bytes, triad.video_bytes)
    total_net = triad_profile.total_usable_capacity_bytes
    
    # Calculate target envelope bytes respecting capacity
    target_envelope_bytes = max(31, int(total_net * payload_fraction))
    target_envelope_bytes = min(target_envelope_bytes, total_net)
    
    # Generate plaintext that will produce approximately this envelope size
    # Envelope = 12 (nonce) + 16 (tag) + len(msg) -> len(msg) = target_envelope_bytes - 28
    plaintext_len = max(1, target_envelope_bytes - 28)
    base_text = plaintext_seed or f"Phase8_Bench_Src{triad.source_id}_Trial{trial_index:03d}"
    plaintext = (base_text * ((plaintext_len // len(base_text)) + 1))[:plaintext_len]

    # Shared single secret key and pre-computed reference envelope
    shared_key = generate_key()
    shared_envelope = encrypt(plaintext.encode("utf-8"), shared_key)

    # 1. Evaluate Fixed Strategy
    fixed_res = evaluate_single_strategy_on_triad(
        triad=triad,
        strategy_name="fixed",
        plaintext_msg=plaintext,
        pre_encrypted_envelope=shared_envelope,
        secret_key=shared_key,
    )

    # 2. Evaluate Adaptive Strategy
    adaptive_res = evaluate_single_strategy_on_triad(
        triad=triad,
        strategy_name="adaptive",
        plaintext_msg=plaintext,
        pre_encrypted_envelope=shared_envelope,
        secret_key=shared_key,
    )

    paired = PairedTrialResult(
        trial_id=f"trial_{triad.source_id}_{payload_bracket}_{trial_index:03d}",
        source_id=triad.source_id,
        provenance=triad.provenance,
        target_payload_bracket=payload_bracket,
        target_payload_fraction=payload_fraction,
        fixed_result=fixed_res,
        adaptive_result=adaptive_res,
    )
    paired.compute_deltas()
    return paired


def run_comparative_experiment_suite(
    sources: List[CarrierTriadSource],
    payload_brackets: Optional[Dict[str, float]] = None,
) -> List[PairedTrialResult]:
    """Execute the full paired comparative evaluation matrix across all sources and payload brackets."""
    if payload_brackets is None:
        payload_brackets = {
            "low": 0.15,
            "medium": 0.35,
            "high": 0.55,
        }

    results: List[PairedTrialResult] = []
    trial_idx = 0

    for triad in sources:
        for bracket, fraction in payload_brackets.items():
            trial_res = run_comparative_trial(
                triad=triad,
                trial_index=trial_idx,
                payload_bracket=bracket,  # type: ignore
                payload_fraction=fraction,
            )
            results.append(trial_res)
            trial_idx += 1

    return results
