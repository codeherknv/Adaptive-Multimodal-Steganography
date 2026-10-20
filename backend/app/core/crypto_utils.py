"""Authenticated encryption utilities for AES-256-GCM.

This module provides industry-standard authenticated symmetric encryption
using Python's `cryptography` library.

Key Architectural Decisions for Students:
1. Algorithm: AES-256-GCM (Galois/Counter Mode).
   - Provides both Confidentiality (secrecy) and Integrity/Authenticity.
   - Any tampering with ciphertext, nonce, or authenticated metadata causes
     decryption to fail before any unverified plaintext is returned.
2. Nonce Management:
   - Exactly 96 bits (12 bytes) as recommended by NIST SP 800-38D.
   - A FRESH, cryptographically random nonce is generated via `os.urandom(12)`
     for every single encryption call. Nonce reuse in GCM is catastrophic and
     would compromise both authenticity and confidentiality.
3. Binary Envelope Framing:
   - 1 byte: Envelope version (0x01)
   - 1 byte: Reserved flags (0x00)
   - 12 bytes: 96-bit Nonce
   - Remaining bytes: Ciphertext + 16-byte GCM Authentication Tag
   - The 2-byte header is passed as Additional Authenticated Data (AAD) into AES-GCM
     so that even the envelope version cannot be modified without detection.
4. Key Management:
   - AES-256 requires exactly 32 bytes (256 bits).
   - Educational workflow generates random 32-byte keys returned separately to the user.
   - Password derivation is implemented using PBKDF2-HMAC-SHA256 with 600,000 iterations
     and a random 16-byte salt per OWASP recommendations.
   - Keys are NEVER embedded into carrier media or committed to version control.
"""

import base64
import binascii
import os
import struct
from typing import Optional, Tuple

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

# Constants
KEY_SIZE_BYTES = 32          # 256 bits
NONCE_SIZE_BYTES = 12        # 96 bits (NIST SP 800-38D recommended for GCM)
TAG_SIZE_BYTES = 16          # 128 bits
SALT_SIZE_BYTES = 16         # 128 bits for PBKDF2 salt
PBKDF2_ITERATIONS = 600_000  # OWASP recommendation for PBKDF2-HMAC-SHA256
ENVELOPE_VERSION = 1
ENVELOPE_HEADER_FORMAT = ">BB12s"  # Version (1B), Reserved (1B), Nonce (12B)
ENVELOPE_HEADER_SIZE = struct.calcsize(ENVELOPE_HEADER_FORMAT)  # 14 bytes
MINIMUM_ENVELOPE_SIZE = ENVELOPE_HEADER_SIZE + TAG_SIZE_BYTES   # 30 bytes (for 0-byte plaintext)


class CryptoError(Exception):
    """Base exception for cryptographic operations."""
    pass


class InvalidKeyError(CryptoError):
    """Raised when an encryption key has an invalid length or format."""
    pass


class MalformedEnvelopeError(CryptoError):
    """Raised when an encrypted envelope has an invalid structure or header."""
    pass


class DecryptionError(CryptoError):
    """Raised when authenticated decryption fails (tampered data, bad key, or corrupt tag)."""
    pass


def generate_key() -> bytes:
    """Generate a cryptographically secure 256-bit (32-byte) AES key.

    Returns:
        32 random bytes generated from OS CSPRNG.
    """
    return os.urandom(KEY_SIZE_BYTES)


def derive_key_from_password(
    password: str,
    salt: Optional[bytes] = None,
    iterations: int = PBKDF2_ITERATIONS
) -> Tuple[bytes, bytes]:
    """Derive a 256-bit AES key from a human passphrase using PBKDF2-HMAC-SHA256.

    Educational Note:
    Passwords have much lower entropy than random keys. PBKDF2 with a high iteration
    count (e.g. 600,000) and a unique salt makes brute-force attacks computationally
    expensive. Never use unsalted fast hashes (e.g. MD5 or SHA-256) as a password KDF.

    Args:
        password: Plaintext password string.
        salt: Optional 16-byte salt. If None, a fresh random salt is generated.
        iterations: Number of HMAC iterations (default 600,000).

    Returns:
        Tuple of (32-byte derived key, 16-byte salt).

    Raises:
        InvalidKeyError: If password is empty or salt has invalid length.
    """
    if not password:
        raise InvalidKeyError("Password cannot be empty.")
    
    if salt is None:
        salt = os.urandom(SALT_SIZE_BYTES)
    elif len(salt) < 16:
        raise InvalidKeyError(f"Salt must be at least 16 bytes; got {len(salt)} bytes.")

    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=KEY_SIZE_BYTES,
        salt=salt,
        iterations=iterations,
        backend=default_backend()
    )
    derived_key = kdf.derive(password.encode("utf-8"))
    return derived_key, salt


