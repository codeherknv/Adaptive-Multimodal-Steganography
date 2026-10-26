"""FastAPI route definitions for health, status, crypto, and image steganography."""

import base64
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional, Tuple, Union
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
from app.media.audio_stego import (
    get_audio_capacity,
    embed_in_audio,
    extract_from_audio,
    AudioStegoError,
    InsufficientCapacityError as AudioCapacityError,
    CarrierExtractionError as AudioExtractionError,
    UnsupportedAudioFormatError,
)
from app.media.video_stego import (
    get_video_capacity,
    embed_in_video,
    extract_from_video,
    VideoStegoError,
    InsufficientCapacityError as VideoCapacityError,
    CarrierExtractionError as VideoExtractionError,
    UnsupportedVideoFormatError,
    CodecUnavailableError,
)
from app.allocation.profiler import (
    profile_multimodal_triad,
    ProfilingError,
    InvalidCarrierError,
)
from app.allocation.allocator import (
    get_allocation_strategy,
    AllocationError,
    MultimodalCapacityExceededError,
)
from app.allocation.engine import (
    embed_multimodal,
    extract_multimodal,
    unpack_stego_zip_bundle,
    MultimodalEngineError,
    CarrierExtractionMismatchError,
)
from app.steganalysis.features import (
    extract_image_features,
    extract_audio_features,
    extract_video_features,
    FeatureExtractionError,
)
from app.steganalysis.dataset_generator import (
    generate_modality_dataset,
    SteganalysisDataset,
)
from app.steganalysis.trainer import (
    train_steganalyzer,
    load_steganalyzer,
    TrainedSteganalyzer,
)
from app.steganalysis.classifier import (
    classify_media_file,
    detect_media_modality,
    ClassificationResult,
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
    AudioCapacityResponse,
    AudioQualityMetricsResponse,
    AudioEmbedResponse,
    AudioExtractResponse,
    VideoCapacityResponse,
    VideoQualityMetricsResponse,
    VideoEmbedResponse,
    VideoExtractResponse,
    ImageProfileResponse,
    AudioProfileResponse,
    VideoProfileResponse,
    MultimodalCarrierAllocationResponse,
    MultimodalAnalyzeResponse,
    MultimodalEmbedResponse,
    MultimodalExtractResponse,
    SteganalysisMetricsResponse,
    SteganalysisDatasetSummaryResponse,
    SteganalysisTrainRequest,
    SteganalysisTrainResponse,
    SteganalysisClassifyResponse,
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
            phase=4,
            status="implemented",
            description="16-bit & 8-bit PCM WAV LSB embedding and extraction with WSTG framing and header preservation.",
            capabilities=[
                "Uncompressed PCM WAV Sample LSB",
                "14-Byte Binary WSTG Framing",
                "Mono & Stereo Interleaved Sample Handling",
                "Audio Header & Duration Preservation",
                "CRC32 Pre-Check Integrity",
                "Audio Capacity Estimation",
                "Normalized MSE & SNR Distortion Metrics"
            ]
        ),
        "video_stego": ModuleStatus(
            name="Frame-Based Video Steganography",
            phase=5,
            status="implemented",
            description="Lossless video carrier (FFV1/AVI) multi-frame spatial LSB embedding and extraction with VSTG framing.",
            capabilities=[
                "Lossless Video Container Encoding (FFV1 / HFYU in AVI)",
                "14-Byte Binary VSTG Framing",
                "Multi-Frame Spatial LSB Embedding & Extraction",
                "Video Dimensions & FPS Preservation",
                "CRC32 Pre-Check Integrity",
                "Video Capacity Estimation",
                "Average Frame MSE & PSNR Distortion Metrics"
            ]
        ),
        "allocation": ModuleStatus(
            name="Payload Allocation Engine",
            phase=6,
            status="implemented",
            description="Fixed baseline and entropy-weighted adaptive allocation across Image, Audio, and Video.",
            capabilities=[
                "Multimodal Carrier Profiling (Laplacian, RMS, Motion Variance)",
                "Fixed Equal-Split Allocation with Overflow Water-Filling",
                "Adaptive Feature-Weighted Rate-Distortion Optimization",
                "ASTG Chunk Slicing & Header Capacity Accounting",
                "Unified Triad Embedding & Zip Bundling",
                "Cross-Carrier Consistent Reassembly & AES-256-GCM Verification"
            ]
        ),
        "steganalysis": ModuleStatus(
            name="ML Steganalysis Classifier",
            phase=7,
            status="implemented",
            description="Supervised statistical artifact feature extraction, zero-leakage training, and detectability evaluation across Image, Audio, and Video.",
            capabilities=[
                "First- & Second-Order Statistical Artifact Extraction",
                "Pairs of Values (PoV) & Difference Kurtosis Analysis",
                "Zero-Leakage GroupShuffleSplit Partitioning",
                "Random Forest & Logistic Regression Baseline Models",
                "Held-Out Test Detectability Evaluation (ROC-AUC, F1, Recall)",
                "Matched-Condition Strategy Comparison (Fixed vs. Adaptive)",
                "Single-Carrier Live Classification & Probability Scoring"
            ]
        ),
        "evaluation_lab": ModuleStatus(
            name="Evaluation & Benchmarking Laboratory",
            phase=8,
            status="pending",
            description="Systematic measurement of PSNR, SNR, BER, recovery reliability, and CSV export.",
            capabilities=[]
        )
    }

    return SystemStatusResponse(
        project_name=settings.PROJECT_NAME,
        version=settings.VERSION,
        current_phase=7,
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


# ---------------------------------------------------------
# Audio Steganography Endpoints (Phase 4)
# ---------------------------------------------------------

@router.post(
    "/audio/capacity",
    response_model=AudioCapacityResponse,
    status_code=status.HTTP_200_OK,
    summary="Estimate Audio Carrier Payload Capacity",
    description="Inspects an uploaded PCM WAV audio file and calculates its maximum usable LSB payload capacity."
)
async def check_audio_capacity(
    audio: UploadFile = File(..., description="PCM WAV audio carrier file")
) -> AudioCapacityResponse:
    contents = await audio.read()
    if len(contents) > settings.MAX_UPLOAD_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Uploaded file exceeds maximum limit of {settings.MAX_UPLOAD_SIZE_BYTES} bytes."
        )

    try:
        capacity_info = get_audio_capacity(contents)
        return AudioCapacityResponse(**capacity_info)
    except UnsupportedAudioFormatError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to process audio: {str(e)}"
        )


