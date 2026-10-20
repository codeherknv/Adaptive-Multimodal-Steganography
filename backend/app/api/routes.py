"""FastAPI route definitions for health, system status, and cryptographic operations."""

from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, status

from app.config import settings
from app.core.crypto_utils import (
    KEY_SIZE_BYTES,
    generate_key,
    derive_key_from_password,
    validate_key,
    encrypt,
    decrypt,
    unpack_envelope,
    bytes_to_hex,
    bytes_from_hex,
    bytes_to_base64,
    bytes_from_base64,
    CryptoError,
    InvalidKeyError,
    MalformedEnvelopeError,
    DecryptionError,
)
from app.schemas import (
    HealthResponse,
    SystemStatusResponse,
    ModuleStatus,
    EncryptRequest,
    EncryptResponse,
    DecryptRequest,
    DecryptResponse,
)

router = APIRouter()


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Service Health Check",
    description="Returns service health status without disclosing internal environment or sensitive details."
)
async def get_health() -> HealthResponse:
    return HealthResponse(
        status="healthy",
        version=settings.VERSION,
        timestamp=datetime.now(timezone.utc)
    )


@router.get(
    "/status",
    response_model=SystemStatusResponse,
    summary="Project Implementation Status",
    description="Returns the actual completion state of research and engineering modules."
)
async def get_system_status() -> SystemStatusResponse:
    modules = {
        "infrastructure": ModuleStatus(
            name="Infrastructure & Monorepo",
            phase=1,
            status="implemented",
            description="Monorepo layout, FastAPI backend, React/Vite/TS frontend, and baseline docs.",
            capabilities=["Health Check API", "CORS Configuration", "Project Monorepo Scaffolding"]
        ),
        "cryptography": ModuleStatus(
            name="Authenticated Encryption (AES-256-GCM)",
            phase=2,
            status="implemented",
            description="AES-256-GCM encryption with fresh nonce, tag authentication, and versioned binary envelope framing.",
            capabilities=[
                "AES-256-GCM Authenticated Encryption",
                "Fresh 96-bit Nonces (NIST SP 800-38D)",
                "128-bit Authentication Tags",
                "PBKDF2-HMAC-SHA256 Key Derivation",
                "Tamper & Truncation Rejection",
                "Versioned Envelope Framing"
            ]
        ),
        "payload_codec": ModuleStatus(
            name="Versioned Binary Payload Codec",
            phase=2,
            status="implemented",
            description="Binary framing with magic bytes (b'ASTG'), message ID, chunk index, chunk count, and CRC32 validation.",
            capabilities=[
                "ASTG Magic Header (34 bytes)",
                "Version 1 Framing",
                "UUID4 Message Identifiers",
                "CRC32 Payload Checksums",
                "Deterministic Big-Endian Slicing",
                "Order-Independent Reassembly",
                "Missing/Duplicate/Mismatched Chunk Rejection"
            ]
        ),
        "image_stego": ModuleStatus(
            name="Spatial LSB Image Steganography",
            phase=3,
            status="pending",
            description="PNG LSB embedding and extraction with capacity checks and distortion metrics.",
            capabilities=[]
        ),
        "audio_stego": ModuleStatus(
            name="PCM WAV Audio Steganography",
            phase=5,
            status="pending",
            description="16-bit PCM WAV LSB embedding and extraction preserving audio headers.",
            capabilities=[]
        ),
        "video_stego": ModuleStatus(
            name="Frame-Based Video Steganography",
            phase=6,
            status="pending",
            description="Video frame extraction and embedding with container preservation.",
            capabilities=[]
        ),
        "allocation": ModuleStatus(
            name="Payload Allocation Engine",
            phase=7,
            status="pending",
            description="Fixed deterministic and empirical adaptive allocation across multimodal carriers.",
            capabilities=[]
        ),
        "steganalysis": ModuleStatus(
            name="ML Steganalysis Classifier",
            phase=8,
            status="pending",
            description="Cover vs. stego feature extraction and supervised classification baselines.",
            capabilities=[]
        ),
        "evaluation_lab": ModuleStatus(
            name="Evaluation & Benchmarking Laboratory",
            phase=9,
            status="pending",
            description="Systematic measurement of PSNR, SNR, BER, recovery reliability, and CSV export.",
            capabilities=[]
        )
    }

    return SystemStatusResponse(
        project_name=settings.PROJECT_NAME,
        version=settings.VERSION,
        current_phase=2,
        modules=modules
    )


