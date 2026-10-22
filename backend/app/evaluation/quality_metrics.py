"""Image and media quality distortion metrics.

This module provides standard fidelity metrics for evaluating steganographic distortion:
1. Mean Squared Error (MSE):
   Quantifies the average squared pixel-channel difference between cover and stego media.
2. Peak Signal-to-Noise Ratio (PSNR):
   Measures image fidelity in decibels (dB) relative to the maximum possible signal power.
   Higher PSNR indicates lower numerical distortion. While PSNR > 40 dB is conventionally
   cited as visually inconspicuous to human perception, it measures visual fidelity only
   and does NOT guarantee security or resistance against statistical or ML-based steganalysis.
3. Structural Similarity Index (SSIM):
   Evaluates luminance, contrast, and structural consistency between image pairs.
   Ranges from -1.0 to +1.0 (where 1.0 represents perfect structural identity).
   Like PSNR, high SSIM indicates visual fidelity, not cryptographic or steganalytic security.
"""

import math
from typing import Dict, Union
import numpy as np


def validate_image_pair(cover: np.ndarray, stego: np.ndarray) -> None:
    """Validate that two image arrays are compatible for quality metric comparison."""
    if not isinstance(cover, np.ndarray) or not isinstance(stego, np.ndarray):
        raise TypeError("Both cover and stego inputs must be numpy ndarrays.")
    if cover.shape != stego.shape:
        raise ValueError(
            f"Image dimensions must match: cover shape {cover.shape} != stego shape {stego.shape}."
        )
    if cover.size == 0:
        raise ValueError("Image arrays cannot be empty.")


def calculate_mse(cover: np.ndarray, stego: np.ndarray) -> float:
    """Calculate the Mean Squared Error (MSE) between cover and stego image arrays.

    Formula:
        MSE = (1 / N) * sum((cover - stego) ** 2)

    Args:
        cover: Original unmodified image array (uint8 or float).
        stego: Modified stego image array with identical shape.

    Returns:
        MSE as a non-negative float. Returns 0.0 for identical images.
    """
    validate_image_pair(cover, stego)
    # Convert to float64 to prevent uint8 overflow/underflow during subtraction
    cover_f = cover.astype(np.float64)
    stego_f = stego.astype(np.float64)
    err = np.mean((cover_f - stego_f) ** 2)
    return float(err)


def calculate_psnr(
    cover: np.ndarray,
    stego: np.ndarray,
    max_val: float = 255.0
) -> float:
    """Calculate the Peak Signal-to-Noise Ratio (PSNR) in decibels (dB).

    Formula:
        PSNR = 10 * log10(max_val^2 / MSE)

    Educational Note for Students:
    When an image is unmodified (MSE == 0), the ratio approaches infinity (float('inf')).
    In steganography, spatial LSB embedding typically achieves PSNR values between
    48 dB and 65 dB depending on payload density.

    Args:
        cover: Original image array.
        stego: Stego image array.
        max_val: Dynamic range of pixel values (default 255.0 for standard 8-bit channels).

    Returns:
        PSNR in dB, or float('inf') if images are bit-for-bit identical.
    """
    mse = calculate_mse(cover, stego)
    if mse == 0.0:
        return float("inf")
    
    psnr = 10.0 * math.log10((max_val ** 2) / mse)
    return float(psnr)


