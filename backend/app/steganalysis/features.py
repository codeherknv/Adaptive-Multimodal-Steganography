"""Steganalysis feature extraction across image, audio, and video modalities.

This module extracts first- and second-order statistical, signal, and residual features
designed to detect Least Significant Bit (LSB) embedding artifacts.

Theoretical Steganalysis Background:
-----------------------------------
1. LSB 1-Ratio & Bernoulli Regularization:
   In uncompressed natural media, the distribution of LSBs often exhibits natural bias
   (e.g., uneven parity due to sensor noise or illumination gradients). Hiding an encrypted,
   high-entropy payload drives the empirical LSB probability P(LSB = 1) toward exactly 0.5.
2. Pairs of Values (PoV) / Sample Pair Analysis (SPA):
   LSB substitution maps adjacent even/odd intensity pairs (2k <-> 2k+1) into each other.
   This equalizes the bin frequencies of adjacent histogram pairs: |h(2k) - h(2k+1)| decreases
   as embedding density increases.
3. First- & Second-Order Differences:
   LSB replacement acts as an additive, independent, uniformly distributed noise source
   d in {-1, 0, 1}. In natural continuous signals (audio waveforms or spatial gradients),
   adjacent samples are highly correlated. Adding independent LSB noise increases the variance
   of sample differences and flattens the peaked difference histogram (reducing kurtosis).
4. High-Frequency Spectral & Residual Energy:
   Because LSB modifications alternate rapidly across adjacent samples, they introduce
   artificial high-frequency energy observable in high-pass spatial filtering or spectral FFT bands.

Scientific Notice:
-----------------
These features provide interpretable, lightweight baseline detection suitable for
comparative evaluation. They do NOT guarantee 100% detection accuracy on low-rate payloads
(< 0.05 bpp) or non-LSB steganographic algorithms.
"""

import io
import math
from typing import Dict, List, Tuple, Union
import cv2
import numpy as np
from scipy import stats

from app.media.image_stego import load_image_as_rgb_array, UnsupportedImageFormatError
from app.media.audio_stego import load_wav_audio, UnsupportedAudioFormatError
from app.media.video_stego import load_video_from_bytes, UnsupportedVideoFormatError


class FeatureExtractionError(Exception):
    """Raised when feature extraction fails due to corrupted or unsupported media."""
    pass


# =========================================================================
# 1. IMAGE STEGANALYSIS FEATURES
# =========================================================================

IMAGE_FEATURE_NAMES = [
    "img_lsb_one_ratio",           # Frequency of 1s in RGB LSBs (drives to 0.5 in stego)
    "img_pov_asymmetry",           # Mean relative difference between adjacent even-odd histogram bins
    "img_horiz_diff_var",          # Variance of horizontal pixel differences
    "img_vert_diff_var",           # Variance of vertical pixel differences
    "img_diff_kurtosis",           # Kurtosis of pixel difference histogram (decreases in stego)
    "img_highpass_residual_var",   # Variance of high-pass Laplacian filtered image
    "img_lsb_transition_rate",     # Fraction of adjacent pixels with differing LSB values
    "img_mean_intensity",          # Average pixel intensity across RGB
    "img_std_intensity",           # Standard deviation of pixel intensity
    "img_rg_diff_var",             # Cross-channel variance between Red and Green channels
]


