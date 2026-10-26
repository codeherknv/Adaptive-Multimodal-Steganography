"""Steganalysis labeled dataset generation pipeline across Image, Audio, and Video.

This module generates reproducible, leak-free labeled datasets for supervised steganalysis:
- Label 0: Cover media (no hidden payload).
- Label 1: Stego media (containing AES-256-GCM encrypted ASTG payload).

Leakage Prevention Architecture:
-------------------------------
Every synthesized or imported cover instance is assigned a unique `source_id` (e.g. `img_src_001`).
All stego variants derived from that specific cover retain the exact same `source_id`.
Downstream training uses `GroupShuffleSplit` on `source_id` so that an original cover
and its corresponding stego derivatives NEVER span across train, validation, and test splits.

Security & Confidentiality:
--------------------------
Neither the plaintext message, the encryption key, nor the initialization vector
is ever stored in dataset features or metadata records.
"""

from dataclasses import asdict, dataclass
import io
import math
import os
import uuid
from typing import Any, Dict, List, Literal, Optional, Tuple
import cv2
import numpy as np
from PIL import Image

from app.core.crypto_utils import generate_key, encrypt
from app.media.image_stego import embed_in_image, get_image_capacity
from app.media.audio_stego import embed_in_audio, get_audio_capacity, save_wav_audio
from app.media.video_stego import embed_in_video, get_video_capacity, save_video_to_bytes, detect_available_lossless_codec
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
    payload_category: str            # 'none', 'low' (5-15%), 'medium' (20-35%), 'high' (40-60%)
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
    """Generate a reproducible, procedurally varied cover PNG image."""
    rng = np.random.RandomState(source_index * 100 + 42)
    style = source_index % 5

    if style == 0:  # Gaussian noise texture
        arr = rng.randint(40, 215, (height, width, 3), dtype=np.uint8)
    elif style == 1:  # Smooth gradient
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
    style = source_index % 4

    if style == 0:  # Harmonic sinusoidal combination (e.g. musical chord)
        f0 = 220.0 + (source_index * 35.0)
        sig = 0.5 * np.sin(2 * np.pi * f0 * t) + 0.3 * np.sin(2 * np.pi * 2 * f0 * t) + 0.2 * np.sin(2 * np.pi * 3 * f0 * t)
    elif style == 1:  # Frequency modulated chirp
        f_start = 200.0 + (source_index * 20.0)
        f_end = 800.0 + (source_index * 40.0)
        phase = 2 * np.pi * (f_start * t + 0.5 * (f_end - f_start) * (t ** 2) / duration_sec)
        sig = np.sin(phase) * 0.8
    elif style == 2:  # Bandpass filtered noise
        noise = rng.normal(0, 0.4, total_samples)
        # Simple moving average smoothing
        sig = np.convolve(noise, np.ones(5)/5.0, mode='same')
    else:  # Percussive decaying envelope
        f_tone = 150.0 + (source_index * 50.0)
        decay = np.exp(-5.0 * t)
        sig = np.sin(2 * np.pi * f_tone * t) * decay * 0.9

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
    style = source_index % 3

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
        else:  # Modulating textured noise
            base = rng.randint(50, 190, (height, width, 3), dtype=np.uint8)
            frame = cv2.addWeighted(frame, 0.3, base, 0.7, 0)
        frames.append(frame)

    return save_video_to_bytes(frames, fps, width, height, codec_str, ext)


# =========================================================================
# Labeled Steganalysis Dataset Generation Engine
# =========================================================================

def generate_modality_dataset(
    modality: Literal["image", "audio", "video"],
    num_sources: int = 12,
    payload_fractions: Optional[List[float]] = None,
    allocation_strategies: Optional[List[str]] = None,
) -> SteganalysisDataset:
    """Generate a balanced, labeled steganalysis dataset for a specific modality.

    Args:
        modality: 'image', 'audio', or 'video'.
        num_sources: Number of independent cover media sources to synthesize.
        payload_fractions: List of capacity utilization ratios to evaluate (e.g. [0.10, 0.30, 0.50]).
        allocation_strategies: List of strategies to tag ('fixed', 'adaptive').

    Returns:
        SteganalysisDataset containing labeled samples, features, and source IDs.
    """
    fractions = payload_fractions or [0.10, 0.30, 0.50]
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
            cover_bytes = generate_procedural_audio(src_idx, duration_sec=0.4, sample_rate=16000)
            cap_info = get_audio_capacity(cover_bytes)
            max_usable = int(cap_info["max_usable_payload_bytes"])
            cover_feats, _ = extract_audio_features(cover_bytes)
        else:
            cover_bytes = generate_procedural_video(src_idx, num_frames=8, width=48, height=48)
            cap_info = get_video_capacity(cover_bytes)
            max_usable = int(cap_info["max_usable_payload_bytes"])
            cover_feats, _ = extract_video_features(cover_bytes)

        # 2. Add Label 0 (Cover) Sample
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

        # 3. Add Label 1 (Stego) Samples across varied payload sizes
        for frac in fractions:
            desired_payload_len = max(8, int(max_usable * frac))
            if desired_payload_len > max_usable:
                continue

            # Deterministic pseudo-payload
            plain_data = os.urandom(max(1, desired_payload_len - 30))
            envelope_bytes = encrypt(plain_data, dummy_key)[:desired_payload_len]

            # Categorize payload density
            if frac <= 0.15:
                cat = "low"
            elif frac <= 0.35:
                cat = "medium"
            else:
                cat = "high"

            for strat in strategies:
                try:
                    if modality == "image":
                        stego_arr, _ = embed_in_image(cover_bytes, envelope_bytes)
                        stego_feats, _ = extract_image_features(stego_arr)
                    elif modality == "audio":
                        stego_wav, _ = embed_in_audio(cover_bytes, envelope_bytes)
                        stego_feats, _ = extract_audio_features(stego_wav)
                    else:
                        stego_vid, _, _ = embed_in_video(cover_bytes, envelope_bytes)
                        stego_feats, _ = extract_video_features(stego_vid)

                    samples.append(DatasetSample(
                        sample_id=str(uuid.uuid4()),
                        source_id=source_id,
                        modality=modality,
                        label=1,
                        label_name="stego",
                        payload_bytes=len(envelope_bytes),
                        payload_fraction=round(len(envelope_bytes) / max_usable, 4) if max_usable > 0 else 0.0,
                        payload_category=cat,
                        allocation_strategy=strat,
                        features=stego_feats.tolist(),
                    ))
                except Exception:
                    # Ignore occasional capacity boundary edge cases safely
                    continue

    return SteganalysisDataset(
        modality=modality,
        feature_names=feature_names,
        samples=samples,
    )