def calculate_ssim(
    cover: np.ndarray,
    stego: np.ndarray,
    k1: float = 0.01,
    k2: float = 0.03,
    l_val: float = 255.0
) -> float:
    """Calculate global Structural Similarity Index (SSIM) between cover and stego images.

    Educational Note:
    MSE and PSNR evaluate absolute pixel differences, whereas SSIM assesses human
    visual perception of structural changes, luminance, and contrast.

    Formula:
        SSIM = ((2 * mu_x * mu_y + C1) * (2 * sigma_xy + C2)) /
               ((mu_x^2 + mu_y^2 + C1) * (sigma_x^2 + sigma_y^2 + C2))

    Args:
        cover: Original image array.
        stego: Stego image array.
        k1: Stability constant 1 (default 0.01).
        k2: Stability constant 2 (default 0.03).
        l_val: Dynamic range (default 255.0 for 8-bit).

    Returns:
        SSIM float in range [-1.0, 1.0]. Returns 1.0 for identical images.
    """
    validate_image_pair(cover, stego)

    c1 = (k1 * l_val) ** 2
    c2 = (k2 * l_val) ** 2

    cover_f = cover.astype(np.float64)
    stego_f = stego.astype(np.float64)

    # For multi-channel images (e.g. RGB), compute per channel and average
    if cover_f.ndim == 3:
        channels = cover_f.shape[2]
        ssim_per_channel = []
        for ch in range(channels):
            x = cover_f[:, :, ch]
            y = stego_f[:, :, ch]

            mu_x = np.mean(x)
            mu_y = np.mean(y)
            var_x = np.var(x)
            var_y = np.var(y)
            cov_xy = np.cov(x.ravel(), y.ravel())[0, 1] if x.size > 1 else 0.0

            numerator = (2 * mu_x * mu_y + c1) * (2 * cov_xy + c2)
            denominator = (mu_x ** 2 + mu_y ** 2 + c1) * (var_x + var_y + c2)

            ssim_per_channel.append(numerator / denominator)

        return float(np.mean(ssim_per_channel))

    # Grayscale 2D array
    mu_x = np.mean(cover_f)
    mu_y = np.mean(stego_f)
    var_x = np.var(cover_f)
    var_y = np.var(stego_f)
    cov_xy = np.cov(cover_f.ravel(), stego_f.ravel())[0, 1] if cover_f.size > 1 else 0.0

    numerator = (2 * mu_x * mu_y + c1) * (2 * cov_xy + c2)
    denominator = (mu_x ** 2 + mu_y ** 2 + c1) * (var_x + var_y + c2)

    return float(numerator / denominator)


def evaluate_image_quality(
    cover: np.ndarray,
    stego: np.ndarray
) -> Dict[str, Union[float, str]]:
    """Compute all media fidelity metrics comparing cover to stego image.

    Returns:
        Dictionary containing 'mse', 'psnr', 'ssim', and human-readable 'psnr_formatted'.
    """
    mse = calculate_mse(cover, stego)
    psnr = calculate_psnr(cover, stego)
    ssim = calculate_ssim(cover, stego)

    return {
        "mse": round(mse, 6),
        "psnr": psnr if math.isinf(psnr) else round(psnr, 4),
        "psnr_display": "Infinity (Identical)" if math.isinf(psnr) else f"{round(psnr, 2)} dB",
        "ssim": round(ssim, 6),
    }


# ---------------------------------------------------------
# Audio Quality & Distortion Metrics (Phase 4)
# ---------------------------------------------------------

def validate_audio_pair(cover: np.ndarray, stego: np.ndarray) -> None:
    """Validate that two audio sample arrays are compatible for distortion comparison.

    Args:
        cover: Original cover audio samples as a 1D or 2D NumPy array.
        stego: Stego audio samples as a NumPy array with identical shape.

    Raises:
        TypeError: If either input is not a NumPy array.
        ValueError: If array shapes do not match or arrays are empty.
    """
    if not isinstance(cover, np.ndarray) or not isinstance(stego, np.ndarray):
        raise TypeError("Both cover and stego audio inputs must be numpy ndarrays.")
    if cover.shape != stego.shape:
        raise ValueError(
            f"Audio sample dimensions must match: cover shape {cover.shape} != stego shape {stego.shape}."
        )
    if cover.size == 0:
        raise ValueError("Audio sample arrays cannot be empty.")


