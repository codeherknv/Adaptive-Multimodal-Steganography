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