def extract_image_features(image_input: Union[bytes, np.ndarray]) -> Tuple[np.ndarray, List[str]]:
    """Extract 10 statistical and LSB artifact features from a candidate image.

    Args:
        image_input: Raw image bytes or existing NumPy uint8 RGB array.

    Returns:
        Tuple of (1D float64 NumPy array of 10 features, list of feature names).

    Raises:
        FeatureExtractionError: If image cannot be read or has incompatible dimensions.
    """
    try:
        img_arr, _ = load_image_as_rgb_array(image_input)
    except (UnsupportedImageFormatError, Exception) as e:
        raise FeatureExtractionError(f"Image feature extraction failed: {str(e)}") from e

    h, w, c = img_arr.shape
    if h < 4 or w < 4:
        raise FeatureExtractionError(f"Image is too small for statistical analysis: {w}x{h}.")

    rgb = img_arr[:, :, :3]
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY).astype(np.float64)

    # 1. LSB 1-ratio across RGB channels
    lsbs = rgb & 1
    lsb_one_ratio = float(np.mean(lsbs))

    # 2. Pairs of Values (PoV) asymmetry across grayscale histogram
    hist, _ = np.histogram(gray, bins=256, range=(0, 256))
    even_bins = hist[0::2].astype(np.float64)
    odd_bins = hist[1::2].astype(np.float64)
    denom = even_bins + odd_bins + 1e-6
    pov_asymmetry = float(np.mean(np.abs(even_bins - odd_bins) / denom))

    # 3. Horizontal and vertical first-order differences
    diff_h = np.diff(gray, axis=1)
    diff_v = np.diff(gray, axis=0)
    horiz_diff_var = float(np.var(diff_h))
    vert_diff_var = float(np.var(diff_v))

    # 4. Difference histogram kurtosis (excess kurtosis: normal = 0)
    flat_diff = diff_h.flatten()
    diff_kurtosis = float(stats.kurtosis(flat_diff)) if len(flat_diff) > 10 else 0.0

    # 5. High-pass Laplacian residual variance
    laplacian = cv2.Laplacian(gray, cv2.CV_64F)
    highpass_residual_var = float(np.var(laplacian))

    # 6. LSB transition rate across adjacent horizontal pixels
    gray_lsb = gray.astype(np.uint8) & 1
    lsb_transitions = np.abs(np.diff(gray_lsb, axis=1))
    lsb_transition_rate = float(np.mean(lsb_transitions))

    # 7. Basic intensity statistics
    mean_intensity = float(np.mean(gray))
    std_intensity = float(np.std(gray))

    # 8. Cross-channel difference variance (Red vs Green)
    rg_diff = rgb[:, :, 0].astype(np.float64) - rgb[:, :, 1].astype(np.float64)
    rg_diff_var = float(np.var(rg_diff))

    feats = np.array([
        lsb_one_ratio,
        pov_asymmetry,
        horiz_diff_var,
        vert_diff_var,
        diff_kurtosis,
        highpass_residual_var,
        lsb_transition_rate,
        mean_intensity,
        std_intensity,
        rg_diff_var,
    ], dtype=np.float64)

    # Sanitize any NaNs or Infs
    feats = np.nan_to_num(feats, nan=0.0, posinf=1e6, neginf=-1e6)
    return feats, list(IMAGE_FEATURE_NAMES)


# =========================================================================
# 2. AUDIO STEGANALYSIS FEATURES
# =========================================================================

AUDIO_FEATURE_NAMES = [
    "aud_lsb_one_ratio",           # Frequency of 1s in audio sample LSBs
    "aud_pov_asymmetry",           # Histogram even-odd pair asymmetry
    "aud_first_diff_var",          # Variance of first-order sample differences s(t) - s(t-1)
    "aud_diff_kurtosis",           # Kurtosis of first-order sample difference distribution
    "aud_second_diff_var",         # Variance of second-order sample differences s(t) - 2s(t-1) + s(t-2)
    "aud_lsb_transition_rate",     # Successive sample LSB flip frequency
    "aud_high_band_spectral_ratio",# Fraction of FFT energy in high frequencies (fs/4 to fs/2)
    "aud_rms_energy",              # Root Mean Square energy of the audio signal
]


