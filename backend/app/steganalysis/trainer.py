"""Steganalysis baseline model training and detectability evaluation pipeline.

This module trains lightweight, explainable baseline machine learning classifiers
(Random Forest and Logistic Regression) to detect LSB steganographic embedding across
Image, Audio, and Video media.

Leakage Prevention Guarantees:
-----------------------------
1. Source-Grouped Partitioning:
   Splits dataset into train and test subsets using GroupShuffleSplit based on `source_id`.
   A cover media source and ALL its corresponding stego variants are strictly quarantined
   to the same partition (never split across train and test).
2. Isolated Preprocessing:
   StandardScaler is fitted ONLY on the training split (scaler.fit(X_train)) and then
   applied to transform test samples (scaler.transform(X_test)).
3. Seeded Reproducibility:
   Random states (random_state=42) are pinned across data shuffling and model estimation.

Scientific & Integrity Notice:
-----------------------------
1. High accuracy or low detectability on a small procedural dataset is illustrative.
   Real-world steganalyzers require tens of thousands of natural camera/microphone captures.
2. An ML detector outputting 'Cover' (label 0) is an empirical statistical prediction;
   it is NOT mathematical proof of the absence of hidden data.
3. Media distortion metrics (PSNR, SSIM, SNR) are strictly separated from detectability
   metrics (Accuracy, Recall, ROC-AUC). High perceptual quality does NOT imply undetectability.
"""

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import os
from typing import Any, Dict, List, Literal, Optional, Tuple
import joblib
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import GroupShuffleSplit
from sklearn.preprocessing import StandardScaler

from app.steganalysis.dataset_generator import SteganalysisDataset, DatasetSample

DEFAULT_MODELS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "outputs", "models"))


@dataclass(frozen=True)
class EvaluationMetrics:
    """Comprehensive performance metrics for a trained steganalysis model."""
    accuracy: float
    precision: float
    recall: float
    f1_score: float
    roc_auc: Optional[float]
    true_positives: int
    true_negatives: int
    false_positives: int
    false_negatives: int
    total_samples: int
    cover_count: int
    stego_count: int
    by_payload_category: Dict[str, Dict[str, float]]
    by_allocation_strategy: Dict[str, Dict[str, float]]
    limitations_note: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class TrainedSteganalyzer:
    """Encapsulates a fitted pipeline (scaler + classifier) and evaluation metrics."""
    modality: str
    model_type: str
    scaler: StandardScaler
    classifier: Any
    feature_names: List[str]
    training_metrics: EvaluationMetrics
    test_metrics: EvaluationMetrics
    trained_at: str
    train_sources: List[str]
    test_sources: List[str]

    def predict(self, feature_vector: np.ndarray) -> Tuple[int, float]:
        """Predict class and stego probability for a single sample's feature vector.

        Returns:
            Tuple of (predicted_label: 0 or 1, stego_probability: 0.0 to 1.0).
        """
        feats_2d = feature_vector.reshape(1, -1)
        feats_scaled = self.scaler.transform(feats_2d)
        pred_label = int(self.classifier.predict(feats_scaled)[0])

        if hasattr(self.classifier, "predict_proba"):
            probs = self.classifier.predict_proba(feats_scaled)[0]
            stego_prob = float(probs[1]) if len(probs) > 1 else float(pred_label)
        else:
            stego_prob = float(pred_label)

        return pred_label, round(stego_prob, 4)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "modality": self.modality,
            "model_type": self.model_type,
            "feature_names": self.feature_names,
            "trained_at": self.trained_at,
            "train_sources_count": len(self.train_sources),
            "test_sources_count": len(self.test_sources),
            "test_metrics": self.test_metrics.to_dict(),
        }


def compute_metrics(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    y_prob: Optional[np.ndarray],
    test_samples: List[DatasetSample],
) -> EvaluationMetrics:
    """Calculate comprehensive detection metrics including category and strategy breakdowns."""
    acc = float(accuracy_score(y_true, y_pred))
    prec = float(precision_score(y_true, y_pred, zero_division=0))
    rec = float(recall_score(y_true, y_pred, zero_division=0))
    f1 = float(f1_score(y_true, y_pred, zero_division=0))

    roc = None
    if y_prob is not None and len(np.unique(y_true)) > 1:
        try:
            roc = float(roc_auc_score(y_true, y_prob))
        except Exception:
            roc = None

    cm = confusion_matrix(y_true, y_pred, labels=[0, 1])
    tn, fp, fn, tp = int(cm[0, 0]), int(cm[0, 1]), int(cm[1, 0]), int(cm[1, 1])

    # Category breakdown (Low, Medium, High payload)
    by_cat: Dict[str, Dict[str, float]] = {}
    for cat in ["low", "medium", "high"]:
        indices = [i for i, s in enumerate(test_samples) if s.label == 1 and s.payload_category == cat]
        if indices:
            cat_true = y_true[indices]
            cat_pred = y_pred[indices]
            # Stego detection recall on this specific payload size
            det_rate = float(np.mean(cat_pred == 1))
            by_cat[cat] = {
                "sample_count": len(indices),
                "stego_detection_rate": round(det_rate, 4),
            }

    # Allocation strategy breakdown under matched conditions (Fixed vs Adaptive)
    by_strat: Dict[str, Dict[str, float]] = {}
    for strat in ["fixed", "adaptive"]:
        indices = [i for i, s in enumerate(test_samples) if s.label == 1 and s.allocation_strategy == strat]
        if indices:
            strat_pred = y_pred[indices]
            det_rate = float(np.mean(strat_pred == 1))
            by_strat[strat] = {
                "sample_count": len(indices),
                "stego_detection_rate": round(det_rate, 4),
            }

    limitations = (
        "Limitations notice: Baseline evaluation conducted on procedural media. Results depend on sample size, "
        "media variance, and payload density. Model outputs indicate statistical probability, "
        "not deterministic proof of presence or absence."
    )

    return EvaluationMetrics(
        accuracy=round(acc, 4),
        precision=round(prec, 4),
        recall=round(rec, 4),
        f1_score=round(f1, 4),
        roc_auc=round(roc, 4) if roc is not None else None,
        true_positives=tp,
        true_negatives=tn,
        false_positives=fp,
        false_negatives=fn,
        total_samples=len(y_true),
        cover_count=int(np.sum(y_true == 0)),
        stego_count=int(np.sum(y_true == 1)),
        by_payload_category=by_cat,
        by_allocation_strategy=by_strat,
        limitations_note=limitations,
    )


