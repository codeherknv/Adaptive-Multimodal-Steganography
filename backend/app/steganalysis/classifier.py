"""Single-file live inference and steganalysis classification.

This module inspects an uploaded media file, extracts statistical artifact features,
and executes inference using the trained baseline steganalyzer.

Safety & Integrity:
------------------
The classification output is an empirical statistical prediction. The module includes
an explicit disclaimer reminding researchers that ML detectors output probabilities,
not mathematical or forensic proof of the presence or absence of steganography.
Outputs are explicitly labeled as calibrated (e.g. Platt sigmoid) or uncalibrated scores.
"""

from dataclasses import asdict, dataclass
import os
from typing import Any, Dict, List, Literal, Optional, Tuple
import numpy as np

from app.steganalysis.features import (
    extract_image_features,
    extract_audio_features,
    extract_video_features,
    FeatureExtractionError,
)
from app.steganalysis.trainer import load_steganalyzer, train_steganalyzer, TrainedSteganalyzer
from app.steganalysis.dataset_generator import generate_modality_dataset


@dataclass(frozen=True)
class ClassificationResult:
    """Consolidated prediction and statistical explanation for a single inspected media file."""
    modality: str
    filename: str
    predicted_label: int             # 0 = Cover, 1 = Stego
    predicted_class: str             # 'Cover' or 'Stego'
    stego_probability: float         # 0.0 to 1.0 confidence score
    confidence_percentage: float     # 0.0 to 100.0%
    model_type: str                  # 'random_forest' or 'logistic_regression'
    feature_values: Dict[str, float] # Name-to-value map of extracted statistical features
    disclaimer: str
    is_calibrated: bool = False
    calibration_method: str = "none"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def detect_media_modality(file_bytes: bytes, filename: str = "") -> str:
    """Infer media modality (image, audio, or video) from filename or magic bytes.

    Args:
        file_bytes: Raw file header bytes.
        filename: Optional filename hint.

    Returns:
        'image', 'audio', or 'video'.

    Raises:
        FeatureExtractionError: If file format cannot be recognized.
    """
    fn_lower = filename.lower()

    if fn_lower.endswith((".png", ".jpg", ".jpeg", ".webp")) or file_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image"
    if fn_lower.endswith((".wav", ".wave")) or (file_bytes.startswith(b"RIFF") and b"WAVE" in file_bytes[:16]):
        return "audio"
    if fn_lower.endswith((".avi", ".mkv", ".mp4")) or (file_bytes.startswith(b"RIFF") and b"AVI " in file_bytes[:16]):
        return "video"

    # Fallback inspection
    if file_bytes.startswith(b"RIFF"):
        if b"WAVE" in file_bytes[:32]: return "audio"
        if b"AVI " in file_bytes[:32]: return "video"

    raise FeatureExtractionError(
        f"Unable to recognize media format for '{filename}'. Supported carriers: PNG, WAV, AVI."
    )


def classify_media_file(
    file_bytes: bytes,
    filename: str = "sample",
    model_type: Literal["random_forest", "logistic_regression"] = "random_forest",
) -> ClassificationResult:
    """Classify a single uploaded media file as Cover or Stego.

    Args:
        file_bytes: Raw file bytes.
        filename: Uploaded filename for modality detection.
        model_type: Classifier architecture to use.

    Returns:
        ClassificationResult with predicted class, stego probability, and feature values.

    Raises:
        FeatureExtractionError: If media cannot be parsed or analyzed.
    """
    modality = detect_media_modality(file_bytes, filename)

    # 1. Extract statistical artifact features
    if modality == "image":
        feats, names = extract_image_features(file_bytes)
    elif modality == "audio":
        feats, names = extract_audio_features(file_bytes)
    else:
        feats, names = extract_video_features(file_bytes)

    # 2. Load trained model (or train default baseline on demand if not present)
    analyzer = load_steganalyzer(modality, model_type=model_type)
    if analyzer is None:
        # Generate lightweight default baseline dataset and train on demand
        default_ds = generate_modality_dataset(modality, num_sources=8)
        analyzer = train_steganalyzer(default_ds, model_type=model_type)

    # 3. Model Inference (uses internal probability calibration when available)
    pred_label, stego_prob = analyzer.predict(feats)
    pred_class = "Stego" if pred_label == 1 else "Cover"

    # Confidence relative to the predicted class
    conf_pct = round((stego_prob if pred_label == 1 else (1.0 - stego_prob)) * 100, 1)

    feats_dict = {
        name: round(float(val), 5) for name, val in zip(names, feats)
    }

    calib_desc = f"calibrated via {analyzer.calibration_method}" if analyzer.is_calibrated else "uncalibrated baseline score"
    disclaimer = (
        f"Notice: This prediction is an empirical statistical estimate from a baseline machine-learning "
        f"detector ({calib_desc}). Model scores reflect learned artifact patterns on training distributions; "
        f"a prediction of 'Cover' does not prove absence of hidden data, nor does 'Stego' "
        f"provide cryptographic proof of concealed communication."
    )

    return ClassificationResult(
        modality=modality,
        filename=filename,
        predicted_label=pred_label,
        predicted_class=pred_class,
        stego_probability=round(stego_prob, 4),
        confidence_percentage=conf_pct,
        model_type=model_type,
        feature_values=feats_dict,
        disclaimer=disclaimer,
        is_calibrated=analyzer.is_calibrated,
        calibration_method=analyzer.calibration_method,
    )
