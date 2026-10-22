"""PCM WAV Audio Steganography module.

This module implements deterministic, length-prefixed LSB embedding and extraction
for uncompressed PCM WAV audio files using Python's standard `wave` library and NumPy.

Key Architectural Guarantees for Students:
1. Deterministic Bit Ordering & Channel Interleaving:
   - Supports both mono (1 channel) and stereo (2 channels) uncompressed PCM WAV files.
   - For multi-channel audio, samples are interleaved: [L0, R0, L1, R1, ...].
   - Sequential embedding traverses interleaved samples chronologically.
   - Bits within each byte are processed Most Significant Bit (MSB) to Least Significant Bit (LSB).
2. Explicit Binary Framing (14 Bytes Header):
   - Magic Signature (4 bytes): b"WSTG" (WAV Stego) - distinct from PNG b"PSTG".
   - Format Version (1 byte): 0x01
   - Reserved (1 byte): 0x00
   - Payload Length (4 bytes uint32 big-endian)
   - Payload CRC32 (4 bytes uint32 big-endian)
   - Followed by exactly L bytes of embedded payload.
3. Audio Metadata & Header Preservation:
   - The sample rate (e.g. 44.1 kHz, 48 kHz), channel count, sample width (16-bit / 8-bit),
     and total audio duration are strictly preserved in the output WAV container.
4. Lossless Uncompressed PCM:
   - Operates strictly on uncompressed PCM WAV audio. Lossy audio formats (e.g. MP3, AAC, OGG)
     discard high-frequency information and modify sample values via psychoacoustic quantization,
     which destroys LSB modifications.
5. Objective Fidelity Metrics:
   - Calculates Mean Squared Error (MSE) and Signal-to-Noise Ratio (SNR) in decibels (dB).
   - High SNR / low MSE demonstrates physical signal fidelity, but does not prove resistance
     to statistical or machine-learning audio steganalysis.
"""

import io
import math
import struct
from typing import Dict, Tuple, Union
import wave
import zlib
import numpy as np

from app.evaluation.quality_metrics import evaluate_audio_quality

# Framing Constants
AUDIO_MAGIC = b"WSTG"
AUDIO_FORMAT_VERSION = 1
FRAME_HEADER_FORMAT = ">4sBBII"
FRAME_HEADER_SIZE = struct.calcsize(FRAME_HEADER_FORMAT)  # 14 bytes (112 bits)


class AudioStegoError(Exception):
    """Base exception for audio steganography errors."""
    pass


class InsufficientCapacityError(AudioStegoError):
    """Raised when the carrier audio file cannot hold the requested payload."""
    pass


class CarrierExtractionError(AudioStegoError):
    """Raised when extraction fails (bad signature, corrupt CRC, or truncated audio)."""
    pass


class UnsupportedAudioFormatError(AudioStegoError):
    """Raised when an uploaded audio file is invalid, compressed, or unsupported."""
    pass


def bytes_to_bits(data: bytes) -> np.ndarray:
    """Convert bytes into a 1D NumPy uint8 array of binary bits (MSB first)."""
    byte_arr = np.frombuffer(data, dtype=np.uint8)
    return np.unpackbits(byte_arr)


def bits_to_bytes(bits: np.ndarray) -> bytes:
    """Pack a 1D NumPy uint8 array of binary bits (MSB first) into bytes."""
    return bytes(np.packbits(bits))


def pack_stego_frame(payload: bytes) -> bytes:
    """Pack a raw payload with the 14-byte length-prefixed audio stego framing header.

    Header Layout:
        - 4 bytes magic: b"WSTG"
        - 1 byte version: 0x01
        - 1 byte reserved: 0x00
        - 4 bytes uint32: payload length L (big-endian)
        - 4 bytes uint32: payload CRC32 (big-endian)
    """
    payload_len = len(payload)
    payload_crc = zlib.crc32(payload) & 0xFFFFFFFF
    header = struct.pack(
        FRAME_HEADER_FORMAT,
        AUDIO_MAGIC,
        AUDIO_FORMAT_VERSION,
        0,
        payload_len,
        payload_crc,
    )
    return header + payload


