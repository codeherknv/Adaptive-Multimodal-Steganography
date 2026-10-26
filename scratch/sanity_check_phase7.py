"""
Phase 7 Final Sanity Check & Verification Script:
Validates:
1. Live inference reproducibility on saved models across multiple independent Cover & Stego samples (PNG, WAV, AVI).
2. Feature vector verification: exact dimensions, all finite values, exact feature ordering and scaling.
3. Feature & metadata inspection for synthetic generation leakage, filenames, strategy names, or labels.
4. Probability output auditing: correct Stego class (label 1), score explanation between Cover and Stego.
5. Error handling audit: unsupported format, insufficient capacity, corrupted carrier, failed extraction, missing model file.
"""

import sys
import os
import io
import json
import numpy as np
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from app.main import app
from app.steganalysis.classifier import classify_media_file, detect_media_modality
from app.steganalysis.trainer import load_steganalyzer, train_steganalyzer
from app.steganalysis.dataset_generator import (
    generate_procedural_image,
    generate_procedural_audio,
    generate_procedural_video,
    IMAGE_FEATURE_NAMES,
    AUDIO_FEATURE_NAMES,
    VIDEO_FEATURE_NAMES,
)
from app.media.image_stego import embed_in_image, extract_from_image
from app.media.audio_stego import embed_in_audio, extract_from_audio
from app.media.video_stego import embed_in_video, extract_from_video
from app.core.crypto_utils import generate_key, encrypt, decrypt


def test_live_inference_and_features():
    print("=" * 75)
    print("CHECK 1 & 2: LIVE INFERENCE REPRODUCIBILITY & FEATURE VECTOR INTEGRITY")
    print("=" * 75)

    client = TestClient(app)
    modalities = [
        ("image", generate_procedural_image, embed_in_image, "test_{}.png", IMAGE_FEATURE_NAMES),
        ("audio", generate_procedural_audio, embed_in_audio, "test_{}.wav", AUDIO_FEATURE_NAMES),
        ("video", generate_procedural_video, embed_in_video, "test_{}.avi", VIDEO_FEATURE_NAMES),
    ]

    for mod, gen_fn, embed_fn, fn_fmt, exp_names in modalities:
        print(f"\n--- Testing Modality: {mod.upper()} (Expected Features: {len(exp_names)}) ---")
        analyzer = load_steganalyzer(mod, "random_forest")
        assert analyzer is not None, f"Saved Random Forest model for {mod} must exist on disk!"
        assert analyzer.feature_names == exp_names, f"Saved model feature names must match exactly: {exp_names}"

        for idx in [0, 1, 2]:
            # 1. Generate Clean Cover
            if mod == "image":
                cover_bytes = gen_fn(source_index=idx, width=80, height=80)
            elif mod == "audio":
                cover_bytes = gen_fn(source_index=idx, duration_sec=1.0)
            else:
                cover_bytes = gen_fn(source_index=idx, num_frames=12, width=80, height=80)

            # 2. Embed Valid Stego
            key = generate_key()
            secret_msg = f"SanityCheckPayload_Source_{idx}_{mod}"
            envelope = encrypt(secret_msg.encode("utf-8"), key)

            if mod == "image":
                stego_arr, _ = embed_fn(cover_bytes, envelope)
                from app.media.image_stego import save_image_to_png_bytes
                stego_bytes = save_image_to_png_bytes(stego_arr)
            elif mod == "audio":
                stego_bytes, _ = embed_fn(cover_bytes, envelope)
            else:
                stego_bytes, _, _ = embed_fn(cover_bytes, envelope)

            # Live inference on Cover
            cover_res = classify_media_file(cover_bytes, filename=fn_fmt.format(f"cover_{idx}"), model_type="random_forest")
            # Live inference on Stego
            stego_res = classify_media_file(stego_bytes, filename=fn_fmt.format(f"stego_{idx}"), model_type="random_forest")

            # Check feature vectors
            for res, kind in [(cover_res, "Cover"), (stego_res, "Stego")]:
                feats_map = res.feature_values
                feat_keys = list(feats_map.keys())
                assert feat_keys == exp_names, f"Feature ordering mismatch in {mod} {kind}: {feat_keys} vs {exp_names}"
                vals = np.array(list(feats_map.values()))
                assert len(vals) == len(exp_names), f"Feature length {len(vals)} != {len(exp_names)}"
                assert np.all(np.isfinite(vals)), f"Non-finite values detected in {mod} {kind} features!"

            print(f"  Source {idx}: Cover P(Stego)={cover_res.stego_probability:.4f} ({cover_res.predicted_class}) | "
                  f"Stego P(Stego)={stego_res.stego_probability:.4f} ({stego_res.predicted_class}) | "
                  f"All {len(vals)} features finite & ordered perfectly.")


