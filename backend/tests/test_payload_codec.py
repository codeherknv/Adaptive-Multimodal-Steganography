"""Automated test suite for the versioned binary payload codec."""

import os
import uuid
import pytest
from app.core.payload_codec import (
    HEADER_SIZE,
    MAGIC_BYTES,
    FORMAT_VERSION,
    PayloadChunk,
    serialize_chunk,
    deserialize_chunk,
    split_payload_equally,
    split_payload_by_capacities,
    reassemble_chunks,
    CodecError,
    InvalidMagicError,
    UnsupportedVersionError,
    TruncatedChunkError,
    MalformedChunkError,
    ChecksumMismatchError,
    InvalidChunkIndexError,
    InvalidChunkCountError,
    MessageIdMismatchError,
    ChunkCountMismatchError,
    MissingChunkError,
    DuplicateChunkError,
)


class TestChunkSerialization:
    def test_single_chunk_round_trip(self):
        msg_id = uuid.uuid4().bytes
        payload = b"Research multimodal stego chunk payload"
        chunk = PayloadChunk(
            message_id=msg_id,
            chunk_index=0,
            total_chunks=1,
            payload=payload,
        )

        serialized = serialize_chunk(chunk)
        assert len(serialized) == HEADER_SIZE + len(payload)
        assert serialized[:4] == MAGIC_BYTES
        assert serialized[4] == FORMAT_VERSION

        deserialized = deserialize_chunk(serialized)
        assert deserialized.message_id == msg_id
        assert deserialized.chunk_index == 0
        assert deserialized.total_chunks == 1
        assert deserialized.payload == payload
        assert deserialized.version == FORMAT_VERSION

    def test_empty_payload_chunk(self):
        msg_id = uuid.uuid4().bytes
        chunk = PayloadChunk(
            message_id=msg_id,
            chunk_index=0,
            total_chunks=1,
            payload=b"",
        )
        serialized = serialize_chunk(chunk)
        assert len(serialized) == HEADER_SIZE
        deserialized = deserialize_chunk(serialized)
        assert deserialized.payload == b""


class TestPayloadSplittingAndReassembly:
    def test_split_equally_round_trip(self):
        original = b"This is a longer payload that will be partitioned across 3 carriers: Image, Audio, Video."
        chunks = split_payload_equally(original, num_chunks=3)
        assert len(chunks) == 3
        assert [c.chunk_index for c in chunks] == [0, 1, 2]
        assert all(c.total_chunks == 3 for c in chunks)

        # Check serialization round-trip for each chunk
        serialized_chunks = [serialize_chunk(c) for c in chunks]
        deserialized_chunks = [deserialize_chunk(sc) for sc in serialized_chunks]

        recovered = reassemble_chunks(deserialized_chunks)
        assert recovered == original

    def test_split_by_capacities_round_trip(self):
        original = os.urandom(500)
        # 3 carriers with capacities: Image=200, Audio=150, Video=200 (Total=550 >= 500)
        capacities = [200, 150, 200]
        chunks = split_payload_by_capacities(original, capacities)
        assert len(chunks) == 3

        # Chunk 0 takes 200, Chunk 1 takes 150, Chunk 2 takes remaining 150
        assert len(chunks[0].payload) == 200
        assert len(chunks[1].payload) == 150
        assert len(chunks[2].payload) == 150

        recovered = reassemble_chunks(chunks)
        assert recovered == original

    def test_split_by_insufficient_capacity_rejected(self):
        payload = b"1234567890"  # 10 bytes
        capacities = [3, 4]       # Total 7 < 10
        with pytest.raises(CodecError, match="Insufficient carrier capacity"):
            split_payload_by_capacities(payload, capacities)

    def test_reassembly_out_of_order(self):
        original = b"Order-independent reassembly verification"
        chunks = split_payload_equally(original, num_chunks=4)

        # Provide chunks in reverse order: [3, 2, 1, 0]
        reversed_chunks = list(reversed(chunks))
        recovered = reassemble_chunks(reversed_chunks)
        assert recovered == original

        # Provide chunks in arbitrary shuffled order: [2, 0, 3, 1]
        shuffled_chunks = [chunks[2], chunks[0], chunks[3], chunks[1]]
        recovered2 = reassemble_chunks(shuffled_chunks)
        assert recovered2 == original


