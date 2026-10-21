"""Spatial LSB (Least Significant Bit) PNG image steganography.

This module implements deterministic, length-prefixed LSB embedding and extraction
for lossless PNG images using Pillow and NumPy.

Key Architectural Guarantees for Students:
1. Deterministic Bit Ordering:
   - Traverses pixels in row-major order (y = 0..H-1, x = 0..W-1).
   - Employs RGB color channels in sequence (R -> G -> B).
   - If an RGBA image is supplied, the Alpha channel (channel index 3) is strictly
     preserved and untouched to prevent transparency degradation.
   - Bits within each byte are processed Most Significant Bit (MSB) to Least Significant
     Bit (LSB), matching network byte order convention.
2. Explicit Binary Framing (14 Bytes Header):
   - Magic Signature (4 bytes): b"PSTG" (PNG Stego)
   - Format Version (1 byte): 0x01
   - Reserved (1 byte): 0x00
   - Payload Length (4 bytes uint32 big-endian)
   - Payload CRC32 (4 bytes uint32 big-endian)
   - Followed by exactly L bytes of embedded payload.
3. Integrity Pre-Check:
   - CRC32 verification detects channel bit flips or non-lossy transcoding
     before cryptographic decryption is attempted.
4. Lossless Preservation:
   - Output images are saved strictly as lossless PNGs. Lossy formats (e.g. JPEG)
     would destroy LSB modifications during discrete cosine transform (DCT) quantization.
"""

import io
import struct
from typing import Dict, Tuple, Union
import zlib
import numpy as np
from PIL import Image

from app.evaluation.quality_metrics import evaluate_image_quality

# Framing Constants
IMAGE_MAGIC = b"PSTG"
IMAGE_FORMAT_VERSION = 1
FRAME_HEADER_FORMAT = ">4sBBII"
FRAME_HEADER_SIZE = struct.calcsize(FRAME_HEADER_FORMAT)  # 14 bytes (112 bits)
CHANNELS_PER_PIXEL = 3  # R, G, B channels used for embedding


class ImageStegoError(Exception):
    """Base exception for image steganography errors."""
    pass


class InsufficientCapacityError(ImageStegoError):
    """Raised when the carrier image cannot hold the requested payload."""
    pass


class CarrierExtractionError(ImageStegoError):
    """Raised when extraction fails (bad signature, corrupt CRC, or truncated image)."""
    pass


class UnsupportedImageFormatError(ImageStegoError):
    """Raised when the image format or mode is unsupported."""
    pass


def load_image_as_rgb_array(image_input: Union[bytes, io.BytesIO, Image.Image, np.ndarray]) -> Tuple[np.ndarray, str]:
    """Load an image into a NumPy uint8 RGB or RGBA array.

    Args:
        image_input: Raw image bytes, BytesIO stream, PIL Image, or existing ndarray.

    Returns:
        Tuple of (numpy uint8 array of shape [H, W, 3] or [H, W, 4], original_mode string).

    Raises:
        UnsupportedImageFormatError: If image cannot be parsed or has incompatible mode.
    """
    if isinstance(image_input, np.ndarray):
        if image_input.dtype != np.uint8:
            raise UnsupportedImageFormatError("NumPy image array must have dtype uint8.")
        if image_input.ndim != 3 or image_input.shape[2] not in (3, 4):
            raise UnsupportedImageFormatError("NumPy image array must have shape (H, W, 3) or (H, W, 4).")
        mode = "RGB" if image_input.shape[2] == 3 else "RGBA"
        return image_input.copy(), mode

    pil_img: Image.Image
    if isinstance(image_input, Image.Image):
        pil_img = image_input
    elif isinstance(image_input, (bytes, bytearray, io.BytesIO)):
        stream = io.BytesIO(image_input) if isinstance(image_input, (bytes, bytearray)) else image_input
        try:
            pil_img = Image.open(stream)
            pil_img.load()  # Force reading image data
        except Exception as e:
            raise UnsupportedImageFormatError(f"Failed to decode image: {str(e)}") from e
    else:
        raise UnsupportedImageFormatError("Unsupported image input type.")

    original_mode = pil_img.mode
    # Convert palette, grayscale, or CMYK images to RGB
    if original_mode in ("RGB", "RGBA"):
        img_array = np.array(pil_img, dtype=np.uint8)
        return img_array, original_mode
    elif original_mode in ("P", "L", "1", "CMYK"):
        converted = pil_img.convert("RGB")
        img_array = np.array(converted, dtype=np.uint8)
        return img_array, "RGB"
    else:
        raise UnsupportedImageFormatError(f"Unsupported image color mode '{original_mode}'.")