def extract_audio_features(audio_input: Union[bytes, bytearray, io.BytesIO]) -> Tuple[np.ndarray, List[str]]:
    """Extract 8 statistical, acoustic, and LSB artifact features from a candidate WAV file.

    Args:
        audio_input: Raw WAV file bytes or stream.

    Returns:
        Tuple of (1D float64 NumPy array of 8 features, list of feature names).

    Raises:
        FeatureExtractionError: If audio cannot be read or contains too few samples.
    """
    try:
        samples, params = load_wav_audio(audio_input)
    except (UnsupportedAudioFormatError, Exception) as e:
        raise FeatureExtractionError(f"Audio feature extraction failed: {str(e)}") from e

    if len(samples) < 32:
        raise FeatureExtractionError(f"Audio file contains too few samples ({len(samples)}) for analysis.")

    # 1. LSB 1-ratio
    raw_lsb = (samples.astype(np.int64) & 1).astype(np.float64)
    lsb_one_ratio = float(np.mean(raw_lsb))

    # 2. Pairs of Values (PoV) asymmetry
    # Map samples to positive indices
    if samples.dtype == np.int16:
        # Shift int16 range [-32768, 32767] to [0, 65535]
        shifted = (samples.astype(np.int64) + 32768)
        bins_count = 1024  # coarse binning to capture pair frequencies
        hist, _ = np.histogram(shifted, bins=bins_count)
    else:  # uint8: 0..255
        hist, _ = np.histogram(samples, bins=256, range=(0, 256))

    even_bins = hist[0::2].astype(np.float64)
    odd_bins = hist[1::2].astype(np.float64)
    denom = even_bins + odd_bins + 1e-6
    pov_asymmetry = float(np.mean(np.abs(even_bins - odd_bins) / denom))

    # Normalize samples to [-1.0, 1.0] for signal processing
    if samples.dtype == np.int16:
        norm_samples = samples.astype(np.float64) / 32768.0
    else:
        norm_samples = (samples.astype(np.float64) - 128.0) / 128.0

    # 3. First-order differences Δs(t) = s(t) - s(t-1)
    diff1 = np.diff(norm_samples)
    first_diff_var = float(np.var(diff1))
    diff_kurtosis = float(stats.kurtosis(diff1)) if len(diff1) > 10 else 0.0

    # 4. Second-order differences Δ²s(t)
    diff2 = np.diff(diff1)
    second_diff_var = float(np.var(diff2)) if len(diff2) > 0 else 0.0

    # 5. LSB transition rate across successive samples
    lsb_diffs = np.abs(np.diff(raw_lsb))
    lsb_transition_rate = float(np.mean(lsb_diffs))

    # 6. High-band spectral energy ratio (upper half of spectrum)
    # Truncate to power of 2 for fast FFT if large
    n_fft = min(8192, 2 ** int(math.log2(len(norm_samples))))
    if n_fft >= 64:
        fft_mags = np.abs(np.fft.rfft(norm_samples[:n_fft]))
        split_idx = len(fft_mags) // 2
        total_energy = float(np.sum(fft_mags ** 2)) + 1e-9
        high_energy = float(np.sum(fft_mags[split_idx:] ** 2))
        high_band_spectral_ratio = high_energy / total_energy
    else:
        high_band_spectral_ratio = 0.0

    # 7. RMS Energy
    rms_energy = float(np.sqrt(np.mean(norm_samples ** 2)))

    feats = np.array([
        lsb_one_ratio,
        pov_asymmetry,
        first_diff_var,
        diff_kurtosis,
        second_diff_var,
        lsb_transition_rate,
        high_band_spectral_ratio,
        rms_energy,
    ], dtype=np.float64)

    feats = np.nan_to_num(feats, nan=0.0, posinf=1e6, neginf=-1e6)
    return feats, list(AUDIO_FEATURE_NAMES)


# =========================================================================
# 3. VIDEO STEGANALYSIS FEATURES
# =========================================================================

VIDEO_FEATURE_NAMES = [
    "vid_lsb_one_ratio",           # Average frequency of 1s in video frame subpixel LSBs
    "vid_interframe_diff_var",     # Variance of temporal differences between consecutive frames
    "vid_interframe_diff_kurt",    # Kurtosis of inter-frame difference distribution
    "vid_interframe_lsb_flip_rate",# Rate of LSB flips between consecutive frames at identical pixel
    "vid_spatial_diff_var",        # Mean horizontal spatial difference variance across keyframes
    "vid_highpass_residual_var",   # Mean Laplacian high-pass variance across keyframes
    "vid_mean_frame_intensity",    # Mean pixel intensity across sampled frames
]


