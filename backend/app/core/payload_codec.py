"""Versioned binary payload codec for multimodal steganographic carriers.

This module defines an explicit, versioned binary packet layout for splitting
an encrypted payload across heterogeneous carrier channels (e.g. image, audio, video)
and safely reconstructing it.

Binary Header Layout (34 bytes, Big-Endian):
+--------------------+----------------+-----------------+-------------------+
| Field              | Size / Type    | Byte Offset     | Description       |
+--------------------+----------------+-----------------+-------------------+
| Magic Bytes        | 4 bytes        | 0 - 3           | b"ASTG"           |
| Format Version     | 1 byte uint8   | 4               | 0x01              |
| Reserved           | 1 byte uint8   | 5               | 0x00              |
| Message ID         | 16 bytes       | 6 - 21          | 128-bit UUID      |
| Chunk Index        | 2 bytes uint16 | 22 - 23         | 0-indexed         |
| Total Chunks       | 2 bytes uint16 | 24 - 25         | Total chunks in msg|
| Payload Length (L) | 4 bytes uint32 | 26 - 29         | Byte length of chunk|
| Payload CRC32      | 4 bytes uint32 | 30 - 33         | IEEE 802.3 CRC32  |
+--------------------+----------------+-----------------+-------------------+
| Chunk Payload      | L bytes        | 34 - (34+L-1)   | Raw chunk bytes   |
+--------------------+----------------+-----------------+-------------------+

Key Architectural Guarantees for Students:
1. Deterministic Framing: Big-endian byte order (network byte order `>`) is used
   consistently so data serialized on one machine unpacks identically everywhere.
2. Fast Integrity Pre-Check: The CRC32 checksum allows carriers to detect bit flips
   or channel truncation immediately before handing data to cryptographic decryption.
3. Separation of Concerns:
   - Chunk-level codec validation checks packet framing, chunk ordering, and boundaries.
   - Cryptographic authentication (AES-256-GCM) provides tamper detection and confidentiality.
4. No Inherent Secret Sharing:
   - Slicing ciphertext into 3 pieces does NOT create a threshold secret-sharing scheme
     (e.g., Shamir's Secret Sharing). All required chunks must be recovered to reassemble
     the complete ciphertext envelope.
"""

from dataclasses import dataclass
import struct
from typing import List, Optional, Set, Tuple
import uuid
import zlib

# Constants
MAGIC_BYTES = b"ASTG"
FORMAT_VERSION = 1
HEADER_FORMAT = ">4sBB16sHHII"
HEADER_SIZE = struct.calcsize(HEADER_FORMAT)  # 34 bytes
MAX_CHUNK_PAYLOAD_SIZE = 50 * 1024 * 1024     # 50 MB safety limit per chunk


class CodecError(Exception):
    """Base exception for payload codec errors."""
    pass


class InvalidMagicError(CodecError):
    """Raised when the packet magic signature does not match b'ASTG'."""
    pass


class UnsupportedVersionError(CodecError):
    """Raised when the packet version is not supported."""
    pass


class TruncatedChunkError(CodecError):
    """Raised when raw chunk bytes are shorter than required by header."""
    pass


class MalformedChunkError(CodecError):
    """Raised when packet contains unexpected trailing bytes or invalid bounds."""
    pass


class ChecksumMismatchError(CodecError):
    """Raised when CRC32 checksum of chunk payload does not match header."""
    pass


class InvalidChunkIndexError(CodecError):
    """Raised when chunk index is >= total chunks or negative."""
    pass


class InvalidChunkCountError(CodecError):
    """Raised when total chunks is less than 1."""
    pass


class MessageIdMismatchError(CodecError):
    """Raised when reassembling chunks with different message IDs."""
    pass


class ChunkCountMismatchError(CodecError):
    """Raised when chunks report differing total_chunks values."""
    pass