@router.post(
    "/audio/embed",
    response_model=AudioEmbedResponse,
    status_code=status.HTTP_200_OK,
    summary="Embed Encrypted Envelope into PCM WAV Audio",
    description="Embeds a Phase 2 encrypted envelope into an uncompressed PCM WAV audio file using sample LSB substitution."
)
async def embed_envelope_in_audio(
    audio: UploadFile = File(..., description="Cover PCM WAV audio carrier file"),
    envelope: str = Form(..., description="Encrypted binary envelope (from /crypto/encrypt)"),
    encoding: Literal["base64", "hex"] = Form("base64", description="Encoding of the supplied envelope")
) -> AudioEmbedResponse:
    contents = await audio.read()
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

    # 3. Embed into carrier audio
    try:
        stego_wav_bytes, metrics_dict = embed_in_audio(contents, envelope_bytes)
    except AudioCapacityError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except UnsupportedAudioFormatError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Audio embedding failed: {str(e)}"
        )

    # 4. Format stego audio as base64 data URL for playback and download
    b64_audio = base64.b64encode(stego_wav_bytes).decode("ascii")
    data_url = f"data:audio/wav;base64,{b64_audio}"

    quality_metrics = AudioQualityMetricsResponse(
        mse=metrics_dict["mse"],
        snr=metrics_dict["snr"],
        snr_display=metrics_dict["snr_display"],
        embedded_bytes=metrics_dict["embedded_bytes"],
        framed_bytes=metrics_dict["framed_bytes"],
        capacity_used_ratio=metrics_dict["capacity_used_ratio"],
        bits_per_sample_used=metrics_dict["bits_per_sample_used"],
    )

    filename_stem = audio.filename or "carrier.wav"
    if not filename_stem.lower().endswith(".wav"):
        filename_stem += ".wav"

    return AudioEmbedResponse(
        stego_audio_data_url=data_url,
        filename=f"stego_{filename_stem}",
        embedded_bytes=len(envelope_bytes),
        metrics=quality_metrics,
        message="Payload successfully embedded into WAV audio carrier using sample LSB."
    )


