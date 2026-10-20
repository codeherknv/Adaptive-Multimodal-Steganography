"""Automated test suite for authenticated encryption (AES-256-GCM)."""

import os
import pytest
from app.core.crypto_utils import (
    KEY_SIZE_BYTES,
    NONCE_SIZE_BYTES,
    MINIMUM_ENVELOPE_SIZE,
    generate_key,
    derive_key_from_password,
    validate_key,
    encrypt,
    decrypt,
    encrypt_string,
    decrypt_to_string,
    bytes_to_hex,
    bytes_from_hex,
    bytes_to_base64,
    bytes_from_base64,
    InvalidKeyError,
    MalformedEnvelopeError,
    DecryptionError,
)


class TestKeyManagement:
    def test_generate_key_length_and_randomness(self):
        k1 = generate_key()
        k2 = generate_key()
        assert len(k1) == KEY_SIZE_BYTES
        assert len(k2) == KEY_SIZE_BYTES
        assert k1 != k2

    def test_validate_key(self):
        valid = os.urandom(32)
        validate_key(valid)  # Should not raise

        with pytest.raises(InvalidKeyError):
            validate_key(b"too_short")

        with pytest.raises(InvalidKeyError):
            validate_key(os.urandom(33))

        with pytest.raises(InvalidKeyError):
            validate_key("not_bytes")  # type: ignore

    def test_derive_key_from_password(self):
        pwd = "ResearchSecretPassword123!"
        key1, salt1 = derive_key_from_password(pwd)
        assert len(key1) == 32
        assert len(salt1) == 16

        # Deterministic with identical salt and iterations
        key2, salt2 = derive_key_from_password(pwd, salt=salt1, iterations=10_000)
        key3, _ = derive_key_from_password(pwd, salt=salt1, iterations=10_000)
        assert key2 == key3

        # Different password yields different key
        key_diff, _ = derive_key_from_password("DifferentPass!", salt=salt1, iterations=10_000)
        assert key2 != key_diff

    def test_derive_key_invalid_inputs(self):
        with pytest.raises(InvalidKeyError):
            derive_key_from_password("")

        with pytest.raises(InvalidKeyError):
            derive_key_from_password("valid_pwd", salt=b"short")

    def test_key_encoding_helpers(self):
        raw = os.urandom(32)
        h = bytes_to_hex(raw)
        assert bytes_from_hex(h) == raw

        b64 = bytes_to_base64(raw)
        assert bytes_from_base64(b64) == raw

        with pytest.raises(InvalidKeyError):
            bytes_from_hex("not_hex_string_zzz")

        with pytest.raises(InvalidKeyError):
            bytes_from_base64("not_valid_b64_??!!")


class TestEncryptionRoundTrip:
    def test_round_trip_ascii(self):
        key = generate_key()
        msg = b"Top Secret Payload: Target payload allocation = 33/33/34."
        envelope = encrypt(msg, key)
        decrypted = decrypt(envelope, key)
        assert decrypted == msg

    def test_round_trip_empty_plaintext(self):
        key = generate_key()
        msg = b""
        envelope = encrypt(msg, key)
        assert len(envelope) == MINIMUM_ENVELOPE_SIZE  # 14-byte header + 16-byte tag
        decrypted = decrypt(envelope, key)
        assert decrypted == b""

    def test_round_trip_unicode_and_emojis(self):
        key = generate_key()
        text = "🔒 Adaptive Stego Research 🚀 日本語 12345! \u2603 \U0001F600"
        envelope = encrypt_string(text, key)
        recovered = decrypt_to_string(envelope, key)
        assert recovered == text

    def test_round_trip_large_payload(self):
        key = generate_key()
        large_msg = os.urandom(256 * 1024)  # 256 KB
        envelope = encrypt(large_msg, key)
        assert len(envelope) == 14 + len(large_msg) + 16
        decrypted = decrypt(envelope, key)
        assert decrypted == large_msg

    def test_fresh_nonce_per_encryption(self):
        key = generate_key()
        msg = b"Constant message"
        envelopes = [encrypt(msg, key) for _ in range(50)]
        # Extract nonces (bytes 2 to 14)
        nonces = [env[2:14] for env in envelopes]
        assert len(set(nonces)) == 50  # All 50 nonces must be completely unique
        assert len(set(envelopes)) == 50

    def test_associated_data_authenticated(self):
        key = generate_key()
        msg = b"Authenticated context payload"
        aad = b"CarrierContext=PNG_Image_Chunk_0"

        envelope = encrypt(msg, key, associated_data=aad)
        decrypted = decrypt(envelope, key, associated_data=aad)
        assert decrypted == msg

        # Wrong AAD causes decryption failure
        with pytest.raises(DecryptionError):
            decrypt(envelope, key, associated_data=b"CarrierContext=WAV_Audio")

        # Missing AAD causes decryption failure
        with pytest.raises(DecryptionError):
            decrypt(envelope, key, associated_data=None)


class TestTamperingAndSecurityRejection:
    def test_wrong_key_rejected(self):
        key1 = generate_key()
        key2 = generate_key()
        envelope = encrypt(b"Secret payload", key1)

        with pytest.raises(DecryptionError):
            decrypt(envelope, key2)

    def test_ciphertext_tampering_rejected(self):
        key = generate_key()
        envelope = bytearray(encrypt(b"Immutable message", key))

        # Flip a single bit in the ciphertext payload
        envelope[20] ^= 0x01

        with pytest.raises(DecryptionError):
            decrypt(bytes(envelope), key)

    def test_tag_tampering_rejected(self):
        key = generate_key()
        envelope = bytearray(encrypt(b"Tag verification test", key))

        # Flip a bit in the last byte (auth tag)
        envelope[-1] ^= 0x01

        with pytest.raises(DecryptionError):
            decrypt(bytes(envelope), key)

    def test_nonce_tampering_rejected(self):
        key = generate_key()
        envelope = bytearray(encrypt(b"Nonce integrity check", key))

        # Flip a bit in the nonce (offset 2 to 13)
        envelope[5] ^= 0x01

        with pytest.raises(DecryptionError):
            decrypt(bytes(envelope), key)

    def test_envelope_version_tampering_rejected(self):
        key = generate_key()
        envelope = bytearray(encrypt(b"Version test", key))

        # Modify version byte from 0x01 to 0x02
        envelope[0] = 0x02

        with pytest.raises(MalformedEnvelopeError):
            decrypt(bytes(envelope), key)

    def test_truncated_envelope_rejected(self):
        key = generate_key()
        envelope = encrypt(b"Payload to truncate", key)

        # Truncate below minimum size
        with pytest.raises(MalformedEnvelopeError):
            decrypt(envelope[:20], key)

        # Truncate trailing tag bytes
        with pytest.raises(DecryptionError):
            decrypt(envelope[:-4], key)