class MissingChunkError(CodecError):
    """Raised when some chunk indices are missing during reassembly."""
    pass


class DuplicateChunkError(CodecError):
    """Raised when duplicate chunk indices are encountered during reassembly."""
    pass


@dataclass(frozen=True)
class PayloadChunk:
    """Represents an individual chunk of a larger message.

    Attributes:
        message_id: 16 bytes identifying the parent message (typically UUID4 bytes).
        chunk_index: 0-indexed position of this chunk (0 <= index < total_chunks).
        total_chunks: Total number of chunks the parent message was split into.
        payload: The raw bytes carried in this chunk.
        version: Codec format version (default 1).
    """
    message_id: bytes
    chunk_index: int
    total_chunks: int
    payload: bytes
    version: int = FORMAT_VERSION

    def __post_init__(self):
        if not isinstance(self.message_id, (bytes, bytearray)):
            raise CodecError("message_id must be bytes.")
        if len(self.message_id) != 16:
            raise CodecError(f"message_id must be exactly 16 bytes; got {len(self.message_id)} bytes.")
        if self.total_chunks < 1:
            raise InvalidChunkCountError(f"total_chunks must be >= 1; got {self.total_chunks}.")
        if self.chunk_index < 0 or self.chunk_index >= self.total_chunks:
            raise InvalidChunkIndexError(
                f"chunk_index {self.chunk_index} is out of bounds for total_chunks {self.total_chunks}."
            )
        if len(self.payload) > MAX_CHUNK_PAYLOAD_SIZE:
            raise MalformedChunkError(
                f"Chunk payload size {len(self.payload)} exceeds maximum allowed {MAX_CHUNK_PAYLOAD_SIZE} bytes."
            )


def serialize_chunk(chunk: PayloadChunk) -> bytes:
    """Serialize a PayloadChunk into its versioned 34-byte binary framed representation.

    Args:
        chunk: PayloadChunk instance to serialize.

    Returns:
        34-byte header followed by chunk.payload bytes.
    """
    payload_len = len(chunk.payload)
    payload_crc = zlib.crc32(chunk.payload) & 0xFFFFFFFF

    header = struct.pack(
        HEADER_FORMAT,
        MAGIC_BYTES,
        chunk.version,
        0,  # reserved byte
        chunk.message_id,
        chunk.chunk_index,
        chunk.total_chunks,
        payload_len,
        payload_crc,
    )

    return header + chunk.payload