def validate_key(key: bytes) -> None:
    """Ensure key is exactly 32 bytes.

    Args:
        key: Raw key bytes to validate.

    Raises:
        InvalidKeyError: If key is not exactly 32 bytes.
    """
    if not isinstance(key, (bytes, bytearray)):
        raise InvalidKeyError("Key must be bytes.")
    if len(key) != KEY_SIZE_BYTES:
        raise InvalidKeyError(
            f"AES-256 key must be exactly {KEY_SIZE_BYTES} bytes (256 bits); got {len(key)} bytes."
        )


def pack_envelope(nonce: bytes, ciphertext_with_tag: bytes) -> bytes:
    """Pack nonce and ciphertext with authentication tag into a versioned binary envelope.

    Envelope Layout:
    [0:1]   - Version (uint8, 0x01)
    [1:2]   - Reserved (uint8, 0x00)
    [2:14]  - Nonce (12 bytes)
    [14:]   - Ciphertext + 16-byte GCM authentication tag

    Args:
        nonce: Exactly 12 bytes.
        ciphertext_with_tag: Ciphertext including 16-byte GCM tag.

    Returns:
        Packed binary envelope bytes.
    """
    if len(nonce) != NONCE_SIZE_BYTES:
        raise MalformedEnvelopeError(
            f"Nonce must be exactly {NONCE_SIZE_BYTES} bytes; got {len(nonce)} bytes."
        )
    if len(ciphertext_with_tag) < TAG_SIZE_BYTES:
        raise MalformedEnvelopeError(
            f"Ciphertext payload must be at least {TAG_SIZE_BYTES} bytes for auth tag."
        )

    header = struct.pack(ENVELOPE_HEADER_FORMAT, ENVELOPE_VERSION, 0, nonce)
    return header + ciphertext_with_tag


def unpack_envelope(envelope: bytes) -> Tuple[int, bytes, bytes, bytes]:
    """Parse and validate a versioned binary envelope.

    Args:
        envelope: Binary envelope bytes.

    Returns:
        Tuple of (version, nonce, ciphertext_with_tag, aad_header).

    Raises:
        MalformedEnvelopeError: If envelope is truncated or version unsupported.
    """
    if not isinstance(envelope, (bytes, bytearray)):
        raise MalformedEnvelopeError("Envelope must be bytes.")

    if len(envelope) < MINIMUM_ENVELOPE_SIZE:
        raise MalformedEnvelopeError(
            f"Envelope is truncated: expected at least {MINIMUM_ENVELOPE_SIZE} bytes, got {len(envelope)} bytes."
        )

    version, reserved, nonce = struct.unpack(ENVELOPE_HEADER_FORMAT, envelope[:ENVELOPE_HEADER_SIZE])

    if version != ENVELOPE_VERSION:
        raise MalformedEnvelopeError(
            f"Unsupported envelope version: expected {ENVELOPE_VERSION}, got {version}."
        )

    aad_header = envelope[:2]  # Authenticate version + reserved byte
    ciphertext_with_tag = envelope[ENVELOPE_HEADER_SIZE:]

    return version, nonce, ciphertext_with_tag, aad_header


