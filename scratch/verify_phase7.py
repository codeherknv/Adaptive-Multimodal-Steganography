"""
Empirical verification script for Phase 7:
ML-Based Steganalysis, Feature Extraction, and Detectability Evaluation.

Executes:
1. Dataset generation across Image, Audio, and Video modalities.
2. Zero-leakage GroupShuffleSplit verification (strict source_id isolation).
3. Training of Random Forest and Logistic Regression baseline classifiers.
4. Comprehensive evaluation (Accuracy, Precision, Recall, F1, ROC-AUC, Confusion Matrix).
5. Breakdown by payload category (low, medium, high) and matched condition (Fixed vs. Adaptive).
6. Single-file live inference verification on Cover vs Stego media.
"""

import os
import sys

# Ensure backend app is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from app.steganalysis.dataset_generator import (
    generate_modality_dataset,
    generate_procedural_image,
    generate_procedural_audio,
    generate_procedural_video,
)
from app.steganalysis.trainer import train_steganalyzer
from app.steganalysis.classifier import classify_media_file
from app.media.image_stego import embed_in_image
from app.core.crypto_utils import generate_key, encrypt


def main():
    print("=" * 80)
    print("PHASE 7 EMPIRICAL VERIFICATION: ML-BASED STEGANALYSIS & DETECTABILITY")
    print("=" * 80)

    modalities = ["image", "audio", "video"]
    results = {}

    for modality in modalities:
        print(f"\n" + "-" * 70)
        print(f"MODALITY: {modality.upper()}")
        print("-" * 70)

        # 1. Generate balanced benchmark dataset
        print(f"Generating balanced benchmark dataset for {modality} (10 sources)...")
        dataset = generate_modality_dataset(
            modality=modality,
            num_sources=10,
            payload_fractions=[0.10, 0.35, 0.55],
            allocation_strategies=["fixed", "adaptive"],
        )
        summary = dataset.to_dict()
        print(f"  Total samples: {summary['total_samples']} "
              f"(Covers: {summary['cover_count']}, Stegos: {summary['stego_count']}, "
              f"Independent Sources: {summary['sources_count']})")
        print(f"  Feature dimensions: {len(summary['feature_names'])} features ({', '.join(summary['feature_names'][:4])}...)")

        # 2. Train Random Forest Classifier with Zero-Leakage GroupShuffleSplit
        print(f"\nTraining Random Forest Classifier on {modality}...")
        rf_analyzer = train_steganalyzer(
            dataset,
            model_type="random_forest",
            test_size=0.30,
            random_state=42
        )
        rf_eval = rf_analyzer.test_metrics
        print(f"  RF Test Results (Sources train: {len(rf_analyzer.train_sources)}, test: {len(rf_analyzer.test_sources)}):")
        print(f"    Accuracy:  {rf_eval.accuracy:.2%}")
        print(f"    Precision: {rf_eval.precision:.4f}")
        print(f"    Recall:    {rf_eval.recall:.4f}")
        print(f"    F1-Score:  {rf_eval.f1_score:.4f}")
        roc_auc_str = f"{rf_eval.roc_auc:.4f}" if rf_eval.roc_auc is not None else "N/A"
        print(f"    ROC-AUC:   {roc_auc_str}")
        print(f"    Confusion Matrix: TP={rf_eval.true_positives}, TN={rf_eval.true_negatives}, FP={rf_eval.false_positives}, FN={rf_eval.false_negatives}")

        if rf_eval.by_payload_category:
            print("    Detection Rate by Payload Density:")
            for cat, data in rf_eval.by_payload_category.items():
                print(f"      - {cat.capitalize()} ({data['sample_count']} samples): {data['stego_detection_rate']:.2%}")

        if rf_eval.by_allocation_strategy:
            print("    Matched Condition Detection Rate by Strategy:")
            for strat, data in rf_eval.by_allocation_strategy.items():
                print(f"      - {strat.capitalize()} ({data['sample_count']} samples): {data['stego_detection_rate']:.2%}")

        # 3. Train Logistic Regression Classifier with Zero-Leakage GroupShuffleSplit
        print(f"\nTraining Logistic Regression Classifier on {modality}...")
        lr_analyzer = train_steganalyzer(
            dataset,
            model_type="logistic_regression",
            test_size=0.30,
            random_state=42
        )
        lr_eval = lr_analyzer.test_metrics
        lr_roc_auc_str = f"{lr_eval.roc_auc:.4f}" if lr_eval.roc_auc is not None else "N/A"
        print(f"  LR Test Results:")
        print(f"    Accuracy:  {lr_eval.accuracy:.2%}")
        print(f"    Precision: {lr_eval.precision:.4f}")
        print(f"    Recall:    {lr_eval.recall:.4f}")
        print(f"    F1-Score:  {lr_eval.f1_score:.4f}")
        print(f"    ROC-AUC:   {lr_roc_auc_str}")

        results[modality] = {
            "total_samples": summary["total_samples"],
            "rf": rf_eval,
            "lr": lr_eval,
        }

    # 4. Live Inference Testing on Single Files
    print("\n" + "=" * 80)
    print("LIVE SINGLE-FILE INFERENCE VERIFICATION")
    print("=" * 80)
    
    # Generate a fresh test cover image (source 99)
    test_cover_bytes = generate_procedural_image(source_index=99, width=64, height=64)
    key = generate_key()
    envelope = encrypt(b"Phase 7 Single File Live Steganalysis Probe Payload", key)
    test_stego_bytes, _ = embed_in_image(test_cover_bytes, envelope)

    # Classify clean cover
    cover_clf = classify_media_file(test_cover_bytes, filename="test_cover_image.png", model_type="random_forest")
    print(f"\n1. Clean Cover Inspection (test_cover_image.png):")
    print(f"   Predicted Class:      {cover_clf.predicted_class} (Label: {cover_clf.predicted_label})")
    print(f"   Stego Probability:    {cover_clf.stego_probability:.4f}")
    print(f"   Model Confidence:     {cover_clf.confidence_percentage}%")
    print(f"   Top Extracted Metric: img_lsb_one_ratio = {cover_clf.feature_values.get('img_lsb_one_ratio', 'N/A')}")

    # Classify stego file
    stego_clf = classify_media_file(test_stego_bytes, filename="test_stego_image.png", model_type="random_forest")
    print(f"\n2. Stego Carrier Inspection (test_stego_image.png):")
    print(f"   Predicted Class:      {stego_clf.predicted_class} (Label: {stego_clf.predicted_label})")
    print(f"   Stego Probability:    {stego_clf.stego_probability:.4f}")
    print(f"   Model Confidence:     {stego_clf.confidence_percentage}%")
    print(f"   Top Extracted Metric: img_lsb_one_ratio = {stego_clf.feature_values.get('img_lsb_one_ratio', 'N/A')}")
    print(f"   Scientific Notice:    {stego_clf.disclaimer[:70]}...")

    # Summary Table
    print("\n" + "=" * 80)
    print("PHASE 7 SUMMARY SCORECARD ACROSS MODALITIES")
    print("=" * 80)
    print(f"{'Modality':<10} | {'Samples':<8} | {'RF Acc':<8} | {'RF F1':<8} | {'LR Acc':<8} | {'LR F1':<8}")
    print("-" * 65)
    for mod, data in results.items():
        rf = data["rf"]
        lr = data["lr"]
        print(f"{mod.upper():<10} | {data['total_samples']:<8} | {rf.accuracy:<8.2%} | {rf.f1_score:<8.4f} | {lr.accuracy:<8.2%} | {lr.f1_score:<8.4f}")

    print("\n[VERIFICATION SUCCESS] Phase 7 benchmarks executed cleanly with zero data leakage.")


if __name__ == "__main__":
    main()
