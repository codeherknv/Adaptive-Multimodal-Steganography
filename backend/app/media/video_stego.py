"""Video Steganography module using OpenCV and Lossless Codecs.

This module implements deterministic, length-prefixed LSB embedding and extraction
for video carriers using OpenCV (`cv2`) and lossless video codecs (e.g. FFV1 in AVI/MKV).

Key Architectural Guarantees for Cybersecurity Research:
1. Lossless Video Encoding:
   - Lossy codecs (such as H.264/AVC, H.265/HEVC, MPEG-4, VP9) employ lossy discrete
     cosine transforms (DCT) or wavelet quantization that discard high-frequency details
     and completely destroy spatial LSB modifications.
   - This implementation defaults to FFV1 (Fast Forward Video Codec 1, IETF RFC 9043)
     or HuffYUV (HFYU) in an AVI container, ensuring 100% mathematical bit-exactness
     across every frame and channel.
2. Codec Availability Check & Fallback:
   - Does not assume all codecs are present. Dynamically tests codec availability
     using cv2.VideoWriter and provides descriptive feedback if an environment lacks
     a required lossless encoder.
3. Explicit Binary Framing (14 Bytes Header):
   - Magic Signature (4 bytes): b"VSTG" (Video Stego) - distinct from b"PSTG" and b"WSTG".
   - Format Version (1 byte): 0x01
   - Reserved (1 byte): 0x00
   - Payload Length (4 bytes uint32 big-endian)
   - Payload CRC32 (4 bytes uint32 big-endian)
   - Followed by exactly L bytes of embedded payload.
4. Container & Video Parameter Preservation:
   - Preserves video resolution (width x height), frame rate (FPS), and frame count.
5. Objective Fidelity Metrics:
   - Evaluates Mean Squared Error (MSE) and Peak Signal-to-Noise Ratio (PSNR) across frames.
   - High PSNR demonstrates pixel-level fidelity, but does NOT prove resistance against
     statistical or machine-learning video steganalysis (e.g. motion vector analysis or
     inter-frame residual statistics).
"""

import io
import math
import os
import struct
import tempfile
import zlib
from typing import Dict, List, Optional, Tuple, Union

import cv2
import numpy as np

from app.evaluation.quality_metrics import calculate_video_metrics

# Video Framing Constants
VIDEO_MAGIC = b"VSTG"
VIDEO_FORMAT_VERSION = 1
FRAME_HEADER_FORMAT = ">4sBBII"
FRAME_HEADER_SIZE = struct.calcsize(FRAME_HEADER_FORMAT)  # 14 bytes (112 bits)

# Candidate lossless video codecs to test in order of preference
CANDIDATE_LOSSLESS_CODECS = [
    ("FFV1", ".avi"),
    ("FFV1", ".mkv"),
    ("HFYU", ".avi"),
]


class VideoStegoError(Exception):
    """Base exception for video steganography errors."""
    pass


class InsufficientCapacityError(VideoStegoError):
    """Raised when the carrier video cannot hold the requested payload."""
    pass


class CarrierExtractionError(VideoStegoError):
    """Raised when extraction fails (bad signature, corrupt CRC, or truncated video)."""
    pass


class UnsupportedVideoFormatError(VideoStegoError):
    """Raised when the input video format or container is unsupported or corrupted."""
    pass


class CodecUnavailableError(VideoStegoError):
    """Raised when no suitable lossless video encoder is available in OpenCV."""
    pass


# Global cached codec detection result
_CACHED_LOSSLESS_CODEC: Optional[Tuple[str, str]] = None