def calculate_audio_mse(
    cover: np.ndarray,
    stego: np.ndarray,
    sampwidth: int = 2
) -> float:
    """Calculate Mean Squared Error (MSE) between normalized cover and stego audio samples.

    Educational Note for Students:
    Audio samples are normalized to the range [-1.0, 1.0] before computing MSE so that
    distortion measurements are invariant to sample width (e.g. 8-bit vs. 16-bit PCM).
    For 16-bit signed PCM, samples in [-32768, 32767] are divided by 32768.0.
    For 8-bit unsigned PCM, samples in [0, 255] are shifted and scaled via (x - 128) / 128.0.

    Formula:
        MSE = (1 / N) * sum((cover_norm[n] - stego_norm[n]) ** 2)

    Args:
        cover: Original cover audio samples array.
        stego: Stego audio samples array.
        sampwidth: Bytes per sample (1 for 8-bit PCM, 2 for 16-bit PCM).

    Returns:
        Non-negative float MSE. Returns 0.0 for identical audio.
    """
    validate_audio_pair(cover, stego)

    if sampwidth == 2:
        cover_norm = cover.astype(np.float64) / 32768.0
        stego_norm = stego.astype(np.float64) / 32768.0
    elif sampwidth == 1:
        cover_norm = (cover.astype(np.float64) - 128.0) / 128.0
        stego_norm = (stego.astype(np.float64) - 128.0) / 128.0
    else:
        # Default fallback to peak amplitude normalization
        max_possible = float(2 ** (sampwidth * 8 - 1)) if sampwidth > 0 else 1.0
        cover_norm = cover.astype(np.float64) / max_possible
        stego_norm = stego.astype(np.float64) / max_possible

    err = np.mean((cover_norm - stego_norm) ** 2)
    return float(err)


def calculate_audio_snr(
    cover: np.ndarray,
    stego: np.ndarray
) -> float:
    """Calculate the Signal-to-Noise Ratio (SNR) in decibels (dB) between cover and stego audio.

    Educational Note for Students:
    In audio steganography, the original audio signal is treated as the 'signal' and the
    difference introduced by steganographic bit substitution is treated as the 'noise' (error):
        Signal: s[n] = cover[n]
        Noise:  e[n] = cover[n] - stego[n]

    Formula:
        P_signal = (1 / N) * sum(s[n] ** 2)
        P_noise  = (1 / N) * sum(e[n] ** 2)
        SNR (dB) = 10 * log10(P_signal / P_noise)

    Scientific Caution:
    SNR is a physical fidelity measurement of signal energy relative to distortion energy.
    A high SNR (e.g. > 60 dB) indicates low physical perturbation, but it does NOT guarantee
    inaudibility under all listening conditions (psychoacoustic masking is not modeled by SNR),
    nor does it prove resistance against statistical or machine-learning audio steganalysis.

    Args:
        cover: Original cover audio samples array.
        stego: Stego audio samples array.

    Returns:
        SNR in dB as a float, or float('inf') if cover and stego are identical.
    """
    validate_audio_pair(cover, stego)

    cover_f = cover.astype(np.float64)
    stego_f = stego.astype(np.float64)
    noise_f = cover_f - stego_f

    noise_power = np.mean(noise_f ** 2)
    if noise_power == 0.0:
        return float("inf")

    signal_power = np.mean(cover_f ** 2)
    if signal_power == 0.0:
        # Cover audio is completely silent
        return float("-inf")

    snr = 10.0 * math.log10(signal_power / noise_power)
    return float(snr)


def evaluate_audio_quality(
    cover: np.ndarray,
    stego: np.ndarray,
    sampwidth: int = 2
) -> Dict[str, Union[float, str]]:
    """Compute standard audio distortion and fidelity metrics comparing cover to stego audio.

    Args:
        cover: Original cover audio samples.
        stego: Stego audio samples.
        sampwidth: Bytes per sample (1 or 2).

    Returns:
        Dictionary containing 'mse', 'snr', and human-readable 'snr_display'.
    """
    mse = calculate_audio_mse(cover, stego, sampwidth=sampwidth)
    snr = calculate_audio_snr(cover, stego)

    return {
        "mse": round(mse, 8),
        "snr": snr if math.isinf(snr) else round(snr, 4),
        "snr_display": "Infinity (Identical)" if math.isinf(snr) else f"{round(snr, 2)} dB"
    }


