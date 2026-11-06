"""Independent detectability and embedding rate metrics for multimodal steganography.

This module provides detectability measures that do NOT rely on the allocator's
covariance matrix Sigma or complexity scores:
1. Physical Embedding Rates:
   - Image bits-per-pixel (bpp) and bits-per-channel (bpc)
   - Audio bits-per-sample (bps)
   - Video bits-per-pixel-frame (bppf)
2. Westfeld's Chi-Square Attack on Image Pairs of Values (PoVs):
   - Computes chi-square statistic and p-value on LSB pairs of values (2k, 2k+1).
   - If p-value < 0.05, rejects natural cover hypothesis (indicating stego manipulation).
   - Stego detection probability: P_stego = 1.0 - p_value.
3. Audio Sample-Pair LSB Symmetry Analysis:
   - Measures asymmetry in sample difference histograms and LSB parity distribution.
   - Stego embedding flattens pair differences; measures sample-pair deviation index.
"""

import io
import math
from typing import Any, Dict, Tuple, Union

import numpy as np
from PIL import Image
from scipy.stats import chi2
import wave


def compute_carrier_embedding_rates(
    b_I: int,
    b_A: int,
    b_V: int,
    image_shape: Tuple[int, int, int],  # (height, width, channels)
    audio_samples: int,
    video_shape: Tuple[int, int, int, int],  # (num_frames, height, width, channels)
) -> Dict[str, float]:
    """Compute per-carrier physical embedding rates.

    Embedding rate is the primary theoretical driver of statistical detectability.
    Higher embedding rate = larger statistical perturbation in that carrier channel.

    Returns:
        dict with:
            image_bpp: Image payload bits per pixel
            image_bpc: Image payload bits per color channel
            audio_bps: Audio payload bits per audio sample
            video_bppf: Video payload bits per spatial pixel per frame
    """
    h_img, w_img, c_img = image_shape
    total_img_pixels = max(1, h_img * w_img)
    total_img_subpixels = max(1, total_img_pixels * c_img)

    img_bpp = (b_I * 8.0) / total_img_pixels
    img_bpc = (b_I * 8.0) / total_img_subpixels

    aud_samples = max(1, audio_samples)
    aud_bps = (b_A * 8.0) / aud_samples

    n_frames, h_vid, w_vid, _ = video_shape
    total_vid_pixels = max(1, n_frames * h_vid * w_vid)
    vid_bppf = (b_V * 8.0) / total_vid_pixels

    return {
        "image_bpp": round(img_bpp, 4),
        "image_bpc": round(img_bpc, 4),
        "audio_bps": round(aud_bps, 4),
        "video_bppf": round(vid_bppf, 4),
    }


def analyze_image_chi_square(image_bytes: bytes) -> Dict[str, float]:
    """Execute Westfeld's Chi-Square (PoVs) steganalysis attack on image bytes.

    Theory:
    In natural cover images, frequencies of adjacent even-odd values (2k, 2k+1)
    differ significantly due to image texture.
    Sequential or pseudorandom LSB embedding equalizes the frequencies of 2k and 2k+1:
        E[h(2k)] = E[h(2k+1)] = (h(2k) + h(2k+1)) / 2.
    The chi-square statistic:
        chi2_stat = sum_{k=0}^{127} (h(2k) - h*(2k))^2 / h*(2k)
    where h*(2k) = (h(2k) + h(2k+1)) / 2.
    Degrees of freedom = number of pairs with h(2k) + h(2k+1) > 0 minus 1.
    p_value = 1.0 - chi2.cdf(chi2_stat, df).

    If p_value is near 0.0, the histogram matches LSB equalization (stego detected).
    If p_value is near 1.0, the image shows natural PoV variance (clean cover).

    Returns:
        dict with:
            chi2_stat: float
            p_value: float (probability of clean cover)
            stego_detected: 1.0 if p_value < 0.05, else 0.0
            stego_prob: estimated steganography probability in [0, 1]
    """
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    arr = np.asarray(img, dtype=np.uint8)

    # Flatten pixel values
    flat = arr.ravel()
    hist, _ = np.histogram(flat, bins=256, range=(0, 256))

    # Evaluate Pairs of Values (2k, 2k+1) for k in [0, 127]
    chi2_stat = 0.0
    valid_pairs = 0

    for k in range(128):
        c_even = hist[2 * k]
        c_odd = hist[2 * k + 1]
        pair_sum = c_even + c_odd
        if pair_sum > 5:  # Avoid division by near-zero counts
            expected = pair_sum / 2.0
            diff = c_even - expected
            chi2_stat += (diff ** 2) / expected
            valid_pairs += 1

    if valid_pairs > 1:
        df = valid_pairs - 1
        p_val = float(1.0 - chi2.cdf(chi2_stat, df))
        # Ensure numerical safety
        p_val = max(0.0, min(1.0, p_val))
    else:
        df = 1
        p_val = 1.0

    stego_prob = 1.0 - p_val
    return {
        "chi2_stat": round(float(chi2_stat), 3),
        "degrees_of_freedom": int(df),
        "p_value": round(p_val, 4),
        "stego_detected": 1.0 if p_val < 0.05 else 0.0,
        "stego_prob": round(stego_prob, 4),
    }