# ---------------------------------------------------------
# Cryptographic Endpoints (Phase 2)
# ---------------------------------------------------------

@router.post(
    "/crypto/encrypt",
    response_model=EncryptResponse,
    status_code=status.HTTP_200_OK,
    summary="Encrypt Message with AES-256-GCM",
    description=(
        "Encrypts a plaintext message using AES-256-GCM with a fresh 96-bit nonce. "
        "Returns a self-contained binary envelope and the raw key separately."
    )
)
async def encrypt_message(req: EncryptRequest) -> EncryptResponse:
    salt_bytes = None
    salt_encoded = None

    # 1. Determine key source
    if req.key:
        try:
            key_bytes = bytes_from_base64(req.key) if req.encoding == "base64" else bytes_from_hex(req.key)
            validate_key(key_bytes)
        except InvalidKeyError as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    elif req.password:
        try:
            if req.salt:
                salt_bytes = bytes_from_base64(req.salt) if req.encoding == "base64" else bytes_from_hex(req.salt)
            key_bytes, salt_bytes = derive_key_from_password(req.password, salt=salt_bytes)
            salt_encoded = bytes_to_base64(salt_bytes) if req.encoding == "base64" else bytes_to_hex(salt_bytes)
        except InvalidKeyError as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    else:
        # Generate fresh random 256-bit key
        key_bytes = generate_key()

    # 2. Encrypt plaintext
    plaintext_bytes = req.plaintext.encode("utf-8")
    try:
        envelope_bytes = encrypt(plaintext_bytes, key_bytes)
    except CryptoError as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Encryption failed.")

    # 3. Unpack envelope components for granular response
    version, nonce_bytes, ciphertext_with_tag, _ = unpack_envelope(envelope_bytes)

    # 4. Encode according to requested format
    encode_func = bytes_to_base64 if req.encoding == "base64" else bytes_to_hex

    return EncryptResponse(
        key=encode_func(key_bytes),
        key_encoding=req.encoding,
        salt=salt_encoded,
        envelope_version=version,
        nonce=encode_func(nonce_bytes),
        ciphertext=encode_func(ciphertext_with_tag),
        envelope=encode_func(envelope_bytes),
        envelope_bytes_length=len(envelope_bytes),
        plaintext_bytes_length=len(plaintext_bytes)
    )


@router.post(
    "/crypto/decrypt",
    response_model=DecryptResponse,
    status_code=status.HTTP_200_OK,
    summary="Authenticate and Decrypt Ciphertext Envelope",
    description=(
        "Authenticates and decrypts an AES-256-GCM envelope. "
        "Verifies the 128-bit authentication tag before returning any plaintext."
    )
)
async def decrypt_message(req: DecryptRequest) -> DecryptResponse:
    decode_func = bytes_from_base64 if req.encoding == "base64" else bytes_from_hex

    # 1. Parse envelope bytes
    try:
        envelope_bytes = decode_func(req.envelope)
    except InvalidKeyError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Envelope decode error: {str(e)}"
        )

    # 2. Determine key source
    if req.key:
        try:
            key_bytes = decode_func(req.key)
            validate_key(key_bytes)
        except InvalidKeyError as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    elif req.password:
        try:
            if not req.salt:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Salt must be provided when decrypting with a password."
                )
            salt_bytes = decode_func(req.salt)
            key_bytes, _ = derive_key_from_password(req.password, salt=salt_bytes)
        except InvalidKeyError as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either 'key' or 'password' must be supplied."
        )

    # 3. Authenticate and decrypt envelope
    try:
        plaintext_bytes = decrypt(envelope_bytes, key_bytes)
        version, _, _, _ = unpack_envelope(envelope_bytes)
    except MalformedEnvelopeError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Malformed envelope structure: {str(e)}"
        )
    except DecryptionError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Decryption failed: integrity check failed or invalid key."
        )

    # 4. Decode plaintext as UTF-8
    try:
        plaintext_str = plaintext_bytes.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Decrypted payload contains invalid UTF-8 bytes."
        )

    return DecryptResponse(
        plaintext=plaintext_str,
        authenticated=True,
        envelope_version=version,
        plaintext_bytes_length=len(plaintext_bytes)
    )