class TestCodecRejectionAndValidation:
    def test_invalid_magic_rejected(self):
        chunk = PayloadChunk(uuid.uuid4().bytes, 0, 1, b"Payload")
        raw = bytearray(serialize_chunk(chunk))
        raw[:4] = b"NOPE"

        with pytest.raises(InvalidMagicError):
            deserialize_chunk(bytes(raw))

    def test_unsupported_version_rejected(self):
        chunk = PayloadChunk(uuid.uuid4().bytes, 0, 1, b"Payload")
        raw = bytearray(serialize_chunk(chunk))
        raw[4] = 99  # Invalid version

        with pytest.raises(UnsupportedVersionError):
            deserialize_chunk(bytes(raw))

    def test_invalid_chunk_index_in_header(self):
        msg_id = uuid.uuid4().bytes
        # Try creating chunk with index >= total
        with pytest.raises(InvalidChunkIndexError):
            PayloadChunk(msg_id, chunk_index=2, total_chunks=2, payload=b"err")

        with pytest.raises(InvalidChunkIndexError):
            PayloadChunk(msg_id, chunk_index=-1, total_chunks=2, payload=b"err")

    def test_invalid_total_chunks(self):
        msg_id = uuid.uuid4().bytes
        with pytest.raises(InvalidChunkCountError):
            PayloadChunk(msg_id, chunk_index=0, total_chunks=0, payload=b"err")

    def test_crc32_checksum_mismatch_rejected(self):
        chunk = PayloadChunk(uuid.uuid4().bytes, 0, 1, b"Valid data payload")
        raw = bytearray(serialize_chunk(chunk))

        # Corrupt the payload part (offset >= 34)
        raw[35] ^= 0xFF

        with pytest.raises(ChecksumMismatchError):
            deserialize_chunk(bytes(raw))

    def test_truncated_header_rejected(self):
        with pytest.raises(TruncatedChunkError):
            deserialize_chunk(b"ASTG\x01\x00")  # Only 6 bytes

    def test_truncated_payload_rejected(self):
        chunk = PayloadChunk(uuid.uuid4().bytes, 0, 1, b"Twelve bytes")
        raw = serialize_chunk(chunk)
        # Chop off the last 4 bytes of payload
        truncated = raw[:-4]

        with pytest.raises(TruncatedChunkError):
            deserialize_chunk(truncated)

    def test_unexpected_trailing_bytes_rejected(self):
        chunk = PayloadChunk(uuid.uuid4().bytes, 0, 1, b"Twelve bytes")
        raw = serialize_chunk(chunk)
        with_extra = raw + b"EXTRA_TRAILING_GARBAGE"

        # By default allow_trailing=False -> raises MalformedChunkError
        with pytest.raises(MalformedChunkError, match="Unexpected trailing bytes"):
            deserialize_chunk(with_extra, allow_trailing=False)

        # When allow_trailing=True, succeeds and ignores trailing bytes
        parsed = deserialize_chunk(with_extra, allow_trailing=True)
        assert parsed.payload == b"Twelve bytes"

    def test_duplicate_chunk_in_reassembly(self):
        chunks = split_payload_equally(b"Testing duplicates", num_chunks=3)
        # Duplicate chunk 1: [0, 1, 1]
        corrupt_list = [chunks[0], chunks[1], chunks[1]]

        with pytest.raises(DuplicateChunkError):
            reassemble_chunks(corrupt_list)

    def test_missing_chunk_in_reassembly(self):
        chunks = split_payload_equally(b"Testing missing", num_chunks=3)
        # Drop chunk 1: [0, 2]
        incomplete_list = [chunks[0], chunks[2]]

        with pytest.raises(MissingChunkError, match="Missing indices: \\[1\\]"):
            reassemble_chunks(incomplete_list)

    def test_mismatched_message_ids_in_reassembly(self):
        chunks_a = split_payload_equally(b"Message A content", num_chunks=2)
        chunks_b = split_payload_equally(b"Message B content", num_chunks=2)

        # Mix chunk from message A and chunk from message B
        mixed = [chunks_a[0], chunks_b[1]]

        with pytest.raises(MessageIdMismatchError):
            reassemble_chunks(mixed)

    def test_mismatched_total_chunks(self):
        msg_id = uuid.uuid4().bytes
        c0 = PayloadChunk(msg_id, 0, 2, b"Part 0")
        c1 = PayloadChunk(msg_id, 1, 3, b"Part 1")  # Disagrees on total (3 vs 2)

        with pytest.raises(ChunkCountMismatchError):
            reassemble_chunks([c0, c1])

    def test_empty_reassemble_list(self):
        with pytest.raises(CodecError, match="chunks list is empty"):
            reassemble_chunks([])