@router.post(
    "/audio/extract",
    response_model=AudioExtractResponse,
    status_code=status.HTTP_200_OK,
    summary="Extract Encrypted Envelope from Stego WAV Audio",
    description="Extracts the embedded Phase 2 envelope from a stego WAV audio file and verifies framing integrity."
)
async def extract_envelope_from_audio(
    audio: UploadFile = File(..., description="Stego PCM WAV audio carrier file"),
    encoding: Literal["base64", "hex"] = Form("base64", description="Desired output encoding format")
) -> AudioExtractResponse:
    contents = await audio.read()
    if len(contents) > settings.MAX_UPLOAD_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Uploaded file exceeds maximum limit of {settings.MAX_UPLOAD_SIZE_BYTES} bytes."
        )

    # 1. Extract payload bytes from audio
    try:
        extracted_bytes = extract_from_audio(contents)
    except AudioExtractionError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Extraction failed: {str(e)}"
        )
    except UnsupportedAudioFormatError as e:
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

    return AudioExtractResponse(
        envelope=encode_func(extracted_bytes),
        encoding=encoding,
        envelope_bytes_length=len(extracted_bytes),
        envelope_version=version,
        status="verified",
        message="Successfully extracted and verified authenticated envelope from WAV carrier."
    )


# ---------------------------------------------------------
# Video Steganography Endpoints (Phase 5)
# ---------------------------------------------------------

@router.post(
    "/video/capacity",
    response_model=VideoCapacityResponse,
    status_code=status.HTTP_200_OK,
    summary="Estimate Video Carrier Payload Capacity",
    description="Inspects an uploaded video file and calculates its maximum usable LSB payload capacity across frames."
)
async def check_video_capacity(
    video: UploadFile = File(..., description="Video carrier file")
) -> VideoCapacityResponse:
    contents = await video.read()
    if len(contents) > settings.MAX_UPLOAD_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Uploaded file exceeds maximum limit of {settings.MAX_UPLOAD_SIZE_BYTES} bytes."
        )

    try:
        capacity_info = get_video_capacity(contents)
        return VideoCapacityResponse(**capacity_info)
    except UnsupportedVideoFormatError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except CodecUnavailableError as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to process video: {str(e)}"
        )