def extract_video_features(
    video_input: bytes,
    max_frames_to_sample: int = 25
) -> Tuple[np.ndarray, List[str]]:
    """Extract 7 statistical, temporal motion, and LSB artifact features from an AVI video.

    Args:
        video_input: Raw video bytes.
        max_frames_to_sample: Maximum frames to inspect for deterministic runtime.

    Returns:
        Tuple of (1D float64 NumPy array of 7 features, list of feature names).

    Raises:
        FeatureExtractionError: If video cannot be decoded or has too few frames.
    """
    try:
        frames, meta = load_video_from_bytes(video_input)
    except (UnsupportedVideoFormatError, Exception) as e:
        raise FeatureExtractionError(f"Video feature extraction failed: {str(e)}") from e

    num_frames = len(frames)
    if num_frames == 0:
        raise FeatureExtractionError("Video contains zero decodable frames.")

    # Evenly sample frames
    if num_frames <= max_frames_to_sample:
        sampled_indices = list(range(num_frames))
    else:
        sampled_indices = np.linspace(0, num_frames - 1, max_frames_to_sample, dtype=int).tolist()

    sampled_frames = [frames[i] for i in sampled_indices]

    # Convert frames to grayscale float64
    gray_frames = [cv2.cvtColor(f, cv2.COLOR_BGR2GRAY).astype(np.float64) for f in sampled_frames]

    # 1. LSB 1-ratio across sampled frames
    lsb_means = [float(np.mean(f.astype(np.uint8) & 1)) for f in sampled_frames]
    lsb_one_ratio = float(np.mean(lsb_means))

    # 2. Inter-frame temporal difference statistics
    inter_diff_vars = []
    inter_diff_kurts = []
    inter_lsb_flips = []

    for i in range(1, len(gray_frames)):
        diff = gray_frames[i] - gray_frames[i - 1]
        inter_diff_vars.append(float(np.var(diff)))
        flat_diff = diff.flatten()
        if len(flat_diff) > 20:
            inter_diff_kurts.append(float(stats.kurtosis(flat_diff)))

        # Inter-frame LSB flip rate at identical coordinates
        lsb_prev = gray_frames[i - 1].astype(np.uint8) & 1
        lsb_curr = gray_frames[i].astype(np.uint8) & 1
        inter_lsb_flips.append(float(np.mean(np.abs(lsb_curr - lsb_prev))))

    interframe_diff_var = float(np.mean(inter_diff_vars)) if inter_diff_vars else 0.0
    interframe_diff_kurt = float(np.mean(inter_diff_kurts)) if inter_diff_kurts else 0.0
    interframe_lsb_flip_rate = float(np.mean(inter_lsb_flips)) if inter_lsb_flips else 0.0

    # 3. Spatial keyframe metrics
    spatial_vars = []
    lap_vars = []
    means = []

    for g in gray_frames:
        spatial_vars.append(float(np.var(np.diff(g, axis=1))))
        lap = cv2.Laplacian(g, cv2.CV_64F)
        lap_vars.append(float(np.var(lap)))
        means.append(float(np.mean(g)))

    spatial_diff_var = float(np.mean(spatial_vars)) if spatial_vars else 0.0
    highpass_residual_var = float(np.mean(lap_vars)) if lap_vars else 0.0
    mean_frame_intensity = float(np.mean(means)) if means else 0.0

    feats = np.array([
        lsb_one_ratio,
        interframe_diff_var,
        interframe_diff_kurt,
        interframe_lsb_flip_rate,
        spatial_diff_var,
        highpass_residual_var,
        mean_frame_intensity,
    ], dtype=np.float64)

    feats = np.nan_to_num(feats, nan=0.0, posinf=1e6, neginf=-1e6)
    return feats, list(VIDEO_FEATURE_NAMES)