def encrypt(
    plaintext: bytes,
    key: bytes,
    associated_data: Optional[bytes] = None
) -> bytes:
    """Encrypt plaintext using AES-256-GCM and return a versioned binary envelope.

    Educational Note:
    The 2-byte envelope header (version + reserved) is automatically concatenated
    with any caller-provided associated_data to form the authenticated data (AAD).
    This ensures an attacker cannot modify envelope metadata without causing an
    authenticated tag failure.

    Args:
        plaintext: Raw data bytes to encrypt (can be empty b"").
        key: Exactly 32 bytes (256-bit AES key).
        associated_data: Optional additional data to authenticate (not encrypted).

    Returns:
        Self-contained versioned binary envelope bytes.

    Raises:
        InvalidKeyError: If key is not 32 bytes.
        CryptoError: If encryption fails.
    """
    validate_key(key)
    
    # 1. Generate fresh 96-bit nonce
    nonce = os.urandom(NONCE_SIZE_BYTES)

    # 2. Prepare AAD: envelope header prefix + optional caller data
    header_aad = struct.pack(">BB", ENVELOPE_VERSION, 0)
    full_aad = header_aad if associated_data is None else header_aad + associated_data

    # 3. Encrypt via AESGCM (appends 16-byte tag automatically)
    aesgcm = AESGCM(key)
    try:
        ciphertext_with_tag = aesgcm.encrypt(nonce, plaintext, full_aad)
    except Exception as e:
        raise CryptoError(f"Encryption failed: {str(e)}") from e

    # 4. Pack into envelope
    return pack_envelope(nonce, ciphertext_with_tag)


def decrypt(
    envelope: bytes,
    key: bytes,
    associated_data: Optional[bytes] = None
) -> bytes:
    """Authenticate and decrypt a versioned binary envelope using AES-256-GCM.

    Educational Note:
    AES-GCM verifies the 128-bit authentication tag before returning any decrypted
    bytes. If the ciphertext, nonce, key, or associated data has been tampered with
    even by a single bit, verification fails and a `DecryptionError` is raised.

    Security Warning:
    To prevent padding or error oracle side-channel leaks, we avoid revealing whether
    the failure was caused by an incorrect key vs tampered ciphertext.

    Args:
        envelope: Binary envelope bytes produced by `encrypt()`.
        key: Exactly 32 bytes (256-bit AES key).
        associated_data: Optional additional data to authenticate (must match encryption).

    Returns:
        Verified plaintext bytes.

    Raises:
        InvalidKeyError: If key is not 32 bytes.
        MalformedEnvelopeError: If envelope framing or version is invalid.
        DecryptionError: If authentication tag verification fails (bad key or tampered data).
    """
    validate_key(key)
    version, nonce, ciphertext_with_tag, aad_header = unpack_envelope(envelope)

    # Reconstruct exact AAD used during encryption
    full_aad = aad_header if associated_data is None else aad_header + associated_data

    aesgcm = AESGCM(key)
    try:
        plaintext = aesgcm.decrypt(nonce, ciphertext_with_tag, full_aad)
        return plaintext
    except InvalidTag as e:
        raise DecryptionError(
            "Decryption failed: Authentication tag verification failed. "
            "Data may be corrupted, tampered with, or decrypted with an incorrect key."
        ) from e
    except Exception as e:
        raise DecryptionError(f"Decryption failed: {str(e)}") from e


def encrypt_string(plaintext: str, key: bytes) -> bytes:
    """Convenience helper to encrypt a UTF-8 string."""
    return encrypt(plaintext.encode("utf-8"), key)


def decrypt_to_string(envelope: bytes, key: bytes) -> str:
    """Convenience helper to decrypt an envelope and decode as UTF-8 string."""
    plaintext_bytes = decrypt(envelope, key)
    try:
        return plaintext_bytes.decode("utf-8")
    except UnicodeDecodeError as e:
        raise DecryptionError(f"Decrypted payload is not valid UTF-8 text: {str(e)}") from e


# Key & Byte Encoding Utilities
def bytes_to_hex(data: bytes) -> str:
    return binascii.hexlify(data).decode("ascii")


def bytes_from_hex(hex_str: str) -> bytes:
    try:
        clean = hex_str.strip()
        return binascii.unhexlify(clean)
    except (binascii.Error, ValueError) as e:
        raise InvalidKeyError(f"Invalid hexadecimal encoding: {str(e)}") from e


def bytes_to_base64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def bytes_from_base64(b64_str: str) -> bytes:
    try:
        clean = b64_str.strip()
        return base64.b64decode(clean, validate=True)
    except (binascii.Error, ValueError) as e:
        raise InvalidKeyError(f"Invalid base64 encoding: {str(e)}") from e
