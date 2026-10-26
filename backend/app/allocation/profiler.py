"""Carrier profiling and feature extraction for multimodal steganography.

This module inspects candidate cover carriers (Image, Audio, Video) to determine:
1. Usable steganographic capacity, strictly accounting for binary framing overhead.
2. Domain-specific media statistics and complexity features:
   - Image: Laplacian variance (edge texture complexity), pixel intensity mean/std, edge density.
   - Audio: RMS energy, sample difference variance, dynamic range, duration.
   - Video: Inter-frame difference variance (temporal motion), average keyframe texture, FPS.

Scientific & Methodological Notice:
----------------------------------
Texture complexity, acoustic energy, and temporal motion are classical proxies for
Human Visual System (HVS) and Human Auditory System (HAS) masking thresholds. Regions with
high spatial variance or dynamic motion can absorb subtle LSB modifications with lower visual
noticeability.

CRITICAL LIMITATION:
High texture variance, RMS energy, or temporal motion does NOT guarantee immunity to
machine-learning or statistical steganalysis. Modern steganalysis classifiers (e.g., SRM,
Sample Pair Analysis, optical flow residual models) detect statistical distribution shifts
and co-occurrence deviations rather than visual artifacts. These profiling metrics serve
as relative complexity indicators for rate-distortion heuristic allocation, not proof of
undetectability.
"""

from dataclasses import asdict, dataclass
import io
import math
from typing import Any, Dict, List, Optional, Tuple, Union
import cv2
import numpy as np

from app.media.image_stego import (
    load_image_as_rgb_array,
    get_image_capacity,
    FRAME_HEADER_SIZE as IMAGE_FRAME_HEADER_SIZE,
    UnsupportedImageFormatError,
)
from app.media.audio_stego import (
    load_wav_audio,
    get_audio_capacity,
    FRAME_HEADER_SIZE as AUDIO_FRAME_HEADER_SIZE,
    UnsupportedAudioFormatError,
)
from app.media.video_stego import (
    load_video_from_bytes,
    get_video_capacity,
    FRAME_HEADER_SIZE as VIDEO_FRAME_HEADER_SIZE,
    UnsupportedVideoFormatError,
)


class ProfilingError(Exception):
    """Base exception for carrier profiling failures."""
    pass


class InvalidCarrierError(ProfilingError):
    """Raised when an input file cannot be parsed or lacks carrier properties."""
    pass


@dataclass(frozen=True)
class ImageProfile:
    """Quantitative features and capacity profile of a candidate cover image.

    Attributes:
        carrier_type: Always 'image'.
        width: Image width in pixels.
        height: Image height in pixels.
        channels: Channel count (RGB = 3, RGBA = 4).
        color_mode: Original color mode (RGB, RGBA, etc.).
        total_carrier_bytes: Raw bit count divided by 8.
        header_overhead_bytes: 14-byte PSTG framing overhead.
        max_usable_payload_bytes: Usable payload capacity in bytes.
        laplacian_variance: Variance of the Laplacian operator on grayscale image.
            Higher values indicate rich high-frequency edge texture.
        mean_intensity: Average pixel value across all RGB channels (0-255).
        std_intensity: Standard deviation of pixel values across RGB channels.
        edge_density: Proportion of pixels whose gradient magnitude exceeds threshold.
        complexity_score: Normalized complexity indicator in [0.0, 1.0].
    """
    carrier_type: str
    width: int
    height: int
    channels: int
    color_mode: str
    total_carrier_bytes: int
    header_overhead_bytes: int
    max_usable_payload_bytes: int
    laplacian_variance: float
    mean_intensity: float
    std_intensity: float
    edge_density: float
    complexity_score: float

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class AudioProfile:
    """Quantitative features and capacity profile of a candidate cover audio file.

    Attributes:
        carrier_type: Always 'audio'.
        sample_rate: Audio sampling frequency in Hz (e.g. 44100).
        bits_per_sample: Bit depth per sample (8 or 16).
        num_channels: Channel count (1 for Mono, 2 for Stereo).
        channel_layout: Descriptive string ('Mono' or 'Stereo').
        total_samples: Total number of PCM audio samples across all channels.
        duration_seconds: Playback duration in seconds.
        total_carrier_bytes: Total sample count divided by 8.
        header_overhead_bytes: 14-byte WSTG framing overhead.
        max_usable_payload_bytes: Usable payload capacity in bytes.
        rms_energy: Root Mean Square of normalized audio samples in [0.0, 1.0].
        sample_diff_variance: Variance of successive sample differences.
            Higher values indicate rapid acoustic fluctuations / percussive content.
        mean_abs_diff: Mean absolute difference between successive samples.
        complexity_score: Normalized complexity indicator in [0.0, 1.0].
    """
    carrier_type: str
    sample_rate: int
    bits_per_sample: int
    num_channels: int
    channel_layout: str
    total_samples: int
    duration_seconds: float
    total_carrier_bytes: int
    header_overhead_bytes: int
    max_usable_payload_bytes: int
    rms_energy: float
    sample_diff_variance: float
    mean_abs_diff: float
    complexity_score: float

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class VideoProfile:
    """Quantitative features and capacity profile of a candidate cover video file.

    Attributes:
        carrier_type: Always 'video'.
        width: Frame width in pixels.
        height: Frame height in pixels.
        num_frames: Total number of video frames.
        fps: Playback frame rate in frames per second.
        duration_seconds: Video duration in seconds.
        recommended_codec: Lossless codec string (e.g. 'FFV1').
        container_format: Container extension ('AVI' or 'MKV').
        total_carrier_bytes: Total carrier subpixels divided by 8.
        header_overhead_bytes: 14-byte VSTG framing overhead.
        max_usable_payload_bytes: Usable payload capacity in bytes.
        frame_diff_variance: Average variance of inter-frame differences.
            Higher values indicate significant temporal scene motion.
        keyframe_laplacian_variance: Average Laplacian variance across keyframes.
        complexity_score: Normalized complexity indicator in [0.0, 1.0].
    """
    carrier_type: str
    width: int
    height: int
    num_frames: int
    fps: float
    duration_seconds: float
    recommended_codec: str
    container_format: str
    total_carrier_bytes: int
    header_overhead_bytes: int
    max_usable_payload_bytes: int
    frame_diff_variance: float
    keyframe_laplacian_variance: float
    complexity_score: float

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class MultimodalTriadProfile:
    """Consolidated profiles for all three cover carriers in the multimodal triad.

    Attributes:
        image: ImageProfile instance.
        audio: AudioProfile instance.
        video: VideoProfile instance.
        total_usable_capacity_bytes: Sum of max_usable_payload_bytes across all three carriers.
        capacity_shares: Normalized proportion of usable capacity per carrier.
    """
    image: ImageProfile
    audio: AudioProfile
    video: VideoProfile
    total_usable_capacity_bytes: int
    capacity_shares: Dict[str, float]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "image": self.image.to_dict(),
            "audio": self.audio.to_dict(),
            "video": self.video.to_dict(),
            "total_usable_capacity_bytes": self.total_usable_capacity_bytes,
            "capacity_shares": self.capacity_shares,
        }