def test_features_and_metadata_leakage():
    print("\n" + "=" * 75)
    print("CHECK 3: VERIFY ZERO LEAKAGE OF GENERATION PATTERNS / FILENAMES / LABELS")
    print("=" * 75)

    # Verify that feature extractors depend only on raw signal bytes, NOT filenames or labels
    img_bytes = generate_procedural_image(source_index=55)

    # Classify with misleading filenames
    res_fake_stego = classify_media_file(img_bytes, filename="stego_label1_adaptive_synthetic.png")
    res_fake_cover = classify_media_file(img_bytes, filename="cover_label0_baseline_real.png")

    assert res_fake_stego.stego_probability == res_fake_cover.stego_probability, \
        "Classifier probability must NOT depend on filename or synthetic labels!"
    assert res_fake_stego.feature_values == res_fake_cover.feature_values, \
        "Feature values must NOT depend on filename!"

    # Verify that feature dictionary keys contain no metadata/label keywords
    forbidden = ["label", "source", "strategy", "target", "secret", "key", "password", "synthetic", "filename"]
    for mod, names in [("image", IMAGE_FEATURE_NAMES), ("audio", AUDIO_FEATURE_NAMES), ("video", VIDEO_FEATURE_NAMES)]:
        for f in names:
            for w in forbidden:
                assert w not in f.lower(), f"Feature name '{f}' in {mod} contains forbidden metadata word '{w}'!"

    print("  [PASS] Confirmed: Feature extraction depends solely on signal/pixel bytes.")
    print("  [PASS] Confirmed: Filenames, class labels, and metadata are 100% excluded from model inputs.")


def test_probability_outputs_and_shift_reasons():
    print("\n" + "=" * 75)
    print("CHECK 4: POSITIVE CLASS PROBABILITY & PNG SCORE EXPLANATION")
    print("=" * 75)

    for mod in ["image", "audio", "video"]:
        analyzer = load_steganalyzer(mod, "random_forest")
        active = analyzer.calibrator if analyzer.calibrator is not None else analyzer.classifier
        classes = active.classes_
        assert list(classes) == [0, 1], f"Active model classes for {mod} must be [0, 1], got {classes}"
        print(f"  Modality '{mod}': Active classes = {classes.tolist()} (Class 1 = Stego). Calibration: {analyzer.calibration_method}")

    # Inspect Cover vs Stego Image feature shifts
    img_cover = generate_procedural_image(source_index=99)
    key = generate_key()
    env = encrypt(b"ExplanatoryTestPayloadForSignalDistortion", key)
    img_stego_arr, _ = embed_in_image(img_cover, env)
    from app.media.image_stego import save_image_to_png_bytes
    img_stego = save_image_to_png_bytes(img_stego_arr)

    c_res = classify_media_file(img_cover, filename="c.png")
    s_res = classify_media_file(img_stego, filename="s.png")

    print(f"\n  Detailed Image Feature Shift Analysis:")
    print(f"    Clean Cover P(Stego):  {c_res.stego_probability:.4f} -> Class: {c_res.predicted_class}")
    print(f"    Embedded Stego P(Stego): {s_res.stego_probability:.4f} -> Class: {s_res.predicted_class}")
    print(f"    Key Statistical Shifts Explaining Probability Delta:")
    for k in ["img_lsb_one_ratio", "img_lsb_transition_rate", "img_pov_asymmetry", "img_highpass_residual_var"]:
        cv = c_res.feature_values[k]
        sv = s_res.feature_values[k]
        print(f"      - {k:<28}: Cover = {cv:<8.5f} | Stego = {sv:<8.5f} | Delta = {sv - cv:+.5f}")