@router.post(
    "/video/embed",
    response_model=VideoEmbedResponse,
    status_code=status.HTTP_200_OK,
    summary="Embed Encrypted Envelope into Video Frames",
    description="Embeds a Phase 2 encrypted envelope into video frames using spatial LSB substitution."
)
async def embed_envelope_in_video(
    video: UploadFile = File(..., description="Cover video carrier file"),
    envelope: str = Form(..., description="Encrypted binary envelope (from /crypto/encrypt)"),
    encoding: Literal["base64", "hex"] = Form("base64", description="Encoding of the supplied envelope")
) -> VideoEmbedResponse:
    contents = await video.read()
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

    # 3. Embed into carrier video
    try:
        stego_video_bytes, metrics_dict, preview_png_bytes = embed_in_video(contents, envelope_bytes)
    except VideoCapacityError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except UnsupportedVideoFormatError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except CodecUnavailableError as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Video embedding failed: {str(e)}"
        )

    # 4. Format stego video as base64 data URL for download and preview PNG
    b64_video = base64.b64encode(stego_video_bytes).decode("ascii")
    video_data_url = f"data:video/avi;base64,{b64_video}"

    b64_preview = base64.b64encode(preview_png_bytes).decode("ascii")
    preview_data_url = f"data:image/png;base64,{b64_preview}"

    quality_metrics = VideoQualityMetricsResponse(
        average_mse=metrics_dict["average_mse"],
        average_psnr=metrics_dict["average_psnr"],
        psnr_display=metrics_dict["psnr_display"],
        total_frames=metrics_dict["total_frames"],
        modified_frames=metrics_dict["modified_frames"],
        embedded_bytes=metrics_dict["embedded_bytes"],
        framed_bytes=metrics_dict["framed_bytes"],
        capacity_used_ratio=metrics_dict["capacity_used_ratio"],
        width=metrics_dict["width"],
        height=metrics_dict["height"],
        fps=metrics_dict["fps"],
        duration_seconds=metrics_dict["duration_seconds"],
    )

    filename_stem = video.filename or "carrier.avi"
    base_name = os.path.splitext(filename_stem)[0]

    return VideoEmbedResponse(
        stego_video_data_url=video_data_url,
        preview_frame_data_url=preview_data_url,
        filename=f"stego_{base_name}.avi",
        embedded_bytes=len(envelope_bytes),
        metrics=quality_metrics,
        message="Payload successfully embedded into video frames using spatial LSB."
    )


@router.post(
    "/video/extract",
    response_model=VideoExtractResponse,
    status_code=status.HTTP_200_OK,
    summary="Extract Encrypted Envelope from Stego Video",
    description="Extracts the embedded Phase 2 envelope from a stego video file and verifies VSTG framing integrity."
)
async def extract_envelope_from_video(
    video: UploadFile = File(..., description="Stego video carrier file"),
    encoding: Literal["base64", "hex"] = Form("base64", description="Desired output encoding format")
) -> VideoExtractResponse:
    contents = await video.read()
    if len(contents) > settings.MAX_UPLOAD_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Uploaded file exceeds maximum limit of {settings.MAX_UPLOAD_SIZE_BYTES} bytes."
        )

    # 1. Extract payload bytes from video
    try:
        extracted_bytes = extract_from_video(contents)
    except VideoExtractionError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Extraction failed: {str(e)}"
        )
    except UnsupportedVideoFormatError as e:
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

    return VideoExtractResponse(
        envelope=encode_func(extracted_bytes),
        encoding=encoding,
        envelope_bytes_length=len(extracted_bytes),
        envelope_version=version,
        status="verified",
        message="Successfully extracted and verified authenticated envelope from video carrier."
    )


# ---------------------------------------------------------
# Multimodal Allocation & Orchestration Endpoints (Phase 6)
# ---------------------------------------------------------