def profile_image_carrier(image_input: Union[bytes, np.ndarray]) -> ImageProfile:
    """Inspect and profile a candidate image cover carrier.

    Extracts:
    1. Spatial dimensions, channels, and usable LSB capacity.
    2. Laplacian variance as an indicator of spatial high-frequency texture.
    3. Pixel intensity statistics (mean, standard deviation).
    4. Edge pixel density via Sobel magnitude thresholding.
    5. Relative complexity score scaled sigmoidally into [0.05, 1.0].

    Args:
        image_input: Raw image bytes or existing NumPy uint8 RGB array.

    Returns:
        Validated ImageProfile dataclass.

    Raises:
        InvalidCarrierError: If image cannot be decoded or has unsupported format.
    """
    try:
        img_array, mode = load_image_as_rgb_array(image_input)
    except (UnsupportedImageFormatError, Exception) as e:
        raise InvalidCarrierError(f"Image profiling failed: {str(e)}") from e

    h, w, c = img_array.shape
    total_carrier_bytes = (h * w * 3) // 8
    max_usable = max(0, total_carrier_bytes - IMAGE_FRAME_HEADER_SIZE)

    # Convert RGB to grayscale for spatial gradient calculations
    # Using standard ITU-R 601-2 luma weights: Y = 0.299R + 0.587G + 0.114B
    gray = cv2.cvtColor(img_array[:, :, :3], cv2.COLOR_RGB2GRAY)

    # 1. Laplacian variance: Var(∇² I)
    laplacian = cv2.Laplacian(gray, cv2.CV_64F)
    lap_var = float(laplacian.var())

    # 2. Pixel intensity mean and standard deviation
    mean_val = float(np.mean(gray))
    std_val = float(np.std(gray))

    # 3. Edge density: proportion of pixels with high Sobel gradient magnitude
    sobelx = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
    sobely = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
    grad_mag = np.hypot(sobelx, sobely)
    # Threshold at 50 gradient units
    edge_pixels = np.count_nonzero(grad_mag > 50.0)
    edge_density = float(edge_pixels / (h * w))

    # 4. Normalized complexity score in [0.05, 1.0] using smooth logarithmic scaling
    # Laplacian variance of smooth images ~ 10-50; textured images ~ 200-2000+
    log_lap = math.log10(max(1.0, lap_var))
    # Map log10(1) = 0 to 0.1, log10(1000) = 3 to 0.9
    raw_score = 1.0 / (1.0 + math.exp(-1.5 * (log_lap - 2.0)))
    complexity_score = round(max(0.05, min(1.0, raw_score)), 4)

    return ImageProfile(
        carrier_type="image",
        width=w,
        height=h,
        channels=c,
        color_mode=mode,
        total_carrier_bytes=total_carrier_bytes,
        header_overhead_bytes=IMAGE_FRAME_HEADER_SIZE,
        max_usable_payload_bytes=max_usable,
        laplacian_variance=round(lap_var, 2),
        mean_intensity=round(mean_val, 2),
        std_intensity=round(std_val, 2),
        edge_density=round(edge_density, 4),
        complexity_score=complexity_score,
    )