def get_image_capacity(image_input: Union[bytes, Image.Image, np.ndarray]) -> Dict[str, int]:
    """Calculate the total and usable payload capacity of a carrier image.

    Args:
        image_input: Carrier image input.

    Returns:
        Dictionary detailing dimensions, carrier capacity, and maximum payload bytes.
    """
    img_array, mode = load_image_as_rgb_array(image_input)
    h, w, c = img_array.shape

    # Embed 1 bit per RGB channel (first 3 channels)
    total_carrier_bits = h * w * CHANNELS_PER_PIXEL
    total_carrier_bytes = total_carrier_bits // 8

    # 14 bytes dedicated to framing header
    max_usable_payload_bytes = max(0, total_carrier_bytes - FRAME_HEADER_SIZE)

    return {
        "width": w,
        "height": h,
        "channels": c,
        "color_mode": mode,
        "embeddable_channels_per_pixel": CHANNELS_PER_PIXEL,
        "total_carrier_bits": total_carrier_bits,
        "total_carrier_bytes": total_carrier_bytes,
        "header_overhead_bytes": FRAME_HEADER_SIZE,
        "max_usable_payload_bytes": max_usable_payload_bytes,
    }


def pack_stego_frame(payload: bytes) -> bytes:
    """Pack a raw payload with the 14-byte length-prefixed stego framing header.

    Header:
        - 4 bytes magic: b"PSTG"
        - 1 byte version: 0x01
        - 1 byte reserved: 0x00
        - 4 bytes uint32: payload length L
        - 4 bytes uint32: payload CRC32
    """
    payload_len = len(payload)
    payload_crc = zlib.crc32(payload) & 0xFFFFFFFF
    header = struct.pack(
        FRAME_HEADER_FORMAT,
        IMAGE_MAGIC,
        IMAGE_FORMAT_VERSION,
        0,
        payload_len,
        payload_crc,
    )
    return header + payload


def bytes_to_bits(data: bytes) -> np.ndarray:
    """Convert bytes into a 1D NumPy uint8 array of binary bits (MSB first)."""
    # Unpack bits: 8 bits per byte
    byte_arr = np.frombuffer(data, dtype=np.uint8)
    bits = np.unpackbits(byte_arr)
    return bits


def bits_to_bytes(bits: np.ndarray) -> bytes:
    """Pack a 1D NumPy uint8 array of binary bits (MSB first) into bytes."""
    packed = np.packbits(bits)
    return bytes(packed)


def embed_in_image(
    image_input: Union[bytes, Image.Image, np.ndarray],
    payload: bytes
) -> Tuple[np.ndarray, Dict[str, Union[float, str, int]]]:
    """Embed a binary payload into a PNG image using spatial LSB substitution.

    Args:
        image_input: Cover image input.
        payload: Binary payload bytes (e.g. Phase 2 encrypted envelope).

    Returns:
        Tuple of (stego_image_array as uint8 ndarray, quality_metrics dictionary).

    Raises:
        InsufficientCapacityError: If payload exceeds image capacity.
        UnsupportedImageFormatError: If image cannot be parsed.
    """
    cover_array, mode = load_image_as_rgb_array(image_input)
    h, w, c = cover_array.shape

    # 1. Pack payload with 14-byte stego framing header
    framed_data = pack_stego_frame(payload)
    framed_bits = bytes_to_bits(framed_data)
    num_bits = len(framed_bits)

    # 2. Verify capacity
    total_available_bits = h * w * CHANNELS_PER_PIXEL
    if num_bits > total_available_bits:
        raise InsufficientCapacityError(
            f"Payload of {len(payload)} bytes (framed: {len(framed_data)} bytes = {num_bits} bits) "
            f"exceeds carrier capacity of {total_available_bits // 8} bytes ({total_available_bits} bits)."
        )

    # 3. Clone array to create stego image
    stego_array = cover_array.copy()

    # Flatten the RGB channels for sequential bit assignment
    # If image is RGBA, we only manipulate channels 0..2 (RGB)
    rgb_channels = stego_array[:, :, :CHANNELS_PER_PIXEL].reshape(-1)

    # Apply LSB substitution: clear LSB (mask 0xFE) then OR with payload bit
    bits_to_embed = framed_bits.astype(np.uint8)
    rgb_channels[:num_bits] = (rgb_channels[:num_bits] & np.uint8(0xFE)) | bits_to_embed

    # Put modified RGB channels back
    stego_array[:, :, :CHANNELS_PER_PIXEL] = rgb_channels.reshape(h, w, CHANNELS_PER_PIXEL)

    # 4. Compute quality metrics
    metrics = evaluate_image_quality(cover_array, stego_array)
    metrics["embedded_bytes"] = len(payload)
    metrics["framed_bytes"] = len(framed_data)
    metrics["capacity_used_ratio"] = round(num_bits / total_available_bits, 4)
    metrics["bits_per_pixel"] = round(num_bits / (h * w), 4)

    return stego_array, metrics