def load_wav_audio(
    audio_input: Union[bytes, bytearray, io.BytesIO]
) -> Tuple[np.ndarray, Dict[str, Union[int, float, str]]]:
    """Parse and validate an uncompressed PCM WAV audio file.

    Args:
        audio_input: Raw audio file bytes or BytesIO stream.

    Returns:
        Tuple of (samples as 1D NumPy array, audio_parameters dictionary).

    Raises:
        UnsupportedAudioFormatError: If audio is corrupted, compressed, or uses unsupported sample width.
    """
    if isinstance(audio_input, (bytes, bytearray)):
        stream = io.BytesIO(audio_input)
    elif isinstance(audio_input, io.BytesIO):
        stream = audio_input
        stream.seek(0)
    else:
        raise UnsupportedAudioFormatError("Unsupported audio input type.")

    try:
        with wave.open(stream, "rb") as wf:
            num_channels = wf.getnchannels()
            sample_width = wf.getsampwidth()
            sample_rate = wf.getframerate()
            num_frames = wf.getnframes()
            comp_type = wf.getcomptype()
            raw_frames = wf.readframes(num_frames)
    except wave.Error as e:
        raise UnsupportedAudioFormatError(f"Invalid or unreadable WAV file: {str(e)}") from e
    except Exception as e:
        raise UnsupportedAudioFormatError(f"Failed to decode audio file: {str(e)}") from e

    # Validation: must be uncompressed PCM
    if comp_type != "NONE":
        raise UnsupportedAudioFormatError(
            f"Unsupported WAV compression '{comp_type}': only uncompressed PCM WAV is supported."
        )

    # Validation: channel count
    if num_channels not in (1, 2):
        raise UnsupportedAudioFormatError(
            f"Unsupported channel count ({num_channels}): only mono (1) and stereo (2) WAV files are supported."
        )

    # Validation: sample width (16-bit signed PCM or 8-bit unsigned PCM)
    if sample_width == 2:
        samples = np.frombuffer(raw_frames, dtype=np.int16).copy()
    elif sample_width == 1:
        samples = np.frombuffer(raw_frames, dtype=np.uint8).copy()
    else:
        raise UnsupportedAudioFormatError(
            f"Unsupported sample width ({sample_width * 8}-bit): only 16-bit and 8-bit PCM WAV are supported."
        )

    if len(samples) == 0:
        raise UnsupportedAudioFormatError("Audio carrier contains zero audio samples.")

    duration_seconds = round(num_frames / float(sample_rate), 4) if sample_rate > 0 else 0.0

    params = {
        "num_channels": num_channels,
        "channel_layout": "Stereo" if num_channels == 2 else "Mono",
        "sample_width": sample_width,
        "bits_per_sample": sample_width * 8,
        "sample_rate": sample_rate,
        "num_frames": num_frames,
        "total_samples": len(samples),
        "duration_seconds": duration_seconds,
    }

    return samples, params


def save_wav_audio(
    samples: np.ndarray,
    params: Dict[str, Union[int, float, str]]
) -> bytes:
    """Encode audio samples and preserve original WAV container headers.

    Args:
        samples: 1D NumPy array of audio samples (int16 or uint8).
        params: Original audio parameters dictionary.

    Returns:
        Standard WAV file bytes.
    """
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(int(params["num_channels"]))
        wf.setsampwidth(int(params["sample_width"]))
        wf.setframerate(int(params["sample_rate"]))
        wf.writeframes(samples.tobytes())
    return buf.getvalue()


def get_audio_capacity(
    audio_input: Union[bytes, bytearray, io.BytesIO]
) -> Dict[str, Union[int, float, str]]:
    """Calculate the total and usable payload capacity of a carrier WAV audio file.

    Capacity Calculation:
        - 1 bit embedded per audio sample (both mono and stereo interleaved).
        - Total Carrier Bits = Total Samples.
        - Total Carrier Bytes = Total Samples // 8.
        - Usable Payload Bytes = max(0, Total Carrier Bytes - 14) [14 bytes for WSTG framing].

    Args:
        audio_input: Carrier audio input.

    Returns:
        Dictionary detailing audio parameters, carrier capacity, and maximum payload bytes.
    """
    samples, params = load_wav_audio(audio_input)
    total_samples = len(samples)

    total_carrier_bits = total_samples
    total_carrier_bytes = total_carrier_bits // 8
    max_usable_payload_bytes = max(0, total_carrier_bytes - FRAME_HEADER_SIZE)

    return {
        "num_channels": int(params["num_channels"]),
        "channel_layout": str(params["channel_layout"]),
        "sample_rate": int(params["sample_rate"]),
        "sample_width": int(params["sample_width"]),
        "bits_per_sample": int(params["bits_per_sample"]),
        "num_frames": int(params["num_frames"]),
        "duration_seconds": float(params["duration_seconds"]),
        "total_samples": total_samples,
        "total_carrier_bits": total_carrier_bits,
        "total_carrier_bytes": total_carrier_bytes,
        "header_overhead_bytes": FRAME_HEADER_SIZE,
        "max_usable_payload_bytes": max_usable_payload_bytes,
    }