@router.post(
    "/multimodal/analyze",
    response_model=MultimodalAnalyzeResponse,
    status_code=status.HTTP_200_OK,
    summary="Profile Multimodal Carrier Triad",
    description="Inspects candidate Image, Audio, and Video carriers, calculating usable capacities and media complexity metrics."
)
async def analyze_multimodal_triad(
    image: UploadFile = File(..., description="Candidate PNG image file"),
    audio: UploadFile = File(..., description="Candidate WAV audio file"),
    video: UploadFile = File(..., description="Candidate AVI video file"),
    payload_length: Optional[int] = Form(None, description="Optional simulated payload length in bytes"),
    strategy: Literal["fixed", "adaptive"] = Form("adaptive", description="Simulated allocation strategy")
) -> MultimodalAnalyzeResponse:
    # 1. Read files
    img_bytes = await image.read()
    aud_bytes = await audio.read()
    vid_bytes = await video.read()

    for name, data in [("Image", img_bytes), ("Audio", aud_bytes), ("Video", vid_bytes)]:
        if len(data) > settings.MAX_UPLOAD_SIZE_BYTES:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"{name} file exceeds maximum upload size limit."
            )

    # 2. Profile carriers
    try:
        triad_profile = profile_multimodal_triad(img_bytes, aud_bytes, vid_bytes)
    except (InvalidCarrierError, ProfilingError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Carrier profiling failed: {str(e)}"
        )

    # 3. Optional simulated allocation
    simulated = None
    if payload_length is not None and payload_length > 0:
        try:
            alloc_strategy = get_allocation_strategy(strategy)
            sim_plan = alloc_strategy.allocate(payload_length, triad_profile)
            simulated = sim_plan.to_dict()
        except MultimodalCapacityExceededError as e:
            simulated = {"error": str(e), "exceeded": True}
        except AllocationError as e:
            simulated = {"error": str(e), "exceeded": True}

    return MultimodalAnalyzeResponse(
        image=ImageProfileResponse(**triad_profile.image.to_dict()),
        audio=AudioProfileResponse(**triad_profile.audio.to_dict()),
        video=VideoProfileResponse(**triad_profile.video.to_dict()),
        total_usable_capacity_bytes=triad_profile.total_usable_capacity_bytes,
        capacity_shares=triad_profile.capacity_shares,
        simulated_allocation=simulated,
        message="Multimodal carrier triad successfully profiled."
    )


@router.post(
    "/multimodal/embed",
    response_model=MultimodalEmbedResponse,
    status_code=status.HTTP_200_OK,
    summary="Embed Payload Across Multimodal Triad",
    description="Encrypts message, allocates chunks across Image, Audio, and Video, embeds with framing, and returns a downloadable ZIP bundle."
)
async def embed_payload_multimodal(
    message: str = Form(..., max_length=1_000_000, description="Secret message text to conceal"),
    strategy: Literal["fixed", "adaptive"] = Form("adaptive", description="Allocation strategy ('fixed' or 'adaptive')"),
    password: Optional[str] = Form(None, min_length=1, max_length=1024, description="Optional passphrase for key derivation"),
    key: Optional[str] = Form(None, description="Optional 32-byte AES key (base64 or hex)"),
    salt: Optional[str] = Form(None, description="Optional salt for password derivation"),
    encoding: Literal["base64", "hex"] = Form("base64", description="Key and salt encoding format"),
    image: UploadFile = File(..., description="Cover PNG image carrier"),
    audio: UploadFile = File(..., description="Cover WAV audio carrier"),
    video: UploadFile = File(..., description="Cover AVI video carrier"),
) -> MultimodalEmbedResponse:
    if key and password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provide either 'key' or 'password', not both."
        )

    # Decode key / salt if provided
    key_bytes = None
    salt_bytes = None
    decode_func = bytes_from_base64 if encoding == "base64" else bytes_from_hex

    if key:
        try:
            key_bytes = decode_func(key)
            validate_key(key_bytes)
        except InvalidKeyError as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    if salt:
        try:
            salt_bytes = decode_func(salt)
        except InvalidKeyError as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    # Read carrier files
    img_bytes = await image.read()
    aud_bytes = await audio.read()
    vid_bytes = await video.read()

    for name, data in [("Image", img_bytes), ("Audio", aud_bytes), ("Video", vid_bytes)]:
        if len(data) > settings.MAX_UPLOAD_SIZE_BYTES:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"{name} file exceeds maximum upload size limit."
            )

    try:
        res = embed_multimodal(
            message=message,
            image_bytes=img_bytes,
            audio_bytes=aud_bytes,
            video_bytes=vid_bytes,
            password=password,
            key_bytes=key_bytes,
            salt_bytes=salt_bytes,
            strategy_name=strategy,
        )
    except MultimodalCapacityExceededError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except (InvalidCarrierError, ProfilingError, AllocationError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except MultimodalEngineError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Multimodal embedding failed: {str(e)}"
        )

    # Format return data
    encode_func = bytes_to_base64 if encoding == "base64" else bytes_to_hex
    zip_b64 = base64.b64encode(res.zip_bundle_bytes).decode("ascii")
    preview_b64 = base64.b64encode(res.preview_frame_bytes).decode("ascii")

    alloc_dict = {
        k: MultimodalCarrierAllocationResponse(**v.to_dict())
        for k, v in res.allocation_plan.allocations.items()
    }

    metrics_consolidated = {
        "image": {
            "psnr_display": res.image_metrics.get("psnr_display", "N/A"),
            "mse": res.image_metrics.get("mse", 0.0),
            "ssim": res.image_metrics.get("ssim", 1.0),
        },
        "audio": {
            "snr_display": res.audio_metrics.get("snr_display", "N/A"),
            "mse": res.audio_metrics.get("normalized_mse", 0.0),
        },
        "video": {
            "psnr_display": res.video_metrics.get("psnr_display", "N/A"),
            "average_mse": res.video_metrics.get("average_mse", 0.0),
        },
    }

    return MultimodalEmbedResponse(
        zip_bundle_data_url=f"data:application/zip;base64,{zip_b64}",
        filename="stego_multimodal_bundle.zip",
        key=encode_func(res.key_bytes),
        key_encoding=encoding,
        salt=encode_func(res.salt_bytes) if res.salt_bytes else None,
        message_id=res.message_id_hex,
        strategy=res.allocation_plan.strategy_name,
        total_envelope_bytes=res.allocation_plan.total_payload_bytes,
        total_usable_capacity_bytes=res.allocation_plan.total_usable_capacity_bytes,
        overall_utilization_ratio=res.allocation_plan.overall_utilization_ratio,
        allocations=alloc_dict,
        metrics=metrics_consolidated,
        preview_frame_data_url=f"data:image/png;base64,{preview_b64}",
        manifest=res.manifest,
        message="Payload successfully partitioned, encrypted, and embedded across Image, Audio, and Video."
    )