def detect_available_lossless_codec() -> Tuple[str, str]:
    """Probe the OpenCV FFmpeg backend to find an operational lossless video codec.

    Returns:
        Tuple of (fourcc_string, container_extension), e.g. ("FFV1", ".avi").

    Raises:
        CodecUnavailableError: If no supported lossless codec can be opened by VideoWriter.
    """
    global _CACHED_LOSSLESS_CODEC
    if _CACHED_LOSSLESS_CODEC is not None:
        return _CACHED_LOSSLESS_CODEC

    test_w, test_h = 32, 32
    dummy_frame = np.zeros((test_h, test_w, 3), dtype=np.uint8)

    for fourcc_str, ext in CANDIDATE_LOSSLESS_CODECS:
        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tf:
            tmp_path = tf.name

        try:
            fourcc = cv2.VideoWriter_fourcc(*fourcc_str)
            writer = cv2.VideoWriter(tmp_path, fourcc, 10.0, (test_w, test_h))
            if not writer.isOpened():
                continue
            writer.write(dummy_frame)
            writer.release()

            # Verify readability
            cap = cv2.VideoCapture(tmp_path)
            if not cap.isOpened():
                continue
            ret, read_frame = cap.read()
            cap.release()

            if ret and read_frame is not None and read_frame.shape == dummy_frame.shape:
                if np.array_equal(dummy_frame, read_frame):
                    _CACHED_LOSSLESS_CODEC = (fourcc_str, ext)
                    return _CACHED_LOSSLESS_CODEC
        except Exception:
            continue
        finally:
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass

    raise CodecUnavailableError(
        "No supported lossless video encoder (such as FFV1 or HFYU) is operational in OpenCV. "
        "Lossless video steganography requires an encoder that does not alter pixel values."
    )


def bytes_to_bits(data: bytes) -> np.ndarray:
    """Unpack a byte sequence into a 1D NumPy array of uint8 bits (0 or 1, MSB-first)."""
    if not data:
        return np.empty(0, dtype=np.uint8)
    byte_arr = np.frombuffer(data, dtype=np.uint8)
    return np.unpackbits(byte_arr)


def bits_to_bytes(bits: np.ndarray) -> bytes:
    """Pack a 1D NumPy array of uint8 bits into a byte sequence (MSB-first)."""
    if len(bits) == 0:
        return b""
    if len(bits) % 8 != 0:
        raise ValueError(f"Bit array length ({len(bits)}) must be a multiple of 8.")
    return np.packbits(bits).tobytes()


def pack_stego_frame(payload: bytes) -> bytes:
    """Pack an arbitrary binary payload into a 14-byte length-prefixed VSTG frame.

    Header Format (14 Bytes, Big-Endian):
        Offset 0-3:   Magic bytes b"VSTG"
        Offset 4:     Version 1 (uint8)
        Offset 5:     Reserved 0x00 (uint8)
        Offset 6-9:   Payload length L in bytes (uint32)
        Offset 10-13: IEEE 802.3 CRC32 checksum of payload (uint32)
        Offset 14+:   Payload bytes (L bytes)

    Args:
        payload: Binary data bytes to embed (e.g. Phase 2 encrypted ASTG envelope).

    Returns:
        Full framed binary data (14 + len(payload) bytes).
    """
    payload_len = len(payload)
    checksum = zlib.crc32(payload) & 0xFFFFFFFF
    header = struct.pack(
        FRAME_HEADER_FORMAT,
        VIDEO_MAGIC,
        VIDEO_FORMAT_VERSION,
        0,
        payload_len,
        checksum
    )
    return header + payload


def load_video_from_bytes(
    video_bytes: bytes,
    preferred_ext: str = ".avi"
) -> Tuple[List[np.ndarray], Dict[str, Union[int, float, str]]]:
    """Read a video from raw bytes into an in-memory sequence of BGR frames and metadata.

    Args:
        video_bytes: Raw bytes of the video file.
        preferred_ext: Suggested file extension for temporary disk buffering.

    Returns:
        Tuple of (frames_list, metadata_dict).

    Raises:
        UnsupportedVideoFormatError: If the video cannot be opened or contains no frames.
    """
    if not video_bytes or len(video_bytes) < 32:
        raise UnsupportedVideoFormatError("Uploaded video file is empty or too small to be valid.")

    with tempfile.NamedTemporaryFile(suffix=preferred_ext, delete=False) as tf:
        tf.write(video_bytes)
        tf.flush()
        tmp_path = tf.name

    frames: List[np.ndarray] = []
    metadata: Dict[str, Union[int, float, str]] = {}

    try:
        cap = cv2.VideoCapture(tmp_path)
        if not cap.isOpened():
            raise UnsupportedVideoFormatError(
                "Unable to open video carrier. The format, codec, or container may be unsupported."
            )

        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = float(cap.get(cv2.CAP_PROP_FPS))
        if fps <= 0.0 or math.isnan(fps):
            fps = 25.0  # Fallback default for streams lacking FPS metadata

        fourcc_int = int(cap.get(cv2.CAP_PROP_FOURCC))
        fourcc_str = "".join([chr((fourcc_int >> (8 * i)) & 0xFF) for i in range(4)])

        while True:
            ret, frame = cap.read()
            if not ret or frame is None:
                break
            frames.append(frame)

        cap.release()

        if len(frames) == 0:
            raise UnsupportedVideoFormatError("Video file contains zero decodable frames.")

        num_frames = len(frames)
        duration = round(num_frames / fps, 3)

        metadata = {
            "width": width,
            "height": height,
            "fps": round(fps, 2),
            "num_frames": num_frames,
            "duration_seconds": duration,
            "fourcc": fourcc_str.strip() or "UNKNOWN",
        }
    except UnsupportedVideoFormatError:
        raise
    except Exception as e:
        raise UnsupportedVideoFormatError(f"Error reading video frames: {str(e)}")
    finally:
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass

    return frames, metadata