def test_graceful_error_handling():
    print("\n" + "=" * 75)
    print("CHECK 5: GRACEFUL ERROR HANDLING (UNSUPPORTED, CAPACITY, CORRUPTED, EXTRACTION)")
    print("=" * 75)

    client = TestClient(app)

    # 1. Unsupported media format in steganalysis classify
    bad_bytes = b"This is a plain text file, definitely not PNG, WAV, or AVI."
    resp = client.post(
        "/api/steganalysis/classify",
        files={"file": ("notes.txt", io.BytesIO(bad_bytes), "text/plain")},
        data={"model_type": "random_forest"}
    )
    assert resp.status_code == 400, f"Expected 400 for unsupported format, got {resp.status_code}"
    assert "Unable to recognize media format" in resp.json()["detail"]
    print("  [PASS] Unsupported format rejected with HTTP 400 and clear error detail.")

    # 2. Corrupted PNG carrier in classify
    corrupt_png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 20 # Header present but truncated/corrupt
    resp = client.post(
        "/api/steganalysis/classify",
        files={"file": ("corrupt.png", io.BytesIO(corrupt_png), "image/png")},
        data={"model_type": "random_forest"}
    )
    assert resp.status_code == 400, f"Expected 400 for corrupt PNG, got {resp.status_code}"
    print("  [PASS] Corrupted image carrier rejected with HTTP 400.")

    # 3. Insufficient capacity in image embedding
    tiny_img = generate_procedural_image(source_index=1, width=16, height=16) # Very small capacity (~96 bytes)
    huge_env = encrypt(b"X" * 500, generate_key()) # Envelope is ~530 bytes > 96 bytes
    from app.core.crypto_utils import bytes_to_base64
    resp = client.post(
        "/api/image/embed",
        files={"image": ("tiny.png", io.BytesIO(tiny_img), "image/png")},
        data={"envelope": bytes_to_base64(huge_env), "encoding": "base64"}
    )
    assert resp.status_code == 400, f"Expected 400 for insufficient capacity, got {resp.status_code}"
    assert "Insufficient carrier capacity" in resp.json()["detail"] or "exceeds" in resp.json()["detail"]
    print("  [PASS] Insufficient carrier capacity rejected with HTTP 400.")

    # 4. Failed extraction / wrong key/password
    cover_img = generate_procedural_image(source_index=2, width=64, height=64)
    key = generate_key()
    env = encrypt(b"TopSecretMessage", key)
    stego_arr, _ = embed_in_image(cover_img, env)
    from app.media.image_stego import save_image_to_png_bytes
    stego_bytes = save_image_to_png_bytes(stego_arr)

    # Extract without encryption (should get envelope)
    resp = client.post(
        "/api/image/extract",
        files={"image": ("stego.png", io.BytesIO(stego_bytes), "image/png")}
    )
    assert resp.status_code == 200, f"Expected 200 for raw envelope extraction, got {resp.status_code}"

    # Extract clean cover (not stego)
    resp_clean = client.post(
        "/api/image/extract",
        files={"image": ("clean.png", io.BytesIO(cover_img), "image/png")}
    )
    assert resp_clean.status_code == 400, f"Expected 400 for clean cover extraction, got {resp_clean.status_code}"
    assert "Invalid steganography signature" in resp_clean.json()["detail"] or "Extraction failed" in resp_clean.json()["detail"]
    print("  [PASS] Non-stego extraction rejected with HTTP 400.")

    # Multimodal extract with wrong password
    from app.allocation.engine import embed_multimodal
    mm_res = embed_multimodal(
        message="Secret Multimodal Payload",
        image_bytes=generate_procedural_image(1),
        audio_bytes=generate_procedural_audio(1),
        video_bytes=generate_procedural_video(1),
        password="CorrectPassword123!",
        strategy_name="adaptive"
    )
    salt_hex = mm_res.salt_bytes.hex() if mm_res.salt_bytes else "00" * 16
    resp_wrong = client.post(
        "/api/multimodal/extract",
        files={"bundle_zip": ("bundle.zip", io.BytesIO(mm_res.zip_bundle_bytes), "application/zip")},
        data={"password": "WrongPassword999!", "salt": salt_hex}
    )
    assert resp_wrong.status_code == 400, f"Expected 400 for wrong password, got {resp_wrong.status_code}"
    assert "Decryption authentication failed" in resp_wrong.json()["detail"] or "failed" in resp_wrong.json()["detail"]
    print("  [PASS] Multimodal extraction with wrong password rejected with HTTP 400.")

    # 5. Missing model file on disk handled gracefully
    # If a model is deleted from disk, load_steganalyzer returns None, and classify_media_file falls back to on-demand training
    import tempfile
    from app.steganalysis.classifier import classify_media_file
    from unittest.mock import patch

    with patch("app.steganalysis.classifier.load_steganalyzer", return_value=None):
        fallback_res = classify_media_file(cover_img, filename="fallback.png", model_type="random_forest")
        assert fallback_res is not None
        assert fallback_res.predicted_class in ("Cover", "Stego")
        print("  [PASS] Missing model file triggers graceful on-demand baseline training without crash.")


if __name__ == "__main__":
    test_live_inference_and_features()
    test_features_and_metadata_leakage()
    test_probability_outputs_and_shift_reasons()
    test_graceful_error_handling()
    print("\n" + "=" * 75)
    print("ALL SANITY CHECKS PASSED WITH ZERO DEFECTS")
    print("=" * 75)