# ---------------------------------------------------------
# Video Quality Metrics (Phase 5)
# ---------------------------------------------------------

def validate_video_frame_pairs(
    cover_frames: list,
    stego_frames: list
) -> None:
    """Validate that two lists of video frames are compatible for distortion evaluation."""
    if not isinstance(cover_frames, (list, tuple)) or not isinstance(stego_frames, (list, tuple)):
        raise TypeError("Both cover_frames and stego_frames must be lists or tuples of numpy arrays.")
    if len(cover_frames) != len(stego_frames):
        raise ValueError(
            f"Video frame counts must match: cover has {len(cover_frames)} frames, "
            f"stego has {len(stego_frames)} frames."
        )
    if len(cover_frames) == 0:
        raise ValueError("Video frame lists cannot be empty.")

    for idx, (c_frame, s_frame) in enumerate(zip(cover_frames, stego_frames)):
        if not isinstance(c_frame, np.ndarray) or not isinstance(s_frame, np.ndarray):
            raise TypeError(f"Frame at index {idx} must be a numpy ndarray.")
        if c_frame.shape != s_frame.shape:
            raise ValueError(
                f"Frame dimensions at index {idx} must match: cover {c_frame.shape} != stego {s_frame.shape}."
            )


def calculate_video_metrics(
    cover_frames: list,
    stego_frames: list
) -> Dict[str, Union[float, str, int]]:
    """Calculate objective video distortion metrics across all frames.

    Scientific Caution for Cybersecurity Research:
    Average frame MSE and PSNR measure spatial pixel-level fidelity relative to the cover video.
    A high PSNR (> 50 dB) confirms low perceptual distortion, but does NOT prove resistance
    against statistical or machine-learning video steganalysis (e.g. inter-frame temporal
    motion vector analysis, residual difference classification).

    Args:
        cover_frames: List of original video frames (BGR/RGB uint8 arrays).
        stego_frames: List of stego video frames with identical count and dimensions.

    Returns:
        Dictionary containing:
        - 'average_mse': Mean squared error averaged across all frames.
        - 'average_psnr': Peak Signal-to-Noise Ratio in dB across all frames.
        - 'psnr_display': Formatted display string ('XX.XX dB' or 'Infinity (Identical)').
        - 'total_frames': Total number of frames in the video.
        - 'modified_frames': Number of frames that were altered during embedding.
    """
    validate_video_frame_pairs(cover_frames, stego_frames)

    frame_mses = []
    modified_count = 0

    for c_frame, s_frame in zip(cover_frames, stego_frames):
        c_f = c_frame.astype(np.float64)
        s_f = s_frame.astype(np.float64)
        f_mse = float(np.mean((c_f - s_f) ** 2))
        frame_mses.append(f_mse)
        if f_mse > 0.0:
            modified_count += 1

    total_frames = len(cover_frames)
    avg_mse = float(np.mean(frame_mses))

    if avg_mse == 0.0:
        avg_psnr = float("inf")
        psnr_display = "Infinity (Identical)"
    else:
        avg_psnr = 10.0 * math.log10((255.0 ** 2) / avg_mse)
        psnr_display = f"{round(avg_psnr, 2)} dB"

    return {
        "average_mse": round(avg_mse, 8),
        "average_psnr": avg_psnr if math.isinf(avg_psnr) else round(avg_psnr, 4),
        "psnr_display": psnr_display,
        "total_frames": total_frames,
        "modified_frames": modified_count
    }