def profile_audio_carrier(audio_input: Union[bytes, bytearray, io.BytesIO]) -> AudioProfile:
    """Inspect and profile a candidate WAV audio cover carrier.

    Extracts:
    1. Sample rate, bit depth, channel count, duration, and usable LSB capacity.
    2. RMS energy of the normalized audio waveform in [0.0, 1.0].
    3. Successive sample difference statistics (variance and mean absolute difference).
    4. Relative complexity score scaled into [0.05, 1.0].

    Args:
        audio_input: Raw WAV file bytes or stream.

    Returns:
        Validated AudioProfile dataclass.

    Raises:
        InvalidCarrierError: If audio cannot be decoded or is not uncompressed PCM WAV.
    """
    try:
        samples, params = load_wav_audio(audio_input)
    except (UnsupportedAudioFormatError, Exception) as e:
        raise InvalidCarrierError(f"Audio profiling failed: {str(e)}") from e

    total_samples = len(samples)
    total_carrier_bytes = total_samples // 8
    max_usable = max(0, total_carrier_bytes - AUDIO_FRAME_HEADER_SIZE)

    # Normalize samples to float64 in [-1.0, 1.0]
    sample_width = int(params["sample_width"])
    if sample_width == 2:
        norm_samples = samples.astype(np.float64) / 32768.0
    else:  # uint8: 0..255 -> -1.0..1.0
        norm_samples = (samples.astype(np.float64) - 128.0) / 128.0

    # 1. RMS Energy: sqrt( mean( s(t)^2 ) )
    rms_energy = float(np.sqrt(np.mean(norm_samples ** 2)))

    # 2. First-order sample differences: Δs(t) = s(t) - s(t-1)
    if len(norm_samples) > 1:
        diffs = np.diff(norm_samples)
        diff_var = float(np.var(diffs))
        mean_abs_diff = float(np.mean(np.abs(diffs)))
    else:
        diff_var = 0.0
        mean_abs_diff = 0.0

    # 3. Normalized complexity score in [0.05, 1.0]
    # High dynamic fluctuations and percussive/noise content yield higher difference variance
    # Pure tones or quiet speech have small diff variance (< 1e-4); drums/noise > 1e-2
    log_diff = math.log10(max(1e-7, diff_var))
    # Map log10(1e-4) = -4 to 0.4, log10(1e-2) = -2 to 0.85
    raw_score = 1.0 / (1.0 + math.exp(-1.2 * (log_diff - (-3.5))))
    complexity_score = round(max(0.05, min(1.0, raw_score)), 4)

    return AudioProfile(
        carrier_type="audio",
        sample_rate=int(params["sample_rate"]),
        bits_per_sample=int(params["bits_per_sample"]),
        num_channels=int(params["num_channels"]),
        channel_layout=str(params["channel_layout"]),
        total_samples=total_samples,
        duration_seconds=float(params["duration_seconds"]),
        total_carrier_bytes=total_carrier_bytes,
        header_overhead_bytes=AUDIO_FRAME_HEADER_SIZE,
        max_usable_payload_bytes=max_usable,
        rms_energy=round(rms_energy, 4),
        sample_diff_variance=round(diff_var, 6),
        mean_abs_diff=round(mean_abs_diff, 6),
        complexity_score=complexity_score,
    )