@router.post(
    "/multimodal/extract",
    response_model=MultimodalExtractResponse,
    status_code=status.HTTP_200_OK,
    summary="Extract and Decrypt Payload from Multimodal Triad",
    description="Extracts chunks from all three carriers (or uploaded ZIP bundle), reassembles ASTG envelope, and authenticates decryption via AES-256-GCM."
)
async def extract_payload_multimodal(
    bundle_zip: Optional[UploadFile] = File(None, description="Stego multimodal ZIP bundle"),
    image: Optional[UploadFile] = File(None, description="Stego PNG image carrier"),
    audio: Optional[UploadFile] = File(None, description="Stego WAV audio carrier"),
    video: Optional[UploadFile] = File(None, description="Stego AVI video carrier"),
    key: Optional[str] = Form(None, description="The 32-byte AES-256 key"),
    password: Optional[str] = Form(None, description="Passphrase used during encryption"),
    salt: Optional[str] = Form(None, description="Salt for password derivation"),
    encoding: Literal["base64", "hex"] = Form("base64", description="Key and salt input encoding format"),
) -> MultimodalExtractResponse:
    if not key and not password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provide either 'key' or 'password' for decryption."
        )

    decode_func = bytes_from_base64 if encoding == "base64" else bytes_from_hex
    key_bytes = None
    salt_bytes = None

    if key:
        try:
            key_bytes = decode_func(key)
            validate_key(key_bytes)
        except InvalidKeyError as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    if salt:
        try:
            salt_bytes = decode_func(salt)
        except InvalidKeyError as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    manifest_dict = None

    # Option A: Uploaded ZIP bundle
    if bundle_zip is not None:
        zip_bytes = await bundle_zip.read()
        try:
            img_bytes, aud_bytes, vid_bytes, manifest_dict = unpack_stego_zip_bundle(zip_bytes)
        except MultimodalEngineError as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    # Option B: Uploaded 3 individual files
    elif image is not None and audio is not None and video is not None:
        img_bytes = await image.read()
        aud_bytes = await audio.read()
        vid_bytes = await video.read()
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provide either 'bundle_zip' OR all three individual carrier files ('image', 'audio', 'video')."
        )

    # Perform extraction and decryption
    try:
        ext_res = extract_multimodal(
            stego_image_bytes=img_bytes,
            stego_audio_bytes=aud_bytes,
            stego_video_bytes=vid_bytes,
            key_bytes=key_bytes,
            password=password,
            salt_bytes=salt_bytes,
            manifest_dict=manifest_dict,
        )
    except CarrierExtractionMismatchError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cross-carrier extraction mismatch: {str(e)}"
        )
    except MultimodalEngineError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Multimodal extraction failed: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Extraction or decryption failed: {str(e)}"
        )

    return MultimodalExtractResponse(
        plaintext=ext_res.plaintext,
        message_id=ext_res.message_id_hex,
        envelope_bytes_length=ext_res.envelope_bytes_length,
        chunk_count=ext_res.chunk_count,
        chunk_sizes=ext_res.chunk_sizes,
        verified=ext_res.verified,
        manifest=ext_res.manifest,
        message="Successfully authenticated, reassembled, and decrypted multimodal secret message."
    )