def train_steganalyzer(
    dataset: SteganalysisDataset,
    model_type: Literal["random_forest", "logistic_regression"] = "random_forest",
    test_size: float = 0.25,
    random_state: int = 42,
    models_dir: Optional[str] = None,
) -> TrainedSteganalyzer:
    """Train a leak-free baseline steganalyzer using GroupShuffleSplit on source IDs.

    Args:
        dataset: SteganalysisDataset containing labeled samples and source_ids.
        model_type: 'random_forest' or 'logistic_regression'.
        test_size: Fraction of source groups reserved for held-out evaluation.
        random_state: Fixed random seed for split and model estimation.
        models_dir: Optional directory to persist fitted model bundle (.joblib).

    Returns:
        Fitted and evaluated TrainedSteganalyzer instance.
    """
    X, y, groups = dataset.get_feature_matrix_and_labels()
    unique_sources = np.unique(groups)

    if len(unique_sources) < 4:
        raise ValueError(
            f"Dataset must contain at least 4 independent source media groups for valid splitting; got {len(unique_sources)}."
        )

    # 1. Zero-Leakage Group Partitioning
    gss = GroupShuffleSplit(n_splits=1, test_size=test_size, random_state=random_state)
    train_idx, test_idx = next(gss.split(X, y, groups=groups))

    X_train, y_train = X[train_idx], y[train_idx]
    X_test, y_test = X[test_idx], y[test_idx]

    train_samples = [dataset.samples[i] for i in train_idx]
    test_samples = [dataset.samples[i] for i in test_idx]

    train_sources = sorted(list(set(groups[i] for i in train_idx)))
    test_sources = sorted(list(set(groups[i] for i in test_idx)))

    # Double check: zero group overlap
    overlap = set(train_sources).intersection(set(test_sources))
    assert len(overlap) == 0, f"Critical leakage error: sources {overlap} exist in both train and test splits!"

    # 2. Preprocessing: Fit scaler ONLY on training data
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)

    # 3. Model Estimation
    if model_type == "random_forest":
        clf = RandomForestClassifier(
            n_estimators=100,
            max_depth=6,
            min_samples_split=2,
            random_state=random_state,
        )
    elif model_type == "logistic_regression":
        clf = LogisticRegression(
            max_iter=1000,
            C=1.0,
            random_state=random_state,
        )
    else:
        raise ValueError(f"Unsupported model type '{model_type}'. Choose 'random_forest' or 'logistic_regression'.")

    clf.fit(X_train_scaled, y_train)

    # 4. In-Sample Training Evaluation
    y_train_pred = clf.predict(X_train_scaled)
    y_train_prob = clf.predict_proba(X_train_scaled)[:, 1] if hasattr(clf, "predict_proba") else None
    train_metrics = compute_metrics(y_train, y_train_pred, y_train_prob, train_samples)

    # 5. Out-of-Sample Held-Out Test Evaluation
    y_test_pred = clf.predict(X_test_scaled)
    y_test_prob = clf.predict_proba(X_test_scaled)[:, 1] if hasattr(clf, "predict_proba") else None
    test_metrics = compute_metrics(y_test, y_test_pred, y_test_prob, test_samples)

    trained_at = datetime.now(timezone.utc).isoformat()
    analyzer = TrainedSteganalyzer(
        modality=dataset.modality,
        model_type=model_type,
        scaler=scaler,
        classifier=clf,
        feature_names=dataset.feature_names,
        training_metrics=train_metrics,
        test_metrics=test_metrics,
        trained_at=trained_at,
        train_sources=train_sources,
        test_sources=test_sources,
    )

    # 6. Save model to disk if directory specified or default exists
    target_dir = models_dir or DEFAULT_MODELS_DIR
    os.makedirs(target_dir, exist_ok=True)
    model_filename = f"stego_{dataset.modality}_{model_type}.joblib"
    model_path = os.path.join(target_dir, model_filename)
    joblib.dump(analyzer, model_path)

    return analyzer


def load_steganalyzer(
    modality: Literal["image", "audio", "video"],
    model_type: Literal["random_forest", "logistic_regression"] = "random_forest",
    models_dir: Optional[str] = None,
) -> Optional[TrainedSteganalyzer]:
    """Load a trained steganalyzer model from disk if present."""
    target_dir = models_dir or DEFAULT_MODELS_DIR
    model_filename = f"stego_{modality}_{model_type}.joblib"
    model_path = os.path.join(target_dir, model_filename)

    if not os.path.exists(model_path):
        return None

    try:
        analyzer = joblib.load(model_path)
        return analyzer if isinstance(analyzer, TrainedSteganalyzer) else None
    except Exception:
        return None