def profile_video_carrier(
    video_input: bytes,
    max_sample_frames: int = 30
) -> VideoProfile:
    """Inspect and profile a candidate video cover carrier.

    Extracts:
    1. Spatial dimensions, frame count, FPS, duration, and usable LSB capacity.
    2. Inter-frame difference variance across sampled frame transitions (motion indicator).
    3. Keyframe Laplacian variance (spatial texture indicator).
    4. Relative complexity score scaled into [0.05, 1.0].

    Args:
        video_input: Raw video file bytes.
        max_sample_frames: Maximum number of frames to inspect for temporal statistics
            (ensures fast, deterministic profiling even for long video streams).

    Returns:
        Validated VideoProfile dataclass.

    Raises:
        InvalidCarrierError: If video cannot be decoded or lacks decodable frames.
    """
    try:
        frames, meta = load_video_from_bytes(video_input)
    except (UnsupportedVideoFormatError, Exception) as e:
        raise InvalidCarrierError(f"Video profiling failed: {str(e)}") from e

    w = int(meta["width"])
    h = int(meta["height"])
    num_frames = int(meta["num_frames"])
    fps = float(meta["fps"])
    duration = float(meta["duration_seconds"])

    total_carrier_bits = num_frames * w * h * 3
    total_carrier_bytes = total_carrier_bits // 8
    max_usable = max(0, (total_carrier_bits - (VIDEO_FRAME_HEADER_SIZE * 8)) // 8)

    # Sample frame indices evenly
    if num_frames <= max_sample_frames:
        sample_indices = list(range(num_frames))
    else:
        sample_indices = np.linspace(0, num_frames - 1, max_sample_frames, dtype=int).tolist()

    sampled_frames = [frames[i] for i in sample_indices]

    # 1. Keyframe Laplacian variances
    lap_vars = []
    for f in sampled_frames:
        gray_f = cv2.cvtColor(f, cv2.COLOR_BGR2GRAY)
        lap_vars.append(float(cv2.Laplacian(gray_f, cv2.CV_64F).var()))
    avg_lap_var = float(np.mean(lap_vars)) if lap_vars else 0.0

    # 2. Inter-frame differences (temporal motion)
    frame_diff_vars = []
    for i in range(1, len(sampled_frames)):
        prev_gray = cv2.cvtColor(sampled_frames[i - 1], cv2.COLOR_BGR2GRAY).astype(np.float64)
        curr_gray = cv2.cvtColor(sampled_frames[i], cv2.COLOR_BGR2GRAY).astype(np.float64)
        diff = curr_gray - prev_gray
        frame_diff_vars.append(float(np.var(diff)))

    avg_frame_diff_var = float(np.mean(frame_diff_vars)) if frame_diff_vars else 0.0

    # 3. Normalized complexity score in [0.05, 1.0] combining motion & spatial texture
    # Static video has diff_var near 0; high motion has diff_var > 100
    log_motion = math.log10(max(1e-2, avg_frame_diff_var))
    motion_score = 1.0 / (1.0 + math.exp(-1.0 * (log_motion - 1.0)))

    log_tex = math.log10(max(1.0, avg_lap_var))
    tex_score = 1.0 / (1.0 + math.exp(-1.5 * (log_tex - 2.0)))

    # Weighted blend: 60% temporal motion dynamism + 40% spatial detail
    blended = 0.60 * motion_score + 0.40 * tex_score
    complexity_score = round(max(0.05, min(1.0, blended)), 4)

    return VideoProfile(
        carrier_type="video",
        width=w,
        height=h,
        num_frames=num_frames,
        fps=fps,
        duration_seconds=duration,
        recommended_codec=str(meta.get("fourcc", "FFV1")),
        container_format="AVI",
        total_carrier_bytes=total_carrier_bytes,
        header_overhead_bytes=VIDEO_FRAME_HEADER_SIZE,
        max_usable_payload_bytes=max_usable,
        frame_diff_variance=round(avg_frame_diff_var, 2),
        keyframe_laplacian_variance=round(avg_lap_var, 2),
        complexity_score=complexity_score,
    )


def profile_multimodal_triad(
    image_input: Union[bytes, np.ndarray],
    audio_input: Union[bytes, bytearray, io.BytesIO],
    video_input: bytes
) -> MultimodalTriadProfile:
    """Simultaneously inspect and profile all three candidate carriers in the multimodal triad.

    Args:
        image_input: Image carrier bytes or array.
        audio_input: Audio carrier bytes or stream.
        video_input: Video carrier bytes.

    Returns:
        MultimodalTriadProfile consolidating individual carrier profiles,
        total usable capacity, and normalized capacity shares.

    Raises:
        InvalidCarrierError: If any of the three carriers fails validation.
    """
    img_prof = profile_image_carrier(image_input)
    aud_prof = profile_audio_carrier(audio_input)
    vid_prof = profile_video_carrier(video_input)

    total_cap = (
        img_prof.max_usable_payload_bytes +
        aud_prof.max_usable_payload_bytes +
        vid_prof.max_usable_payload_bytes
    )

    if total_cap > 0:
        shares = {
            "image": round(img_prof.max_usable_payload_bytes / total_cap, 4),
            "audio": round(aud_prof.max_usable_payload_bytes / total_cap, 4),
            "video": round(vid_prof.max_usable_payload_bytes / total_cap, 4),
        }
    else:
        shares = {"image": 0.0, "audio": 0.0, "video": 0.0}

    return MultimodalTriadProfile(
        image=img_prof,
        audio=aud_prof,
        video=vid_prof,
        total_usable_capacity_bytes=total_cap,
        capacity_shares=shares,
    )