# ---------------------------------------------------------
# ML Steganalysis & Detectability Endpoints (Phase 7)
# ---------------------------------------------------------

# In-memory dataset cache for snappy development & experiment evaluation
_DATASET_CACHE: Dict[str, SteganalysisDataset] = {}


@router.post(
    "/steganalysis/dataset/generate",
    response_model=List[SteganalysisDatasetSummaryResponse],
    status_code=status.HTTP_200_OK,
    summary="Generate Labeled Steganalysis Dataset",
    description="Synthesizes diverse cover and stego media across image, audio, and video with labeled sample metadata."
)
async def generate_steganalysis_dataset(
    req: SteganalysisTrainRequest
) -> List[SteganalysisDatasetSummaryResponse]:
    target_modalities = ["image", "audio", "video"] if req.modality == "all" else [req.modality]
    summaries = []

    for m in target_modalities:
        ds = generate_modality_dataset(m, num_sources=req.num_sources)
        _DATASET_CACHE[m] = ds
        d = ds.to_dict()
        summaries.append(SteganalysisDatasetSummaryResponse(
            modality=m,
            total_samples=d["total_samples"],
            cover_count=d["cover_count"],
            stego_count=d["stego_count"],
            sources_count=d["sources_count"],
            feature_count=len(ds.feature_names),
            feature_names=ds.feature_names,
        ))

    return summaries


@router.get(
    "/steganalysis/dataset/summary",
    response_model=List[SteganalysisDatasetSummaryResponse],
    status_code=status.HTTP_200_OK,
    summary="Get Steganalysis Dataset Summary",
    description="Returns sample distribution and feature metadata for current cached datasets."
)
async def get_dataset_summary() -> List[SteganalysisDatasetSummaryResponse]:
    modalities = ["image", "audio", "video"]
    summaries = []

    for m in modalities:
        if m not in _DATASET_CACHE:
            _DATASET_CACHE[m] = generate_modality_dataset(m, num_sources=10)
        ds = _DATASET_CACHE[m]
        d = ds.to_dict()
        summaries.append(SteganalysisDatasetSummaryResponse(
            modality=m,
            total_samples=d["total_samples"],
            cover_count=d["cover_count"],
            stego_count=d["stego_count"],
            sources_count=d["sources_count"],
            feature_count=len(ds.feature_names),
            feature_names=ds.feature_names,
        ))

    return summaries


