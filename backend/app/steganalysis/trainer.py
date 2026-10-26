"""Steganalysis baseline model training and detectability evaluation pipeline.

This module trains lightweight, explainable baseline machine learning classifiers
(Random Forest and Logistic Regression) to detect LSB steganographic embedding across
Image, Audio, and Video media.

Leakage Prevention & Scientific Guarantees:
------------------------------------------
1. Source-Grouped Partitioning:
   Splits dataset into train and test subsets using GroupShuffleSplit strictly based on `source_id`.
   A cover media source and ALL its corresponding stego variants are strictly quarantined
   to the same partition (never split across train and test).
2. Isolated Preprocessing & Calibration:
   - StandardScaler is fitted ONLY on the training split (scaler.fit(X_train)) and then
     applied to transform test samples (scaler.transform(X_test)).
   - Probability calibration (CalibratedClassifierCV) is fitted strictly inside the training data
     via internal cross-validation; the held-out test set is NEVER used for fitting or tuning.
3. Class Weighting & Balanced Evaluation:
   Estimators use class_weight='balanced' to prevent majority class dominance.
4. Probability Column Ordering:
   Positive class index is dynamically resolved from estimator.classes_ to prevent
   probability inversion.
"""

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import os
from typing import Any, Dict, List, Literal, Optional, Tuple
import joblib
import numpy as np
from sklearn.calibration import CalibratedClassifierCV
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
    is_calibrated: bool = False
    calibration_method: str = "none"

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
    calibrator: Optional[Any] = None
    is_calibrated: bool = False
    calibration_method: str = "none"

    def predict(self, feature_vector: np.ndarray) -> Tuple[int, float]:
        """Predict class and stego probability for a single sample's feature vector.

        Returns:
            Tuple of (predicted_label: 0 or 1, stego_probability: 0.0 to 1.0).
        """
        feats_2d = feature_vector.reshape(1, -1)
        feats_scaled = self.scaler.transform(feats_2d)

        active_model = self.calibrator if self.calibrator is not None else self.classifier

        # Safely resolve positive class column index from active model classes_
        if hasattr(active_model, "classes_"):
            classes_list = list(active_model.classes_)
            pos_idx = classes_list.index(1) if 1 in classes_list else -1
        else:
            pos_idx = 1

        if hasattr(active_model, "predict_proba") and pos_idx >= 0:
            probs = active_model.predict_proba(feats_scaled)[0]
            stego_prob = float(probs[pos_idx])
            pred_label = int(stego_prob >= 0.5)
        else:
            pred_label = int(active_model.predict(feats_scaled)[0])
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
            "is_calibrated": self.is_calibrated,
            "calibration_method": self.calibration_method,
            "test_metrics": self.test_metrics.to_dict(),
        }