def extract_from_image(image_input: Union[bytes, Image.Image, np.ndarray]) -> bytes:
    """Extract and verify an embedded binary payload from a stego PNG image.

    Args:
        image_input: Stego image input.

    Returns:
        Exact byte-for-byte recovered payload bytes.

    Raises:
        CarrierExtractionError: If magic signature is missing, length exceeds bounds,
                                or CRC32 verification fails.
        UnsupportedImageFormatError: If image cannot be read.
    """
    stego_array, _ = load_image_as_rgb_array(image_input)
    h, w, _ = stego_array.shape

    # Flatten RGB channels
    rgb_channels = stego_array[:, :, :CHANNELS_PER_PIXEL].reshape(-1)
    total_bits = len(rgb_channels)

    # 1. Extract 14-byte framing header (112 bits)
    header_bits_count = FRAME_HEADER_SIZE * 8
    if total_bits < header_bits_count:
        raise CarrierExtractionError("Image is too small to contain a valid steganographic framing header.")

    header_bits = rgb_channels[:header_bits_count] & 1
    header_bytes = bits_to_bytes(header_bits)

    # Unpack header
    magic, version, reserved, payload_len, expected_crc = struct.unpack(
        FRAME_HEADER_FORMAT,
        header_bytes[:FRAME_HEADER_SIZE]
    )

    if magic != IMAGE_MAGIC:
        raise CarrierExtractionError(
            f"Invalid steganography signature: expected {IMAGE_MAGIC!r}, got {magic!r}. "
            "This image does not appear to contain an embedded payload."
        )

    if version != IMAGE_FORMAT_VERSION:
        raise CarrierExtractionError(
            f"Unsupported stego format version: expected {IMAGE_FORMAT_VERSION}, got {version}."
        )

    # 2. Bounds check on declared payload length
    required_total_bits = header_bits_count + (payload_len * 8)
    if required_total_bits > total_bits:
        raise CarrierExtractionError(
            f"Corrupted payload header: declared length of {payload_len} bytes requires "
            f"{required_total_bits} bits, but carrier only contains {total_bits} bits."
        )

    # 3. Extract payload bits
    payload_bits = rgb_channels[header_bits_count:required_total_bits] & 1
    payload_bytes = bits_to_bytes(payload_bits)

    # Verify exact length
    if len(payload_bytes) != payload_len:
        payload_bytes = payload_bytes[:payload_len]

    # 4. Verify CRC32 integrity
    actual_crc = zlib.crc32(payload_bytes) & 0xFFFFFFFF
    if actual_crc != expected_crc:
        raise CarrierExtractionError(
            f"Payload CRC32 checksum mismatch: header expected 0x{expected_crc:08X}, "
            f"extracted payload computed 0x{actual_crc:08X}. Image data may be corrupted or transcoded."
        )

    return payload_bytes


def save_image_to_png_bytes(image_array: np.ndarray, mode: str = "RGB") -> bytes:
    """Save a NumPy image array to in-memory lossless PNG bytes."""
    pil_img = Image.fromarray(image_array, mode=mode)
    buffer = io.BytesIO()
    pil_img.save(buffer, format="PNG", optimize=False)
    return buffer.getvalue()
