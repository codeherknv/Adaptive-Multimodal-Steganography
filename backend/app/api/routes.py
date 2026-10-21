"""FastAPI route definitions for health, status, crypto, and image steganography."""

import base64
from datetime import datetime, timezone
from typing import Literal
from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status

from app.config import settings
from app.core.crypto_utils import (
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
from app.media.image_stego import (
    get_image_capacity,
    embed_in_image,
    extract_from_image,
    save_image_to_png_bytes,
    load_image_as_rgb_array,
    InsufficientCapacityError,
    CarrierExtractionError,
    UnsupportedImageFormatError,
)
from app.schemas import (
    HealthResponse,
    SystemStatusResponse,
    ModuleStatus,
    EncryptRequest,
    EncryptResponse,
    DecryptRequest,
    DecryptResponse,
    ImageCapacityResponse,
    ImageQualityMetricsResponse,
    ImageEmbedResponse,
    ImageExtractResponse,
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
            status="implemented",
            description="Lossless PNG LSB embedding and extraction with length-prefixed binary framing and quality metrics.",
            capabilities=[
                "Lossless PNG Spatial LSB",
                "14-Byte Binary PSTG Framing",
                "RGB Channel Preservation (Alpha untouched)",
                "CRC32 Pre-Check Integrity",
                "Capacity Estimation",
                "MSE, PSNR, SSIM Distortion Metrics"
            ]
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
        current_phase=3,
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
        key_bytes = generate_key()

    plaintext_bytes = req.plaintext.encode("utf-8")
    try:
        envelope_bytes = encrypt(plaintext_bytes, key_bytes)
    except CryptoError:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Encryption failed.")

    version, nonce_bytes, ciphertext_with_tag, _ = unpack_envelope(envelope_bytes)
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

    try:
        envelope_bytes = decode_func(req.envelope)
    except InvalidKeyError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Envelope decode error: {str(e)}"
        )

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


# ---------------------------------------------------------
# Image Steganography Endpoints (Phase 3)
# ---------------------------------------------------------

@router.post(
    "/image/capacity",
    response_model=ImageCapacityResponse,
    status_code=status.HTTP_200_OK,
    summary="Estimate Image Carrier Payload Capacity",
    description="Inspects an uploaded PNG image and calculates its maximum usable LSB payload capacity."
)
async def check_image_capacity(
    image: UploadFile = File(..., description="PNG image carrier file")
) -> ImageCapacityResponse:
    contents = await image.read()
    if len(contents) > settings.MAX_UPLOAD_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Uploaded file exceeds maximum limit of {settings.MAX_UPLOAD_SIZE_BYTES} bytes."
        )

    try:
        capacity_info = get_image_capacity(contents)
        return ImageCapacityResponse(**capacity_info)
    except UnsupportedImageFormatError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to process image: {str(e)}"
        )


@router.post(
    "/image/embed",
    response_model=ImageEmbedResponse,
    status_code=status.HTTP_200_OK,
    summary="Embed Encrypted Envelope into PNG Image",
    description="Embeds a Phase 2 encrypted envelope into a PNG image using spatial LSB substitution."
)
async def embed_envelope_in_image(
    image: UploadFile = File(..., description="Cover PNG image carrier file"),
    envelope: str = Form(..., description="Encrypted binary envelope (from /crypto/encrypt)"),
    encoding: Literal["base64", "hex"] = Form("base64", description="Encoding of the supplied envelope")
) -> ImageEmbedResponse:
    contents = await image.read()
    if len(contents) > settings.MAX_UPLOAD_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Uploaded file exceeds maximum limit of {settings.MAX_UPLOAD_SIZE_BYTES} bytes."
        )

    # 1. Decode envelope string to bytes
    try:
        envelope_bytes = bytes_from_base64(envelope) if encoding == "base64" else bytes_from_hex(envelope)
    except InvalidKeyError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid envelope {encoding} encoding: {str(e)}"
        )

    # 2. Validate that the payload is a valid Phase 2 envelope
    try:
        unpack_envelope(envelope_bytes)
    except MalformedEnvelopeError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Payload is not a valid encrypted envelope: {str(e)}"
        )

    # 3. Embed into carrier image
    try:
        stego_array, metrics_dict = embed_in_image(contents, envelope_bytes)
        _, mode = load_image_as_rgb_array(contents)
        stego_png_bytes = save_image_to_png_bytes(stego_array, mode=mode)
    except InsufficientCapacityError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except UnsupportedImageFormatError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Image embedding failed: {str(e)}"
        )

    # 4. Format stego image as base64 data URL for instant browser preview and download
    b64_img = base64.b64encode(stego_png_bytes).decode("ascii")
    data_url = f"data:image/png;base64,{b64_img}"

    quality_metrics = ImageQualityMetricsResponse(
        mse=metrics_dict["mse"],
        psnr=metrics_dict["psnr"],
        psnr_display=metrics_dict["psnr_display"],
        ssim=metrics_dict["ssim"],
        embedded_bytes=metrics_dict["embedded_bytes"],
        framed_bytes=metrics_dict["framed_bytes"],
        capacity_used_ratio=metrics_dict["capacity_used_ratio"],
        bits_per_pixel=metrics_dict["bits_per_pixel"],
    )

    return ImageEmbedResponse(
        stego_image_data_url=data_url,
        filename=f"stego_{image.filename or 'carrier.png'}",
        embedded_bytes=len(envelope_bytes),
        metrics=quality_metrics,
        message="Payload successfully embedded into PNG carrier using spatial LSB."
    )


@router.post(
    "/image/extract",
    response_model=ImageExtractResponse,
    status_code=status.HTTP_200_OK,
    summary="Extract Encrypted Envelope from Stego PNG Image",
    description="Extracts the embedded Phase 2 envelope from a stego PNG image and verifies framing integrity."
)
async def extract_envelope_from_image(
    image: UploadFile = File(..., description="Stego PNG image carrier file"),
    encoding: Literal["base64", "hex"] = Form("base64", description="Desired output encoding format")
) -> ImageExtractResponse:
    contents = await image.read()
    if len(contents) > settings.MAX_UPLOAD_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Uploaded file exceeds maximum limit of {settings.MAX_UPLOAD_SIZE_BYTES} bytes."
        )

    # 1. Extract payload bytes from image
    try:
        extracted_bytes = extract_from_image(contents)
    except CarrierExtractionError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Extraction failed: {str(e)}"
        )
    except UnsupportedImageFormatError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Carrier extraction failed: {str(e)}"
        )

    # 2. Validate extracted payload as a Phase 2 envelope
    try:
        version, _, _, _ = unpack_envelope(extracted_bytes)
    except MalformedEnvelopeError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Extracted payload is not a valid encrypted envelope: {str(e)}"
        )

    # 3. Format envelope
    encode_func = bytes_to_base64 if encoding == "base64" else bytes_to_hex

    return ImageExtractResponse(
        envelope=encode_func(extracted_bytes),
        encoding=encoding,
        envelope_bytes_length=len(extracted_bytes),
        envelope_version=version,
        status="verified",
        message="Successfully extracted and verified authenticated envelope from PNG carrier."
    )