def deserialize_chunk(raw_bytes: bytes, allow_trailing: bool = False) -> PayloadChunk:
    """Deserialize raw bytes into a validated PayloadChunk.

    Args:
        raw_bytes: Binary data containing the 34-byte header and payload.
        allow_trailing: If True, ignores trailing bytes beyond declared payload length.
                        If False, raises MalformedChunkError if trailing bytes exist.

    Returns:
        Validated PayloadChunk instance.

    Raises:
        TruncatedChunkError: If raw_bytes is shorter than header or declared payload.
        InvalidMagicError: If magic bytes do not equal b"ASTG".
        UnsupportedVersionError: If format version is not 1.
        InvalidChunkCountError: If total_chunks < 1.
        InvalidChunkIndexError: If chunk_index >= total_chunks.
        ChecksumMismatchError: If CRC32 checksum fails.
        MalformedChunkError: If unexpected trailing bytes exist when allow_trailing=False.
    """
    if not isinstance(raw_bytes, (bytes, bytearray)):
        raise CodecError("raw_bytes must be bytes or bytearray.")

    if len(raw_bytes) < HEADER_SIZE:
        raise TruncatedChunkError(
            f"Chunk data is truncated: expected at least {HEADER_SIZE} bytes for header, got {len(raw_bytes)} bytes."
        )

    magic, version, reserved, message_id, chunk_index, total_chunks, payload_len, expected_crc = (
        struct.unpack(HEADER_FORMAT, raw_bytes[:HEADER_SIZE])
    )

    if magic != MAGIC_BYTES:
        raise InvalidMagicError(
            f"Invalid magic signature: expected {MAGIC_BYTES!r}, got {magic!r}."
        )

    if version != FORMAT_VERSION:
        raise UnsupportedVersionError(
            f"Unsupported codec version: expected {FORMAT_VERSION}, got {version}."
        )

    if total_chunks < 1:
        raise InvalidChunkCountError(
            f"Total chunks in header must be >= 1, got {total_chunks}."
        )

    if chunk_index >= total_chunks:
        raise InvalidChunkIndexError(
            f"Chunk index {chunk_index} is invalid for total_chunks {total_chunks}."
        )

    if payload_len > MAX_CHUNK_PAYLOAD_SIZE:
        raise MalformedChunkError(
            f"Declared payload length {payload_len} exceeds safety limit of {MAX_CHUNK_PAYLOAD_SIZE} bytes."
        )

    total_expected_len = HEADER_SIZE + payload_len
    if len(raw_bytes) < total_expected_len:
        raise TruncatedChunkError(
            f"Truncated chunk payload: declared {payload_len} bytes, but only {len(raw_bytes) - HEADER_SIZE} bytes available."
        )

    if not allow_trailing and len(raw_bytes) > total_expected_len:
        raise MalformedChunkError(
            f"Unexpected trailing bytes: expected {total_expected_len} bytes, got {len(raw_bytes)} bytes."
        )

    chunk_payload = raw_bytes[HEADER_SIZE:total_expected_len]

    # Verify CRC32 checksum
    actual_crc = zlib.crc32(chunk_payload) & 0xFFFFFFFF
    if actual_crc != expected_crc:
        raise ChecksumMismatchError(
            f"Payload CRC32 checksum mismatch: header expected 0x{expected_crc:08X}, computed 0x{actual_crc:08X}."
        )

    return PayloadChunk(
        message_id=message_id,
        chunk_index=chunk_index,
        total_chunks=total_chunks,
        payload=chunk_payload,
        version=version,
    )


def split_payload_equally(
    payload: bytes,
    num_chunks: int,
    message_id: Optional[bytes] = None
) -> List[PayloadChunk]:
    """Split a payload into N approximately equal chunks.

    Args:
        payload: Full payload bytes to partition.
        num_chunks: Number of chunks (must be >= 1).
        message_id: Optional 16-byte message identifier. If None, generates random UUID4 bytes.

    Returns:
        List of N serialized PayloadChunk objects.
    """
    if num_chunks < 1:
        raise InvalidChunkCountError(f"num_chunks must be >= 1; got {num_chunks}.")

    if message_id is None:
        message_id = uuid.uuid4().bytes
    elif len(message_id) != 16:
        raise CodecError(f"message_id must be 16 bytes; got {len(message_id)} bytes.")

    total_len = len(payload)

    # Base chunk size and remainder distribution
    base_size = total_len // num_chunks
    remainder = total_len % num_chunks

    chunks: List[PayloadChunk] = []
    offset = 0

    for i in range(num_chunks):
        # Distribute remainder across the first few chunks
        chunk_size = base_size + (1 if i < remainder else 0)
        chunk_data = payload[offset:offset + chunk_size]
        offset += chunk_size

        chunks.append(
            PayloadChunk(
                message_id=message_id,
                chunk_index=i,
                total_chunks=num_chunks,
                payload=chunk_data,
            )
        )

    return chunks


