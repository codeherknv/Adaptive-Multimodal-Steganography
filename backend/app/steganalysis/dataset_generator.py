"""Steganalysis labeled dataset generation pipeline across Image, Audio, and Video.

This module generates reproducible, leak-free, strictly 1:1 class-balanced labeled datasets
for supervised steganalysis:
- Label 0: Original cover media (no hidden payload).
- Label 1: Stego media containing a fully authenticated AES-256-GCM encrypted envelope.

Leakage Prevention Architecture:
-------------------------------
Every synthesized or imported cover instance is assigned a unique `source_id` (e.g. `img_src_001`).
All stego variants derived from that specific cover retain the exact same `source_id`.
Downstream training uses `GroupShuffleSplit` on `source_id` so that an original cover
and its corresponding stego derivatives NEVER span across train, validation, and test splits.

Cryptographic & Embedding Validity:
-----------------------------------
- Envelopes are NEVER truncated or sliced. Every stego sample contains a complete,
  valid AES-256-GCM envelope with full 14-byte header and 16-byte GHASH tag.
- Round-trip extraction and authenticated decryption are verified for every generated sample.
- Zero secret leakage: neither plaintext, symmetric keys, nor nonces are stored in features or records.
"""

from dataclasses import asdict, dataclass
import io
import os
import uuid
from typing import Any, Dict, List, Literal, Optional, Tuple
import cv2
import numpy as np
from PIL import Image

from app.core.crypto_utils import generate_key, encrypt, decrypt
from app.media.image_stego import embed_in_image, extract_from_image, get_image_capacity
from app.media.audio_stego import embed_in_audio, extract_from_audio, get_audio_capacity, save_wav_audio
from app.media.video_stego import (
    embed_in_video,
    extract_from_video,
    get_video_capacity,
    save_video_to_bytes,
    detect_available_lossless_codec
)
from app.allocation.profiler import profile_multimodal_triad
from app.allocation.allocator import get_allocation_strategy
from app.allocation.engine import embed_multimodal, extract_multimodal
from app.steganalysis.features import (
    extract_image_features,
    extract_audio_features,
    extract_video_features,
    IMAGE_FEATURE_NAMES,
    AUDIO_FEATURE_NAMES,
    VIDEO_FEATURE_NAMES,
)


@dataclass(frozen=True)
class DatasetSample:
    """A single labeled sample record in the steganalysis benchmark dataset."""
    sample_id: str
    source_id: str                   # Group identifier for zero-leakage splitting
    modality: str                    # 'image', 'audio', or 'video'
    label: int                       # 0 = Cover, 1 = Stego
    label_name: str                  # 'cover' or 'stego'
    payload_bytes: int
    payload_fraction: float          # Embedded bytes / usable capacity
    payload_category: str            # 'none', 'low' (5-20%), 'medium' (21-40%), 'high' (>40%)
    allocation_strategy: str         # 'none', 'fixed', or 'adaptive'
    features: List[float]            # Extracted numerical feature vector

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class SteganalysisDataset:
    """Container for a collection of labeled steganalysis samples."""
    modality: str
    feature_names: List[str]
    samples: List[DatasetSample]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "modality": self.modality,
            "feature_names": self.feature_names,
            "total_samples": len(self.samples),
            "cover_count": sum(1 for s in self.samples if s.label == 0),
            "stego_count": sum(1 for s in self.samples if s.label == 1),
            "sources_count": len(set(s.source_id for s in self.samples)),
            "samples": [s.to_dict() for s in self.samples],
        }

    def get_feature_matrix_and_labels(self) -> Tuple[np.ndarray, np.ndarray, List[str]]:
        """Extract X (N x D), y (N,), and group source_ids for scikit-learn models."""
        X = np.array([s.features for s in self.samples], dtype=np.float64)
        y = np.array([s.label for s in self.samples], dtype=np.int32)
        groups = [s.source_id for s in self.samples]
        return X, y, groups


# =========================================================================
# Diverse Cover Media Synthesizers (Reproducible Seeds)
# =========================================================================