def save_video_to_bytes(
    frames: List[np.ndarray],
    fps: float,
    width: int,
    height: int,
    fourcc_str: str = "FFV1",
    ext: str = ".avi"
) -> bytes:
    """Encode an in-memory sequence of frames into a lossless video file and return bytes.

    Args:
        frames: List of BGR uint8 numpy arrays.
        fps: Frames per second.
        width: Frame width in pixels.
        height: Frame height in pixels.
        fourcc_str: 4-character FourCC codec string (default "FFV1").
        ext: Container file extension (default ".avi").

    Returns:
        Raw bytes of the encoded video file.

    Raises:
        VideoStegoError: If VideoWriter fails to encode the frames.
    """
    if not frames:
        raise VideoStegoError("Cannot encode empty list of video frames.")

    with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tf:
        tmp_path = tf.name

    try:
        fourcc = cv2.VideoWriter_fourcc(*fourcc_str)
        writer = cv2.VideoWriter(tmp_path, fourcc, fps, (width, height))
        if not writer.isOpened():
            raise CodecUnavailableError(
                f"Failed to initialize VideoWriter with codec '{fourcc_str}' and container '{ext}'."
            )

        for frame in frames:
            writer.write(frame)

        writer.release()

        with open(tmp_path, "rb") as rf:
            encoded_bytes = rf.read()

        if not encoded_bytes:
            raise VideoStegoError("VideoWriter generated an empty video file.")

        return encoded_bytes
    finally:
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass


def frame_to_png_bytes(frame: np.ndarray) -> bytes:
    """Encode a single BGR frame as PNG bytes for UI keyframe preview."""
    success, buffer = cv2.imencode(".png", frame)
    if not success:
        raise VideoStegoError("Failed to encode video frame to PNG preview.")
    return buffer.tobytes()