@router.post(
    "/steganalysis/train",
    response_model=List[SteganalysisTrainResponse],
    status_code=status.HTTP_200_OK,
    summary="Train Baseline Steganalyzer Model",
    description="Trains Random Forest or Logistic Regression with zero-leakage GroupShuffleSplit and evaluates detectability on held-out test data."
)
async def train_steganalysis_models(
    req: SteganalysisTrainRequest
) -> List[SteganalysisTrainResponse]:
    target_modalities = ["image", "audio", "video"] if req.modality == "all" else [req.modality]
    results = []

    for m in target_modalities:
        # Load or generate dataset
        if m not in _DATASET_CACHE or len(_DATASET_CACHE[m].samples) < req.num_sources:
            _DATASET_CACHE[m] = generate_modality_dataset(m, num_sources=req.num_sources)
        ds = _DATASET_CACHE[m]

        try:
            analyzer = train_steganalyzer(
                dataset=ds,
                model_type=req.model_type,
                test_size=0.25,
                random_state=42,
            )
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Training failed for {m}: {str(e)}"
            )

        results.append(SteganalysisTrainResponse(
            modality=m,
            model_type=req.model_type,
            train_sources_count=len(analyzer.train_sources),
            test_sources_count=len(analyzer.test_sources),
            training_metrics=SteganalysisMetricsResponse(**analyzer.training_metrics.to_dict()),
            test_metrics=SteganalysisMetricsResponse(**analyzer.test_metrics.to_dict()),
            trained_at=analyzer.trained_at,
            message=f"{req.model_type.replace('_', ' ').title()} successfully trained for {m} with zero-leakage group split."
        ))

    return results


@router.get(
    "/steganalysis/models",
    response_model=List[SteganalysisTrainResponse],
    status_code=status.HTTP_200_OK,
    summary="List Trained Steganalyzer Models",
    description="Returns available saved models and their out-of-sample held-out evaluation performance."
)
async def list_trained_models() -> List[SteganalysisTrainResponse]:
    results = []
    for m in ["image", "audio", "video"]:
        for mtype in ["random_forest", "logistic_regression"]:
            analyzer = load_steganalyzer(m, model_type=mtype)
            if analyzer is not None:
                results.append(SteganalysisTrainResponse(
                    modality=m,
                    model_type=mtype,
                    train_sources_count=len(analyzer.train_sources),
                    test_sources_count=len(analyzer.test_sources),
                    training_metrics=SteganalysisMetricsResponse(**analyzer.training_metrics.to_dict()),
                    test_metrics=SteganalysisMetricsResponse(**analyzer.test_metrics.to_dict()),
                    trained_at=analyzer.trained_at,
                    message="Model loaded from disk."
                ))
    return results


@router.post(
    "/steganalysis/classify",
    response_model=SteganalysisClassifyResponse,
    status_code=status.HTTP_200_OK,
    summary="Classify Media File (Cover vs. Stego)",
    description="Extracts statistical artifact features from an uploaded PNG, WAV, or AVI file and predicts Cover vs. Stego class."
)
async def classify_single_media_file(
    file: UploadFile = File(..., description="Uploaded media carrier (PNG, WAV, or AVI)"),
    model_type: Literal["random_forest", "logistic_regression"] = Form(
        "random_forest",
        description="Classifier architecture ('random_forest' or 'logistic_regression')"
    )
) -> SteganalysisClassifyResponse:
    contents = await file.read()
    if len(contents) > settings.MAX_UPLOAD_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Uploaded file exceeds maximum limit of {settings.MAX_UPLOAD_SIZE_BYTES} bytes."
        )

    filename = file.filename or "uploaded_media"
    try:
        result = classify_media_file(
            file_bytes=contents,
            filename=filename,
            model_type=model_type,
        )
    except FeatureExtractionError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Feature extraction failed: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Steganalysis inference failed: {str(e)}"
        )

    return SteganalysisClassifyResponse(
        modality=result.modality,
        filename=result.filename,
        predicted_label=result.predicted_label,
        predicted_class=result.predicted_class,
        stego_probability=result.stego_probability,
        confidence_percentage=result.confidence_percentage,
        model_type=result.model_type,
        feature_values=result.feature_values,
        disclaimer=result.disclaimer,
    )