def compute_metrics(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    y_prob: Optional[np.ndarray],
    test_samples: List[DatasetSample],
    is_calibrated: bool = False,
    calibration_method: str = "none",
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

    # Confusion matrix with strict label ordering: [0 = Cover, 1 = Stego]
    # Row 0: True 0 -> [TN at (0,0), FP at (0,1)]
    # Row 1: True 1 -> [FN at (1,0), TP at (1,1)]
    cm = confusion_matrix(y_true, y_pred, labels=[0, 1])
    tn, fp, fn, tp = int(cm[0, 0]), int(cm[0, 1]), int(cm[1, 0]), int(cm[1, 1])

    # Category breakdown (Low, Medium, High payload)
    by_cat: Dict[str, Dict[str, float]] = {}
    for cat in ["low", "medium", "high"]:
        indices = [i for i, s in enumerate(test_samples) if s.label == 1 and s.payload_category == cat]
        if indices:
            cat_pred = y_pred[indices]
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
        is_calibrated=is_calibrated,
        calibration_method=calibration_method,
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

    # 3. Model Estimation with class weighting
    if model_type == "random_forest":
        clf = RandomForestClassifier(
            n_estimators=100,
            max_depth=6,
            min_samples_split=2,
            class_weight="balanced",
            random_state=random_state,
        )
    elif model_type == "logistic_regression":
        clf = LogisticRegression(
            max_iter=1000,
            C=1.0,
            class_weight="balanced",
            random_state=random_state,
        )
    else:
        raise ValueError(f"Unsupported model type '{model_type}'. Choose 'random_forest' or 'logistic_regression'.")

    clf.fit(X_train_scaled, y_train)

    # 4. Probability Calibration (strictly on training split using internal CV)
    calibrator = None
    is_calibrated = False
    calib_method = "uncalibrated"

    counts_train = np.bincount(y_train, minlength=2)
    if min(counts_train) >= 3:
        try:
            cv_folds = min(3, int(min(counts_train)))
            calibrator = CalibratedClassifierCV(
                estimator=clf,
                method="sigmoid",
                cv=cv_folds
            )
            calibrator.fit(X_train_scaled, y_train)
            is_calibrated = True
            calib_method = f"platt_sigmoid_cv{cv_folds}"
        except Exception:
            calibrator = None
            is_calibrated = False
            calib_method = "uncalibrated"

    active_model = calibrator if is_calibrated else clf

    # Resolve positive class index safely
    if hasattr(active_model, "classes_"):
        classes_list = list(active_model.classes_)
        pos_idx = classes_list.index(1) if 1 in classes_list else 1
    else:
        pos_idx = 1

    # 5. In-Sample Training Evaluation
    if hasattr(active_model, "predict_proba"):
        y_train_prob = active_model.predict_proba(X_train_scaled)[:, pos_idx]
        y_train_pred = (y_train_prob >= 0.5).astype(int)
    else:
        y_train_pred = active_model.predict(X_train_scaled)
        y_train_prob = y_train_pred.astype(float)

    train_metrics = compute_metrics(y_train, y_train_pred, y_train_prob, train_samples, is_calibrated, calib_method)

    # 6. Out-of-Sample Held-Out Test Evaluation
    if hasattr(active_model, "predict_proba"):
        y_test_prob = active_model.predict_proba(X_test_scaled)[:, pos_idx]
        y_test_pred = (y_test_prob >= 0.5).astype(int)
    else:
        y_test_pred = active_model.predict(X_test_scaled)
        y_test_prob = y_test_pred.astype(float)

    test_metrics = compute_metrics(y_test, y_test_pred, y_test_prob, test_samples, is_calibrated, calib_method)

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
        calibrator=calibrator,
        is_calibrated=is_calibrated,
        calibration_method=calib_method,
    )

    # 7. Save model to disk if directory specified or default exists
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
        if isinstance(analyzer, TrainedSteganalyzer):
            return analyzer
        return None
    except Exception:
        return None


def format_metrics_summary(metrics: EvaluationMetrics) -> str:
    """Format an EvaluationMetrics instance as an academic markdown string."""
    calib_str = f"Yes ({metrics.calibration_method})" if metrics.is_calibrated else "No (uncalibrated)"
    lines = [
        f"**Accuracy:** {metrics.accuracy:.2%} | **Precision:** {metrics.precision:.4f} | "
        f"**Recall:** {metrics.recall:.4f} | **F1:** {metrics.f1_score:.4f}",
        f"**ROC-AUC:** {metrics.roc_auc:.4f}" if metrics.roc_auc is not None else "**ROC-AUC:** N/A",
        f"**Calibrated:** {calib_str}",
        f"**Confusion Matrix:** TP={metrics.true_positives}, TN={metrics.true_negatives}, "
        f"FP={metrics.false_positives}, FN={metrics.false_negatives}",
        f"**Samples:** {metrics.total_samples} (Cover: {metrics.cover_count}, Stego: {metrics.stego_count})",
    ]
    return "\n".join(lines)