def get_video_capacity(video_input: bytes) -> Dict[str, Union[int, float, str]]:
    """Inspect a video carrier and compute its maximum usable LSB steganographic payload capacity.

    Each color subpixel (B, G, R) of every frame provides 1 embeddable bit.
    Total carrier bits = num_frames * height * width * 3.
    Usable payload bytes = (total_carrier_bits - 112) // 8.

    Args:
        video_input: Raw video file bytes.

    Returns:
        Dictionary with video dimensions, frame count, FPS, duration, and capacity metrics.
    """
    frames, meta = load_video_from_bytes(video_input)
    width = int(meta["width"])
    height = int(meta["height"])
    num_frames = int(meta["num_frames"])
    fps = float(meta["fps"])
    duration = float(meta["duration_seconds"])

    bits_per_frame = width * height * 3
    total_carrier_bits = num_frames * bits_per_frame
    total_carrier_bytes = total_carrier_bits // 8

    header_bits = FRAME_HEADER_SIZE * 8
    max_usable_payload_bytes = max(0, (total_carrier_bits - header_bits) // 8)

    codec_str, container_ext = detect_available_lossless_codec()

    return {
        "width": width,
        "height": height,
        "channels_per_frame": 3,
        "num_frames": num_frames,
        "fps": fps,
        "duration_seconds": duration,
        "total_carrier_bits": total_carrier_bits,
        "total_carrier_bytes": total_carrier_bytes,
        "header_overhead_bytes": FRAME_HEADER_SIZE,
        "max_usable_payload_bytes": max_usable_payload_bytes,
        "recommended_codec": codec_str,
        "container_format": container_ext.lstrip(".").upper(),
    }


def embed_in_video(
    video_input: bytes,
    payload: bytes
) -> Tuple[bytes, Dict[str, Union[float, str, int]], bytes]:
    """Embed an arbitrary binary payload into a video carrier using spatial LSB substitution.

    Sequential Frame Embedding Algorithm:
    1. Packs payload into a 14-byte length-prefixed VSTG frame (header + payload).
    2. Converts framed bytes into a stream of uint8 bits (MSB-first).
    3. Traverses video frames starting at frame 0, row 0, col 0, BGR channels.
    4. Modifies the LSB of each pixel channel: (pixel & 0xFE) | bit.
    5. Frames beyond the payload boundary remain 100% unaltered.
    6. Encodes stego frames using a lossless codec (e.g. FFV1 in AVI).
    7. Calculates objective video fidelity metrics (average MSE, average PSNR).
    8. Generates a PNG keyframe preview of the first frame for frontend display.

    Args:
        video_input: Raw cover video bytes.
        payload: Binary payload bytes to embed (e.g. Phase 2 encrypted ASTG envelope).

    Returns:
        Tuple of (stego_video_bytes, metrics_dict, preview_png_bytes).

    Raises:
        InsufficientCapacityError: If payload exceeds carrier usable capacity.
        UnsupportedVideoFormatError: If video cannot be read.
        CodecUnavailableError: If no lossless encoder is operational.
    """
    cover_frames, meta = load_video_from_bytes(video_input)
    width = int(meta["width"])
    height = int(meta["height"])
    num_frames = int(meta["num_frames"])
    fps = float(meta["fps"])

    bits_per_frame = width * height * 3
    total_carrier_bits = num_frames * bits_per_frame
    header_bits_count = FRAME_HEADER_SIZE * 8
    max_usable_payload_bytes = max(0, (total_carrier_bits - header_bits_count) // 8)

    if len(payload) > max_usable_payload_bytes:
        raise InsufficientCapacityError(
            f"Payload length ({len(payload)} bytes) exceeds video usable capacity "
            f"({max_usable_payload_bytes} bytes across {num_frames} frames of {width}x{height})."
        )

    # 1. Pack framing header and payload
    framed_data = pack_stego_frame(payload)
    stream_bits = bytes_to_bits(framed_data)
    total_bits_to_embed = len(stream_bits)

    # 2. Embed sequentially across frames
    stego_frames: List[np.ndarray] = []
    bits_embedded = 0

    for frame in cover_frames:
        if bits_embedded >= total_bits_to_embed:
            # All payload bits embedded; subsequent frames remain untouched
            stego_frames.append(frame.copy())
            continue

        stego_frame = frame.copy()
        flat_view = stego_frame.reshape(-1)
        remaining_bits = total_bits_to_embed - bits_embedded
        frame_chunk_bits = min(remaining_bits, len(flat_view))

        bits_chunk = stream_bits[bits_embedded : bits_embedded + frame_chunk_bits]

        # LSB substitution: clear LSB (mask 0xFE) and bitwise-OR with payload bit
        flat_view[:frame_chunk_bits] = (flat_view[:frame_chunk_bits] & 0xFE) | bits_chunk
        bits_embedded += frame_chunk_bits

        stego_frames.append(stego_frame)

    # 3. Calculate objective video fidelity metrics
    raw_metrics = calculate_video_metrics(cover_frames, stego_frames)

    # Calculate capacity utilization
    capacity_used_ratio = round(total_bits_to_embed / total_carrier_bits, 6) if total_carrier_bits > 0 else 0.0

    metrics_dict = {
        "average_mse": raw_metrics["average_mse"],
        "average_psnr": raw_metrics["average_psnr"],
        "psnr_display": raw_metrics["psnr_display"],
        "total_frames": raw_metrics["total_frames"],
        "modified_frames": raw_metrics["modified_frames"],
        "embedded_bytes": len(payload),
        "framed_bytes": len(framed_data),
        "capacity_used_ratio": capacity_used_ratio,
        "width": width,
        "height": height,
        "fps": fps,
        "duration_seconds": meta["duration_seconds"],
    }

    # 4. Save stego frames to lossless video container
    codec_str, ext = detect_available_lossless_codec()
    stego_video_bytes = save_video_to_bytes(
        stego_frames,
        fps=fps,
        width=width,
        height=height,
        fourcc_str=codec_str,
        ext=ext
    )

    # 5. Generate PNG keyframe preview from the first stego frame
    preview_png_bytes = frame_to_png_bytes(stego_frames[0])

    return stego_video_bytes, metrics_dict, preview_png_bytes


def extract_from_video(video_input: bytes) -> bytes:
    """Extract and verify an embedded binary payload from a stego video carrier.

    Extraction Algorithm:
    1. Decodes frames from the stego video.
    2. Extracts the first 112 bits from sequential frames to unpack the 14-byte VSTG header.
    3. Validates the magic signature b"VSTG" and format version 1.
    4. Bounds-checks the declared payload length against the total sample count.
    5. Extracts the subsequent L * 8 payload bits.
    6. Verifies the IEEE 802.3 CRC32 checksum against the header's expected CRC.
    7. Returns the exact recovered payload bytes.

    Args:
        video_input: Stego video file bytes.

    Returns:
        Exact byte-for-byte recovered payload bytes.

    Raises:
        CarrierExtractionError: If magic signature is missing, length exceeds bounds,
                                or CRC32 verification fails.
        UnsupportedVideoFormatError: If video format cannot be decoded.
    """
    stego_frames, meta = load_video_from_bytes(video_input)
    width = int(meta["width"])
    height = int(meta["height"])
    num_frames = int(meta["num_frames"])

    total_samples = num_frames * width * height * 3
    header_bits_count = FRAME_HEADER_SIZE * 8

    if total_samples < header_bits_count:
        raise CarrierExtractionError(
            "Video is too short or small to contain a valid steganographic framing header."
        )

    # Helper generator to yield LSBs across frames sequentially
    def lsb_generator():
        for frame in stego_frames:
            flat = frame.reshape(-1)
            for val in flat:
                yield int(val & 1)

    gen = lsb_generator()

    # 1. Read first 112 bits for framing header
    header_bits = [next(gen) for _ in range(header_bits_count)]
    header_bytes = bits_to_bytes(np.array(header_bits, dtype=np.uint8))

    magic, version, reserved, payload_len, expected_crc = struct.unpack(
        FRAME_HEADER_FORMAT,
        header_bytes[:FRAME_HEADER_SIZE]
    )

    if magic != VIDEO_MAGIC:
        raise CarrierExtractionError(
            f"Invalid video steganography signature: expected {VIDEO_MAGIC!r}, got {magic!r}. "
            "This video does not appear to contain an embedded payload."
        )

    if version != VIDEO_FORMAT_VERSION:
        raise CarrierExtractionError(
            f"Unsupported video stego format version: expected {VIDEO_FORMAT_VERSION}, got {version}."
        )

    # 2. Bounds check on declared payload length
    required_total_bits = header_bits_count + (payload_len * 8)
    if required_total_bits > total_samples:
        raise CarrierExtractionError(
            f"Corrupted video payload header: declared length of {payload_len} bytes requires "
            f"{required_total_bits} carrier bits, but video only contains {total_samples} bits."
        )

    # 3. Read payload bits
    payload_bits_count = payload_len * 8
    payload_bits = [next(gen) for _ in range(payload_bits_count)]
    payload = bits_to_bytes(np.array(payload_bits, dtype=np.uint8))

    # 4. Verify IEEE 802.3 CRC32 checksum
    actual_crc = zlib.crc32(payload) & 0xFFFFFFFF
    if actual_crc != expected_crc:
        raise CarrierExtractionError(
            f"Payload CRC32 checksum mismatch: header expected 0x{expected_crc:08X}, "
            f"but extracted payload computed 0x{actual_crc:08X}. Data has been corrupted."
        )

    return payload