def generate_procedural_image(
    source_index: int,
    width: int = 64,
    height: int = 64
) -> bytes:
    """Generate a reproducible, procedurally varied cover PNG image across diverse styles."""
    rng = np.random.RandomState(source_index * 100 + 42)
    style = source_index % 6

    if style == 0:  # Gaussian noise texture
        arr = rng.randint(40, 215, (height, width, 3), dtype=np.uint8)
    elif style == 1:  # Smooth gradient across diagonals
        x = np.linspace(30, 220, width, dtype=np.uint8)
        arr = np.tile(x, (height, 1))
        arr = np.stack([arr, arr.T, np.flipud(arr)], axis=-1)
    elif style == 2:  # Sinusoidal interference pattern
        x = np.linspace(0, 4 * np.pi, width)
        y = np.linspace(0, 4 * np.pi, height)
        xx, yy = np.meshgrid(x, y)
        pattern = ((np.sin(xx) * np.cos(yy) + 1.0) * 110 + 20).astype(np.uint8)
        arr = np.stack([pattern, np.rot90(pattern), np.flipud(pattern)], axis=-1)
    elif style == 3:  # Geometric checkerboard / blocks
        arr = np.zeros((height, width, 3), dtype=np.uint8)
        block = max(4, width // 8)
        for i in range(0, height, block):
            for j in range(0, width, block):
                val = rng.randint(60, 200, size=3, dtype=np.uint8)
                arr[i:i+block, j:j+block] = val
    elif style == 4:  # Naturalistic Perlin-like smoothed noise
        base = rng.normal(128, 28, (height, width)).clip(10, 245).astype(np.uint8)
        smoothed = cv2.GaussianBlur(base, (5, 5), 1.5)
        arr = np.stack([smoothed, np.roll(smoothed, 3, axis=0), np.roll(smoothed, 3, axis=1)], axis=-1)
    else:  # High-frequency textured pattern
        base = rng.normal(128, 30, (height, width)).clip(0, 255).astype(np.uint8)
        arr = np.stack([base, np.roll(base, 2, axis=0), np.roll(base, 2, axis=1)], axis=-1)

    pil_img = Image.fromarray(arr, mode="RGB")
    buf = io.BytesIO()
    pil_img.save(buf, format="PNG")
    return buf.getvalue()


def generate_procedural_audio(
    source_index: int,
    duration_sec: float = 0.5,
    sample_rate: int = 16000
) -> bytes:
    """Generate a reproducible, procedurally varied cover PCM WAV audio file."""
    rng = np.random.RandomState(source_index * 100 + 77)
    total_samples = int(duration_sec * sample_rate)
    t = np.linspace(0, duration_sec, total_samples, endpoint=False)
    style = source_index % 5

    if style == 0:  # Harmonic musical chord
        f0 = 220.0 + (source_index * 35.0)
        sig = 0.5 * np.sin(2 * np.pi * f0 * t) + 0.3 * np.sin(2 * np.pi * 2 * f0 * t) + 0.2 * np.sin(2 * np.pi * 3 * f0 * t)
    elif style == 1:  # Frequency modulated chirp sweep
        f_start = 200.0 + (source_index * 20.0)
        f_end = 800.0 + (source_index * 40.0)
        phase = 2 * np.pi * (f_start * t + 0.5 * (f_end - f_start) * (t ** 2) / duration_sec)
        sig = np.sin(phase) * 0.8
    elif style == 2:  # Bandpass filtered smooth noise
        noise = rng.normal(0, 0.4, total_samples)
        sig = np.convolve(noise, np.ones(7)/7.0, mode='same')
    elif style == 3:  # Percussive decaying tone
        f_tone = 150.0 + (source_index * 50.0)
        decay = np.exp(-6.0 * t)
        sig = np.sin(2 * np.pi * f_tone * t) * decay * 0.9
    else:  # Multi-tone superposition with amplitude modulation
        f1, f2 = 300.0 + source_index * 15, 600.0 + source_index * 25
        am = 0.5 * (1.0 + np.sin(2 * np.pi * 5.0 * t))
        sig = am * (0.6 * np.sin(2 * np.pi * f1 * t) + 0.4 * np.cos(2 * np.pi * f2 * t))

    int_samples = (np.clip(sig, -0.99, 0.99) * 32000).astype(np.int16)
    params = {
        "num_channels": 1,
        "sample_width": 2,
        "sample_rate": sample_rate,
    }
    return save_wav_audio(int_samples, params)


def generate_procedural_video(
    source_index: int,
    num_frames: int = 10,
    width: int = 48,
    height: int = 48,
    fps: float = 25.0
) -> bytes:
    """Generate a reproducible, procedurally varied cover lossless AVI video."""
    codec_str, ext = detect_available_lossless_codec()
    rng = np.random.RandomState(source_index * 100 + 13)
    style = source_index % 4

    frames = []
    for f_idx in range(num_frames):
        frame = np.full((height, width, 3), 80, dtype=np.uint8)
        if style == 0:  # Moving high-contrast square
            x = int((f_idx * 3) % (width - 12))
            y = int((f_idx * 2) % (height - 12))
            frame[y:y+12, x:x+12] = [220, 180, 50]
        elif style == 1:  # Expanding concentric circles
            center = (width // 2, height // 2)
            radius = int((f_idx * 2 + 4) % (min(width, height) // 2))
            cv2.circle(frame, center, radius, (50, 200, 220), -1)
        elif style == 2:  # Moving horizontal color bar
            y_bar = int((f_idx * 4) % (height - 10))
            frame[y_bar:y_bar+10, :] = [40, 200, 120]
        else:  # Modulating textured noise
            base = rng.randint(50, 190, (height, width, 3), dtype=np.uint8)
            frame = cv2.addWeighted(frame, 0.3, base, 0.7, 0)

        # Add subtle sensor noise (0, 1, 2) to eliminate the synthetic all-even integer shortcut
        # and provide realistic LSB variation matching physical camera sensor captures.
        sensor_noise = rng.randint(0, 3, (height, width, 3), dtype=np.uint8)
        frame = np.clip(frame.astype(np.int16) + sensor_noise, 0, 255).astype(np.uint8)
        frames.append(frame)

    return save_video_to_bytes(frames, fps, width, height, fourcc_str=codec_str, ext=ext)


# =========================================================================
# Labeled Steganalysis Dataset Generation Engine (1:1 Class Balanced)
# =========================================================================

def generate_modality_dataset(
    modality: Literal["image", "audio", "video"],
    num_sources: int = 12,
    payload_fractions: Optional[List[float]] = None,
    allocation_strategies: Optional[List[str]] = None,
) -> SteganalysisDataset:
    """Generate a strictly 1:1 balanced, leak-free labeled steganalysis dataset.

    Design Principles:
    ------------------
    1. Exact 1:1 Class Balance:
       For every independent cover media source (Label 0), exactly ONE matched stego
       instance (Label 1) is generated from that same carrier.
       Total samples = 2 * num_sources (50% Cover, 50% Stego).
    2. Valid Cryptographic Envelopes:
       Calculates required plaintext size so that encrypt(plaintext, key) produces a
       100% valid, untruncated AES-256-GCM envelope with intact 16-byte authentication tag.
    3. Verification & Authenticity:
       Every stego carrier is immediately extracted and decrypted; samples that fail
       authentication or capacity limits are safely discarded.
    4. Zero Leakage:
       Source ID (e.g. 'image_src_001') is shared by both the cover and its matched stego,
       preventing cross-split leakage when using GroupShuffleSplit.

    Args:
        modality: 'image', 'audio', or 'video'.
        num_sources: Number of independent cover sources to synthesize.
        payload_fractions: Target capacity utilization ratios (default: [0.15, 0.35, 0.55]).
        allocation_strategies: Allocation strategy tags to alternate ('fixed', 'adaptive').

    Returns:
        SteganalysisDataset with exactly matched cover/stego pairs.
    """
    fractions = payload_fractions or [0.15, 0.35, 0.55]
    strategies = allocation_strategies or ["fixed", "adaptive"]

    samples: List[DatasetSample] = []
    dummy_key = generate_key()

    if modality == "image":
        feature_names = IMAGE_FEATURE_NAMES
    elif modality == "audio":
        feature_names = AUDIO_FEATURE_NAMES
    else:
        feature_names = VIDEO_FEATURE_NAMES

    for src_idx in range(num_sources):
        source_id = f"{modality}_src_{src_idx:03d}"

        # 1. Synthesize independent cover media
        if modality == "image":
            cover_bytes = generate_procedural_image(src_idx, width=64, height=64)
            cap_info = get_image_capacity(cover_bytes)
            max_usable = cap_info["max_usable_payload_bytes"]
            cover_feats, _ = extract_image_features(cover_bytes)
        elif modality == "audio":
            cover_bytes = generate_procedural_audio(src_idx, duration_sec=0.5, sample_rate=16000)
            cap_info = get_audio_capacity(cover_bytes)
            max_usable = int(cap_info["max_usable_payload_bytes"])
            cover_feats, _ = extract_audio_features(cover_bytes)
        else:
            cover_bytes = generate_procedural_video(src_idx, num_frames=10, width=48, height=48)
            cap_info = get_video_capacity(cover_bytes)
            max_usable = int(cap_info["max_usable_payload_bytes"])
            cover_feats, _ = extract_video_features(cover_bytes)

        if max_usable < 35:
            continue  # Insufficient capacity for minimal 31-byte envelope

        # 2. Select target payload fraction and strategy for this source (balanced round-robin)
        frac = fractions[src_idx % len(fractions)]
        strat = strategies[src_idx % len(strategies)]

        # Determine payload category
        if frac <= 0.20:
            cat = "low"
        elif frac <= 0.40:
            cat = "medium"
        else:
            cat = "high"

        # 3. Create a complete, valid AES-256-GCM envelope (header: 14 bytes, tag: 16 bytes = 30 bytes overhead)
        desired_env_len = max(31, min(max_usable, int(max_usable * frac)))
        plaintext_len = max(1, desired_env_len - 30)
        plaintext = os.urandom(plaintext_len)
        envelope_bytes = encrypt(plaintext, dummy_key)

        if len(envelope_bytes) > max_usable:
            continue

        # 4. Embed into carrier and verify round-trip integrity
        try:
            if modality == "image":
                stego_carrier, _ = embed_in_image(cover_bytes, envelope_bytes)
                extracted_env = extract_from_image(stego_carrier)
                stego_feats, _ = extract_image_features(stego_carrier)
            elif modality == "audio":
                stego_carrier, _ = embed_in_audio(cover_bytes, envelope_bytes)
                extracted_env = extract_from_audio(stego_carrier)
                stego_feats, _ = extract_audio_features(stego_carrier)
            else:
                stego_carrier, _, _ = embed_in_video(cover_bytes, envelope_bytes)
                extracted_env = extract_from_video(stego_carrier)
                stego_feats, _ = extract_video_features(stego_carrier)

            # Cryptographic authentication verification
            assert extracted_env == envelope_bytes, "Extracted envelope did not match embedded envelope!"
            decrypted_plain = decrypt(extracted_env, dummy_key)
            assert decrypted_plain == plaintext, "Decrypted plaintext did not authenticate!"

        except Exception:
            # Skip invalid carrier attempt safely
            continue

        # 5. Add Matched Pair (1 Cover + 1 Stego for this source)
        # Cover Sample (Label 0)
        samples.append(DatasetSample(
            sample_id=str(uuid.uuid4()),
            source_id=source_id,
            modality=modality,
            label=0,
            label_name="cover",
            payload_bytes=0,
            payload_fraction=0.0,
            payload_category="none",
            allocation_strategy="none",
            features=cover_feats.tolist(),
        ))

        # Stego Sample (Label 1)
        actual_frac = round(len(envelope_bytes) / max_usable, 4) if max_usable > 0 else 0.0
        samples.append(DatasetSample(
            sample_id=str(uuid.uuid4()),
            source_id=source_id,
            modality=modality,
            label=1,
            label_name="stego",
            payload_bytes=len(envelope_bytes),
            payload_fraction=actual_frac,
            payload_category=cat,
            allocation_strategy=strat,
            features=stego_feats.tolist(),
        ))

    return SteganalysisDataset(
        modality=modality,
        feature_names=feature_names,
        samples=samples,
    )


# =========================================================================
# Genuine Multimodal Allocation Comparison Pipeline
# =========================================================================

def generate_multimodal_allocation_comparison_dataset(
    num_triads: int = 8,
    message_length: int = 120,
) -> Dict[str, Any]:
    """Execute matched-condition empirical comparison between Fixed and Adaptive allocation.

    Unlike isolated single-carrier datasets, this calls the actual Phase 6 multimodal
    allocation engine across triads of (Image, Audio, Video) covers.

    Returns:
        Dictionary containing comparative allocation slices, extracted features,
        and carrier capacity distributions.
    """
    records = []

    for triad_idx in range(num_triads):
        triad_id = f"triad_src_{triad_idx:03d}"
        img_cover = generate_procedural_image(triad_idx, width=64, height=64)
        aud_cover = generate_procedural_audio(triad_idx, duration_sec=0.5, sample_rate=16000)
        vid_cover = generate_procedural_video(triad_idx, num_frames=10, width=48, height=48)

        # Profile all three carriers
        triad_profile = profile_multimodal_triad(img_cover, aud_cover, vid_cover)

        # Check total net capacity across the triad (accounting for 3 x 34 bytes framing overhead)
        net_cap = sum(max(0, p.max_usable_payload_bytes - 34) for p in [triad_profile.image, triad_profile.audio, triad_profile.video])
        if net_cap < message_length:
            continue

        try:
            # Execute genuine Fixed Allocation and full multimodal embedding/extraction
            dummy_key = generate_key()
            test_msg = f"Phase7MultimodalVerificationPayload_{triad_idx:03d}"

            fixed_res = embed_multimodal(
                message=test_msg,
                image_bytes=img_cover,
                audio_bytes=aud_cover,
                video_bytes=vid_cover,
                key_bytes=dummy_key,
                strategy_name="fixed"
            )
            fixed_ext = extract_multimodal(
                stego_image_bytes=fixed_res.stego_image_bytes,
                stego_audio_bytes=fixed_res.stego_audio_bytes,
                stego_video_bytes=fixed_res.stego_video_bytes,
                key_bytes=dummy_key
            )
            assert fixed_ext.plaintext == test_msg, "Fixed extraction failed authentication!"

            # Execute genuine Adaptive Allocation and full multimodal embedding/extraction
            adaptive_res = embed_multimodal(
                message=test_msg,
                image_bytes=img_cover,
                audio_bytes=aud_cover,
                video_bytes=vid_cover,
                key_bytes=dummy_key,
                strategy_name="adaptive"
            )
            adaptive_ext = extract_multimodal(
                stego_image_bytes=adaptive_res.stego_image_bytes,
                stego_audio_bytes=adaptive_res.stego_audio_bytes,
                stego_video_bytes=adaptive_res.stego_video_bytes,
                key_bytes=dummy_key
            )
            assert adaptive_ext.plaintext == test_msg, "Adaptive extraction failed authentication!"

            fixed_plan = fixed_res.allocation_plan
            adaptive_plan = adaptive_res.allocation_plan
        except Exception:
            continue

        # Extract features from covers
        img_cover_feats, _ = extract_image_features(img_cover)
        aud_cover_feats, _ = extract_audio_features(aud_cover)
        vid_cover_feats, _ = extract_video_features(vid_cover)

        records.append({
            "triad_id": triad_id,
            "message_length": len(test_msg),
            "total_net_capacity": net_cap,
            "both_authenticated": True,
            "fixed_allocation": {
                "image_bytes": fixed_plan.allocations["image"].payload_bytes,
                "audio_bytes": fixed_plan.allocations["audio"].payload_bytes,
                "video_bytes": fixed_plan.allocations["video"].payload_bytes,
            },
            "adaptive_allocation": {
                "image_bytes": adaptive_plan.allocations["image"].payload_bytes,
                "audio_bytes": adaptive_plan.allocations["audio"].payload_bytes,
                "video_bytes": adaptive_plan.allocations["video"].payload_bytes,
            },
            "fixed_distortion": {
                "image_psnr": fixed_res.image_metrics.get("psnr", 0.0),
                "audio_snr": fixed_res.audio_metrics.get("snr", 0.0),
                "video_psnr": fixed_res.video_metrics.get("psnr", 0.0),
            },
            "adaptive_distortion": {
                "image_psnr": adaptive_res.image_metrics.get("psnr", 0.0),
                "audio_snr": adaptive_res.audio_metrics.get("snr", 0.0),
                "video_psnr": adaptive_res.video_metrics.get("psnr", 0.0),
            },
            "cover_features": {
                "image": img_cover_feats.tolist(),
                "audio": aud_cover_feats.tolist(),
                "video": vid_cover_feats.tolist(),
            }
        })

    return {
        "num_triads_evaluated": len(records),
        "triads": records,
    }