def analyze_audio_sample_pairs(audio_bytes: bytes) -> Dict[str, float]:
    """Execute Sample-Pair LSB Symmetry steganalysis on 16-bit PCM WAV audio.

    Theory:
    In natural audio signals, adjacent samples s[t] and s[t+1] are strongly correlated.
    The difference d[t] = s[t+1] - s[t] is smoothly distributed around 0.
    LSB replacement acts as an independent binary noise injection, distorting the
    even-odd difference parity and increasing high-frequency sample fluctuation.
    We measure the sample-pair parity ratio and high-frequency difference variance.

    Returns:
        dict with:
            lsb_one_ratio: fraction of LSBs that are 1 (0.5 in ideal random stego)
            sample_pair_diff_var: variance of sample differences
            audio_stego_score: normalized heuristic indicator in [0, 1]
    """
    with wave.open(io.BytesIO(audio_bytes), "rb") as wf:
        n_samples = wf.getnframes()
        raw = wf.readframes(n_samples)
        samples = np.frombuffer(raw, dtype=np.int16)

    if len(samples) < 10:
        return {"lsb_one_ratio": 0.5, "sample_pair_diff_var": 0.0, "audio_stego_score": 0.0}

    # Extract LSBs
    lsbs = samples & 1
    lsb_one_ratio = float(np.mean(lsbs))

    # Evaluate sample differences
    diffs = np.diff(samples.astype(np.float64))
    diff_var = float(np.var(diffs))

    # Second-order differences (detects high-frequency LSB toggling)
    second_diffs = np.diff(diffs)
    second_var = float(np.var(second_diffs))

    # Deviation of LSB parity from natural audio bias:
    # Encrypted AES ciphertext has uniform 50.0% 1-bits.
    parity_bias = abs(lsb_one_ratio - 0.5)

    # Audio Sample-Pair Histogram Chi-Square Attack
    offset_s = samples.astype(np.int32) + 32768
    hist, _ = np.histogram(offset_s, bins=65536, range=(0, 65536))
    chi2_stat = 0.0
    valid_pairs = 0
    for k in range(32768):
        c_even = hist[2 * k]
        c_odd = hist[2 * k + 1]
        pair_sum = c_even + c_odd
        if pair_sum > 5:
            expected = pair_sum / 2.0
            diff = c_even - expected
            chi2_stat += (diff ** 2) / expected
            valid_pairs += 1

    if valid_pairs > 1:
        df = valid_pairs - 1
        p_val = float(1.0 - chi2.cdf(chi2_stat, df))
        p_val = max(0.0, min(1.0, p_val))
    else:
        df = 1
        p_val = 1.0

    return {
        "lsb_one_ratio": round(lsb_one_ratio, 4),
        "sample_pair_diff_var": round(diff_var, 2),
        "second_diff_var": round(second_var, 2),
        "parity_bias": round(parity_bias, 4),
        "audio_chi2_stat": round(float(chi2_stat), 3),
        "audio_chi2_p_val": round(p_val, 4),
        "audio_stego_prob": round(1.0 - p_val, 4),
    }


def analyze_video_per_frame_chi_square(video_bytes: bytes) -> Dict[str, float]:
    """Execute per-frame Chi-Square (PoVs) steganalysis across all video frames.

    Decodes each video frame and evaluates spatial LSB pair equalization independently.
    Computes the mean frame Chi-square statistic, mean p-value, and the fraction
    of video frames flagged as stego (p < 0.05).

    Returns:
        dict with:
            video_mean_chi2_stat: float
            video_mean_p_val: float
            video_stego_prob: float
            video_frames_detected_ratio: fraction of frames with p < 0.05
    """
    from app.media.video_stego import load_video_from_bytes

    try:
        frames, _ = load_video_from_bytes(video_bytes)
    except Exception:
        return {
            "video_mean_chi2_stat": 0.0,
            "video_mean_p_val": 1.0,
            "video_stego_prob": 0.0,
            "video_frames_detected_ratio": 0.0,
        }

    if not frames:
        return {
            "video_mean_chi2_stat": 0.0,
            "video_mean_p_val": 1.0,
            "video_stego_prob": 0.0,
            "video_frames_detected_ratio": 0.0,
        }

    stats = []
    p_vals = []
    detected_count = 0

    for f in frames:
        flat = f.ravel()
        hist, _ = np.histogram(flat, bins=256, range=(0, 256))
        chi2_stat = 0.0
        valid_pairs = 0
        for k in range(128):
            c_even = hist[2 * k]
            c_odd = hist[2 * k + 1]
            pair_sum = c_even + c_odd
            if pair_sum > 5:
                expected = pair_sum / 2.0
                diff = c_even - expected
                chi2_stat += (diff ** 2) / expected
                valid_pairs += 1

        if valid_pairs > 1:
            df = valid_pairs - 1
            p_val = float(1.0 - chi2.cdf(chi2_stat, df))
            p_val = max(0.0, min(1.0, p_val))
        else:
            p_val = 1.0

        stats.append(chi2_stat)
        p_vals.append(p_val)
        if p_val < 0.05:
            detected_count += 1

    mean_stat = float(np.mean(stats))
    mean_pval = float(np.mean(p_vals))
    det_ratio = float(detected_count / len(frames))

    return {
        "video_mean_chi2_stat": round(mean_stat, 3),
        "video_mean_p_val": round(mean_pval, 4),
        "video_stego_prob": round(1.0 - mean_pval, 4),
        "video_frames_detected_ratio": round(det_ratio, 4),
    }