def embed_in_audio(
    audio_input: Union[bytes, bytearray, io.BytesIO],
    payload: bytes
) -> Tuple[bytes, Dict[str, Union[float, str, int]]]:
    """Embed a binary payload into a PCM WAV audio file using sample LSB substitution.

    Args:
        audio_input: Cover audio file bytes or stream.
        payload: Binary payload bytes (e.g. Phase 2 encrypted envelope).

    Returns:
        Tuple of (stego_wav_bytes, quality_metrics dictionary).

    Raises:
        InsufficientCapacityError: If payload exceeds audio carrier capacity.
        UnsupportedAudioFormatError: If audio format is invalid or compressed.
    """
    cover_samples, params = load_wav_audio(audio_input)
    total_samples = len(cover_samples)

    # 1. Pack payload with 14-byte stego framing header
    framed_data = pack_stego_frame(payload)
    framed_bits = bytes_to_bits(framed_data)
    num_bits = len(framed_bits)

    # 2. Capacity bounds check
    if num_bits > total_samples:
        raise InsufficientCapacityError(
            f"Payload of {len(payload)} bytes (framed: {len(framed_data)} bytes = {num_bits} bits) "
            f"exceeds audio carrier capacity of {total_samples // 8} bytes ({total_samples} samples/bits)."
        )

    # 3. Clone samples to create stego audio
    stego_samples = cover_samples.copy()

    # Apply LSB substitution:
    # For 16-bit PCM: mask with ~1 (-2) then OR with payload bit
    # For 8-bit PCM: mask with 0xFE (254) then OR with payload bit
    sample_width = int(params["sample_width"])
    if sample_width == 2:
        stego_samples[:num_bits] = (stego_samples[:num_bits] & np.int16(~1)) | framed_bits.astype(np.int16)
    else:
        stego_samples[:num_bits] = (stego_samples[:num_bits] & np.uint8(0xFE)) | framed_bits.astype(np.uint8)

    # 4. Compute audio quality distortion metrics
    metrics = evaluate_audio_quality(cover_samples, stego_samples, sampwidth=sample_width)
    metrics["embedded_bytes"] = len(payload)
    metrics["framed_bytes"] = len(framed_data)
    metrics["capacity_used_ratio"] = round(num_bits / total_samples, 6)
    metrics["bits_per_sample_used"] = round(num_bits / total_samples, 4)

    # 5. Save back to standard WAV format
    stego_wav_bytes = save_wav_audio(stego_samples, params)

    return stego_wav_bytes, metrics


def extract_from_audio(
    audio_input: Union[bytes, bytearray, io.BytesIO]
) -> bytes:
    """Extract and verify an embedded binary payload from a stego PCM WAV audio file.

    Args:
        audio_input: Stego audio file bytes or stream.

    Returns:
        Exact byte-for-byte recovered payload bytes.

    Raises:
        CarrierExtractionError: If magic signature is missing, length exceeds bounds,
                                or CRC32 verification fails.
        UnsupportedAudioFormatError: If audio format is invalid or compressed.
    """
    stego_samples, _ = load_wav_audio(audio_input)
    total_samples = len(stego_samples)

    # 1. Extract 14-byte framing header (112 bits)
    header_bits_count = FRAME_HEADER_SIZE * 8
    if total_samples < header_bits_count:
        raise CarrierExtractionError(
            "Audio file is too short to contain a valid steganographic framing header."
        )

    header_bits = (stego_samples[:header_bits_count] & 1).astype(np.uint8)
    header_bytes = bits_to_bytes(header_bits)

    # Unpack header
    magic, version, reserved, payload_len, expected_crc = struct.unpack(
        FRAME_HEADER_FORMAT,
        header_bytes[:FRAME_HEADER_SIZE]
    )

    if magic != AUDIO_MAGIC:
        raise CarrierExtractionError(
            f"Invalid audio steganography signature: expected {AUDIO_MAGIC!r}, got {magic!r}. "
            "This audio file does not appear to contain an embedded payload."
        )

    if version != AUDIO_FORMAT_VERSION:
        raise CarrierExtractionError(
            f"Unsupported audio stego format version: expected {AUDIO_FORMAT_VERSION}, got {version}."
        )

    # 2. Bounds check on declared payload length
    required_total_bits = header_bits_count + (payload_len * 8)
    if required_total_bits > total_samples:
        raise CarrierExtractionError(
            f"Corrupted audio payload header: declared length of {payload_len} bytes requires "
            f"{required_total_bits} samples, but carrier only contains {total_samples} samples."
        )

    # 3. Extract payload bits and pack into bytes
    payload_bits = (stego_samples[header_bits_count:required_total_bits] & 1).astype(np.uint8)
    payload = bits_to_bytes(payload_bits)

    # 4. Verify IEEE 802.3 CRC32 checksum
    actual_crc = zlib.crc32(payload) & 0xFFFFFFFF
    if actual_crc != expected_crc:
        raise CarrierExtractionError(
            f"Payload CRC32 checksum mismatch: header expected 0x{expected_crc:08X}, "
            f"extracted payload computed 0x{actual_crc:08X}. Audio data may be corrupted or transcoded."
        )

    return payload