def split_payload_by_capacities(
    payload: bytes,
    capacities: List[int],
    message_id: Optional[bytes] = None
) -> List[PayloadChunk]:
    """Split a payload across carrier channels based on their explicit byte capacities.

    Args:
        payload: Full payload bytes to split.
        capacities: Usable byte capacities for each carrier (e.g. [image_cap, audio_cap, video_cap]).
        message_id: Optional 16-byte message identifier.

    Returns:
        List of PayloadChunk objects.

    Raises:
        CodecError: If total capacity is insufficient or any capacity < 0.
    """
    if not capacities:
        raise CodecError("Capacities list cannot be empty.")

    if any(c < 0 for c in capacities):
        raise CodecError("Carrier capacities cannot be negative.")

    total_capacity = sum(capacities)
    if total_capacity < len(payload):
        raise CodecError(
            f"Insufficient carrier capacity: payload requires {len(payload)} bytes, "
            f"but total carrier capacity is {total_capacity} bytes."
        )

    if message_id is None:
        message_id = uuid.uuid4().bytes
    elif len(message_id) != 16:
        raise CodecError(f"message_id must be 16 bytes; got {len(message_id)} bytes.")

    # Determine slice sizes proportionally, or greedily filling carriers
    num_chunks = len(capacities)
    chunks: List[PayloadChunk] = []
    remaining_payload = payload

    for i, cap in enumerate(capacities):
        # For the last carrier, it takes whatever remains
        if i == num_chunks - 1:
            chunk_data = remaining_payload
        else:
            # Allocate up to capacity or remaining payload
            take = min(len(remaining_payload), cap)
            chunk_data = remaining_payload[:take]
            remaining_payload = remaining_payload[take:]

        chunks.append(
            PayloadChunk(
                message_id=message_id,
                chunk_index=i,
                total_chunks=num_chunks,
                payload=chunk_data,
            )
        )

    return chunks


def reassemble_chunks(chunks: List[PayloadChunk]) -> bytes:
    """Validate and reassemble an unordered collection of PayloadChunks into the original payload.

    Validation Rules:
    1. Chunks list must not be empty.
    2. All chunks must have matching message_id.
    3. All chunks must have matching total_chunks.
    4. Exact number of chunks must match total_chunks.
    5. No duplicate chunk indices allowed.
    6. All chunk indices 0 to total_chunks - 1 must be present.

    Args:
        chunks: List of PayloadChunk objects (can be in any order).

    Returns:
        Reassembled payload bytes.

    Raises:
        CodecError: If chunks list is empty.
        MessageIdMismatchError: If chunks from different messages are mixed.
        ChunkCountMismatchError: If chunks disagree on total_chunks.
        DuplicateChunkError: If duplicate indices exist.
        MissingChunkError: If indices are missing.
    """
    if not chunks:
        raise CodecError("Cannot reassemble: chunks list is empty.")

    first_msg_id = chunks[0].message_id
    first_total = chunks[0].total_chunks

    seen_indices: Set[int] = set()
    for chunk in chunks:
        if chunk.message_id != first_msg_id:
            raise MessageIdMismatchError(
                f"Message ID mismatch: chunk index {chunk.chunk_index} has ID {chunk.message_id.hex()}, "
                f"expected {first_msg_id.hex()}."
            )
        if chunk.total_chunks != first_total:
            raise ChunkCountMismatchError(
                f"Total chunks mismatch: chunk index {chunk.chunk_index} reports {chunk.total_chunks}, "
                f"expected {first_total}."
            )
        if chunk.chunk_index in seen_indices:
            raise DuplicateChunkError(
                f"Duplicate chunk index detected: index {chunk.chunk_index} appears multiple times."
            )
        seen_indices.add(chunk.chunk_index)

    # Check for missing indices
    expected_indices = set(range(first_total))
    missing = expected_indices - seen_indices
    if missing:
        missing_sorted = sorted(list(missing))
        raise MissingChunkError(
            f"Missing chunks: received {len(chunks)} of {first_total} chunks. "
            f"Missing indices: {missing_sorted}."
        )

    # Sort chunks deterministically by index
    sorted_chunks = sorted(chunks, key=lambda c: c.chunk_index)

    # Concatenate payloads
    return b"".join(c.payload for c in sorted_chunks)
