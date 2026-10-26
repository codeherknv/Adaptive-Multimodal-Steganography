"""Unified multimodal orchestration engine for embedding and extracting steganographic payloads.

This module coordinates the complete multimodal pipeline:
1. Embedding:
   - Encrypts plaintext via AES-256-GCM authenticated encryption (crypto_utils).
   - Profiles candidate Image, Audio, and Video carriers (profiler).
   - Allocates envelope slices using Fixed Baseline or Adaptive Feature strategy (allocator).
   - Slices and frames the envelope into 3 ASTG binary chunks (payload_codec).
   - Embeds chunks into PNG, WAV, and AVI carriers (image_stego, audio_stego, video_stego).
   - Computes objective fidelity metrics across all three media.
   - Generates a non-secret manifest and bundles all carriers into an in-memory ZIP archive.
2. Extraction:
   - Extracts raw chunks from all three stego carriers (or directly from a ZIP bundle).
   - Validates ASTG chunk framing, CRC32, message UUID matching, and chunk index completeness.
   - Reassembles the bit-exact encrypted envelope.
   - Authenticates and decrypts via AES-256-GCM.
   - Returns verified plaintext only after tag authentication succeeds.

Zero-Knowledge & Operational Security Guarantees:
------------------------------------------------
1. Encryption keys, passphrases, and plaintexts are NEVER written into carrier metadata,
   manifest files, or application logs.
2. The manifest contains only non-secret operational metadata: chunk indices, carrier types,
   byte sizes, distortion metrics, and timestamps.
3. Decryption strictly enforces AES-256-GCM authentication. Any tampered carrier, corrupt
   chunk, or wrong key triggers safe error handling without leaking error oracle details.
"""

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import io
import json
from typing import Any, Dict, List, Literal, Optional, Tuple, Union
import uuid
import zipfile

from app.core.crypto_utils import (
    CryptoError,
    DecryptionError,
    InvalidKeyError,
    MalformedEnvelopeError,
    decrypt,
    derive_key_from_password,
    encrypt,
    generate_key,
    validate_key,
)
from app.core.payload_codec import (
    CodecError,
    PayloadChunk,
    deserialize_chunk,
    reassemble_chunks,
    serialize_chunk,
)
from app.media.image_stego import (
    ImageStegoError,
    embed_in_image,
    extract_from_image,
    save_image_to_png_bytes,
)
from app.media.audio_stego import (
    AudioStegoError,
    embed_in_audio,
    extract_from_audio,
)
from app.media.video_stego import (
    VideoStegoError,
    embed_in_video,
    extract_from_video,
)
from app.allocation.profiler import (
    InvalidCarrierError,
    MultimodalTriadProfile,
    profile_multimodal_triad,
)
from app.allocation.allocator import (
    AllocationError,
    AllocationPlan,
    MultimodalCapacityExceededError,
    get_allocation_strategy,
)


class MultimodalEngineError(Exception):
    """Base exception for multimodal orchestration errors."""
    pass


class CarrierExtractionMismatchError(MultimodalEngineError):
    """Raised when extracted chunks from carriers do not form a consistent message."""
    pass


@dataclass(frozen=True)
class MultimodalEmbeddingResult:
    """Consolidated result of a multimodal embedding operation."""
    stego_image_bytes: bytes
    stego_audio_bytes: bytes
    stego_video_bytes: bytes
    preview_frame_bytes: bytes
    zip_bundle_bytes: bytes
    manifest: Dict[str, Any]
    allocation_plan: AllocationPlan
    image_metrics: Dict[str, Any]
    audio_metrics: Dict[str, Any]
    video_metrics: Dict[str, Any]
    key_bytes: bytes
    salt_bytes: Optional[bytes]
    message_id_hex: str


@dataclass(frozen=True)
class MultimodalExtractionResult:
    """Consolidated result of a multimodal extraction operation."""
    plaintext: str
    message_id_hex: str
    envelope_bytes_length: int
    chunk_count: int
    chunk_sizes: Dict[str, int]
    verified: bool
    manifest: Optional[Dict[str, Any]] = None


def create_stego_zip_bundle(
    stego_image_bytes: bytes,
    stego_audio_bytes: bytes,
    stego_video_bytes: bytes,
    manifest_dict: Dict[str, Any],
) -> bytes:
    """Package the 3 stego carrier files and non-secret manifest into an in-memory ZIP archive.

    Args:
        stego_image_bytes: Lossless PNG stego image bytes.
        stego_audio_bytes: Uncompressed PCM WAV stego audio bytes.
        stego_video_bytes: Lossless AVI stego video bytes.
        manifest_dict: Non-secret metadata manifest.

    Returns:
        Raw bytes of the ZIP archive.
    """
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("stego_carrier.png", stego_image_bytes)
        zf.writestr("stego_carrier.wav", stego_audio_bytes)
        zf.writestr("stego_carrier.avi", stego_video_bytes)
        manifest_json = json.dumps(manifest_dict, indent=2)
        zf.writestr("manifest.json", manifest_json.encode("utf-8"))

    return buf.getvalue()


def unpack_stego_zip_bundle(
    zip_bytes: bytes
) -> Tuple[bytes, bytes, bytes, Optional[Dict[str, Any]]]:
    """Unpack a multimodal stego ZIP archive into its constituent carriers and manifest.

    Args:
        zip_bytes: Raw bytes of the uploaded ZIP file.

    Returns:
        Tuple of (image_bytes, audio_bytes, video_bytes, manifest_or_none).

    Raises:
        MultimodalEngineError: If archive is invalid or missing required carrier files.
    """
    try:
        buf = io.BytesIO(zip_bytes)
        with zipfile.ZipFile(buf, mode="r") as zf:
            file_names = set(zf.namelist())

            # Find matching carrier files by extension or canonical name
            png_name = next((f for f in file_names if f.endswith(".png")), None)
            wav_name = next((f for f in file_names if f.endswith(".wav")), None)
            avi_name = next((f for f in file_names if f.endswith((".avi", ".mkv"))), None)

            if not png_name or not wav_name or not avi_name:
                missing = []
                if not png_name: missing.append("PNG Image (*.png)")
                if not wav_name: missing.append("WAV Audio (*.wav)")
                if not avi_name: missing.append("AVI/MKV Video (*.avi, *.mkv)")
                raise MultimodalEngineError(
                    f"Uploaded ZIP bundle is incomplete. Missing required carrier(s): {', '.join(missing)}."
                )

            img_bytes = zf.read(png_name)
            aud_bytes = zf.read(wav_name)
            vid_bytes = zf.read(avi_name)

            manifest_dict: Optional[Dict[str, Any]] = None
            if "manifest.json" in file_names:
                try:
                    manifest_raw = zf.read("manifest.json").decode("utf-8")
                    manifest_dict = json.loads(manifest_raw)
                except Exception:
                    pass  # Non-fatal: manifest is informative only

            return img_bytes, aud_bytes, vid_bytes, manifest_dict
    except zipfile.BadZipFile as e:
        raise MultimodalEngineError("The provided file is not a valid ZIP archive.") from e
    except MultimodalEngineError:
        raise
    except Exception as e:
        raise MultimodalEngineError(f"Failed to unpack ZIP archive: {str(e)}") from e


def embed_multimodal(
    message: str,
    image_bytes: bytes,
    audio_bytes: bytes,
    video_bytes: bytes,
    password: Optional[str] = None,
    key_bytes: Optional[bytes] = None,
    salt_bytes: Optional[bytes] = None,
    strategy_name: Literal["fixed", "adaptive"] = "adaptive",
    weights_config: Optional[Dict[str, float]] = None,
) -> MultimodalEmbeddingResult:
    """Execute the end-to-end multimodal embedding pipeline across Image, Audio, and Video.

    Pipeline Steps:
    1. Key Management & Authenticated Encryption (AES-256-GCM).
    2. Candidate Carrier Profiling & Feature Extraction.
    3. Multi-carrier Capacity Check & Allocation Strategy Execution.
    4. ASTG Packet Slicing & Serialization (34-byte header per chunk).
    5. Embedding into Image (PSTG), Audio (WSTG), and Video (VSTG).
    6. Objective Fidelity Evaluation (PSNR, SNR, MSE).
    7. Packaging into a Non-Secret Manifest and Downloadable ZIP Archive.

    Args:
        message: Plaintext message string to conceal.
        image_bytes: Cover PNG image bytes.
        audio_bytes: Cover WAV audio bytes.
        video_bytes: Cover AVI video bytes.
        password: Optional passphrase to derive AES-256 key.
        key_bytes: Optional direct 32-byte AES-256 key.
        salt_bytes: Optional salt for PBKDF2 derivation.
        strategy_name: 'fixed' or 'adaptive' (default 'adaptive').
        weights_config: Optional carrier weight tuning dictionary.

    Returns:
        MultimodalEmbeddingResult containing stego carriers, zip bundle, metrics, and keys.

    Raises:
        MultimodalCapacityExceededError: If payload cannot fit across the 3 carriers.
        InvalidCarrierError: If any carrier format is unsupported or invalid.
        MultimodalEngineError: If an unexpected error occurs during embedding.
    """
    # 1. Key Derivation & Encryption
    if key_bytes is not None:
        validate_key(key_bytes)
        derived_salt: Optional[bytes] = None
    elif password:
        key_bytes, derived_salt = derive_key_from_password(password, salt=salt_bytes)
    else:
        key_bytes = generate_key()
        derived_salt = None

    plaintext_bytes = message.encode("utf-8")
    try:
        envelope_bytes = encrypt(plaintext_bytes, key_bytes)
    except CryptoError as e:
        raise MultimodalEngineError(f"Encryption failed: {str(e)}") from e

    # 2. Carrier Profiling
    triad_profile = profile_multimodal_triad(image_bytes, audio_bytes, video_bytes)

    # 3. Allocation Strategy
    strategy = get_allocation_strategy(strategy_name)
    plan = strategy.allocate(
        payload_len=len(envelope_bytes),
        triad_profile=triad_profile,
        weights_config=weights_config,
    )

    # 4. ASTG Packet Slicing
    msg_id = uuid.uuid4().bytes
    msg_id_hex = msg_id.hex()

    img_slice_range = plan.slice_offsets["image"]
    aud_slice_range = plan.slice_offsets["audio"]
    vid_slice_range = plan.slice_offsets["video"]

    img_payload = envelope_bytes[img_slice_range[0] : img_slice_range[1]]
    aud_payload = envelope_bytes[aud_slice_range[0] : aud_slice_range[1]]
    vid_payload = envelope_bytes[vid_slice_range[0] : vid_slice_range[1]]

    chunk_img = PayloadChunk(message_id=msg_id, chunk_index=0, total_chunks=3, payload=img_payload)
    chunk_aud = PayloadChunk(message_id=msg_id, chunk_index=1, total_chunks=3, payload=aud_payload)
    chunk_vid = PayloadChunk(message_id=msg_id, chunk_index=2, total_chunks=3, payload=vid_payload)

    img_chunk_bytes = serialize_chunk(chunk_img)
    aud_chunk_bytes = serialize_chunk(chunk_aud)
    vid_chunk_bytes = serialize_chunk(chunk_vid)

    # 5. Carrier Embedding
    try:
        stego_img_arr, img_metrics = embed_in_image(image_bytes, img_chunk_bytes)
        stego_img_bytes = save_image_to_png_bytes(stego_img_arr)
    except ImageStegoError as e:
        raise MultimodalEngineError(f"Image carrier embedding failed: {str(e)}") from e

    try:
        stego_aud_bytes, aud_metrics = embed_in_audio(audio_bytes, aud_chunk_bytes)
    except AudioStegoError as e:
        raise MultimodalEngineError(f"Audio carrier embedding failed: {str(e)}") from e

    try:
        stego_vid_bytes, vid_metrics, preview_frame_bytes = embed_in_video(video_bytes, vid_chunk_bytes)
    except VideoStegoError as e:
        raise MultimodalEngineError(f"Video carrier embedding failed: {str(e)}") from e

    # 6. Build Non-Secret Manifest (NO KEYS OR PLAINTEXT)
    iso_now = datetime.now(timezone.utc).isoformat()
    manifest: Dict[str, Any] = {
        "project": "Reliability-Aware Adaptive Multimodal Steganography",
        "created_at": iso_now,
        "message_id": msg_id_hex,
        "strategy": plan.strategy_name,
        "total_envelope_bytes": len(envelope_bytes),
        "total_usable_capacity_bytes": plan.total_usable_capacity_bytes,
        "overall_utilization_ratio": plan.overall_utilization_ratio,
        "carriers": {
            "image": {
                "filename": "stego_carrier.png",
                "chunk_index": 0,
                "payload_bytes": len(img_payload),
                "framed_chunk_bytes": len(img_chunk_bytes),
                "utilization_ratio": plan.allocations["image"].utilization_ratio,
                "complexity_score": triad_profile.image.complexity_score,
                "metrics": {
                    "psnr_display": img_metrics.get("psnr_display", "N/A"),
                    "mse": img_metrics.get("mse", 0.0),
                    "ssim": img_metrics.get("ssim", 1.0),
                },
                "allocation_reason": plan.allocations["image"].reason,
            },
            "audio": {
                "filename": "stego_carrier.wav",
                "chunk_index": 1,
                "payload_bytes": len(aud_payload),
                "framed_chunk_bytes": len(aud_chunk_bytes),
                "utilization_ratio": plan.allocations["audio"].utilization_ratio,
                "complexity_score": triad_profile.audio.complexity_score,
                "metrics": {
                    "snr_display": aud_metrics.get("snr_display", "N/A"),
                    "mse": aud_metrics.get("normalized_mse", 0.0),
                },
                "allocation_reason": plan.allocations["audio"].reason,
            },
            "video": {
                "filename": "stego_carrier.avi",
                "chunk_index": 2,
                "payload_bytes": len(vid_payload),
                "framed_chunk_bytes": len(vid_chunk_bytes),
                "utilization_ratio": plan.allocations["video"].utilization_ratio,
                "complexity_score": triad_profile.video.complexity_score,
                "metrics": {
                    "psnr_display": vid_metrics.get("psnr_display", "N/A"),
                    "average_mse": vid_metrics.get("average_mse", 0.0),
                },
                "allocation_reason": plan.allocations["video"].reason,
            },
        },
    }

    # 7. Package into ZIP Archive
    zip_bundle_bytes = create_stego_zip_bundle(
        stego_image_bytes=stego_img_bytes,
        stego_audio_bytes=stego_aud_bytes,
        stego_video_bytes=stego_vid_bytes,
        manifest_dict=manifest,
    )

    return MultimodalEmbeddingResult(
        stego_image_bytes=stego_img_bytes,
        stego_audio_bytes=stego_aud_bytes,
        stego_video_bytes=stego_vid_bytes,
        preview_frame_bytes=preview_frame_bytes,
        zip_bundle_bytes=zip_bundle_bytes,
        manifest=manifest,
        allocation_plan=plan,
        image_metrics=img_metrics,
        audio_metrics=aud_metrics,
        video_metrics=vid_metrics,
        key_bytes=key_bytes,
        salt_bytes=derived_salt,
        message_id_hex=msg_id_hex,
    )


def extract_multimodal(
    stego_image_bytes: bytes,
    stego_audio_bytes: bytes,
    stego_video_bytes: bytes,
    key_bytes: Optional[bytes] = None,
    password: Optional[str] = None,
    salt_bytes: Optional[bytes] = None,
    manifest_dict: Optional[Dict[str, Any]] = None,
) -> MultimodalExtractionResult:
    """Execute the multimodal extraction and decryption workflow.

    Workflow:
    1. Extracts raw binary chunks from each of the three stego carriers.
    2. Deserializes each chunk with ASTG validation (CRC32, magic, version).
    3. Validates cross-carrier consistency:
       - Matching message UUIDs across all 3 chunks.
       - Exact chunk indices (0, 1, 2) and total_chunks == 3.
    4. Reassembles the bit-exact encrypted envelope.
    5. Authenticates and decrypts via AES-256-GCM.
    6. Returns verified plaintext.

    Args:
        stego_image_bytes: Stego PNG image bytes.
        stego_audio_bytes: Stego WAV audio bytes.
        stego_video_bytes: Stego AVI video bytes.
        key_bytes: Optional 32-byte AES key.
        password: Optional passphrase.
        salt_bytes: Optional salt for PBKDF2 derivation.
        manifest_dict: Optional manifest extracted from zip bundle.

    Returns:
        MultimodalExtractionResult with verified plaintext and operational metadata.

    Raises:
        MultimodalEngineError: If extraction, validation, or decryption fails.
    """
    # 1. Extract raw chunks from each carrier
    try:
        img_chunk_raw = extract_from_image(stego_image_bytes)
    except ImageStegoError as e:
        raise MultimodalEngineError(f"Image chunk extraction failed: {str(e)}") from e

    try:
        aud_chunk_raw = extract_from_audio(stego_audio_bytes)
    except AudioStegoError as e:
        raise MultimodalEngineError(f"Audio chunk extraction failed: {str(e)}") from e

    try:
        vid_chunk_raw = extract_from_video(stego_video_bytes)
    except VideoStegoError as e:
        raise MultimodalEngineError(f"Video chunk extraction failed: {str(e)}") from e

    # 2. Deserialize chunks
    try:
        chunk_img = deserialize_chunk(img_chunk_raw)
        chunk_aud = deserialize_chunk(aud_chunk_raw)
        chunk_vid = deserialize_chunk(vid_chunk_raw)
    except CodecError as e:
        raise MultimodalEngineError(f"Chunk packet validation failed: {str(e)}") from e

    chunks = [chunk_img, chunk_aud, chunk_vid]

    # 3. Cross-carrier validation
    first_msg_id = chunks[0].message_id
    for idx, c in enumerate(chunks):
        if c.message_id != first_msg_id:
            raise CarrierExtractionMismatchError(
                f"Message ID mismatch: chunk from carrier {idx} has ID {c.message_id.hex()}, "
                f"expected {first_msg_id.hex()}."
            )
        if c.total_chunks != 3:
            raise CarrierExtractionMismatchError(
                f"Total chunks mismatch: chunk from carrier {idx} reports total_chunks={c.total_chunks}, "
                f"expected 3."
            )

    # 4. Reassemble encrypted envelope
    try:
        envelope_bytes = reassemble_chunks(chunks)
    except CodecError as e:
        raise MultimodalEngineError(f"Envelope reassembly failed: {str(e)}") from e

    # 5. Authenticated Decryption
    if key_bytes is not None:
        try:
            validate_key(key_bytes)
        except InvalidKeyError as e:
            raise MultimodalEngineError(f"Invalid AES key: {str(e)}") from e
        active_key = key_bytes
    elif password:
        if not salt_bytes:
            raise MultimodalEngineError("Salt is required when decrypting with a passphrase.")
        try:
            active_key, _ = derive_key_from_password(password, salt=salt_bytes)
        except InvalidKeyError as e:
            raise MultimodalEngineError(f"Key derivation failed: {str(e)}") from e
    else:
        raise MultimodalEngineError("Decryption requires either an AES key or a passphrase + salt.")

    try:
        plaintext_bytes = decrypt(envelope_bytes, active_key)
        plaintext = plaintext_bytes.decode("utf-8")
    except DecryptionError as e:
        raise MultimodalEngineError(f"Decryption authentication failed: {str(e)}") from e
    except UnicodeDecodeError as e:
        raise MultimodalEngineError("Decrypted payload is not valid UTF-8 text.") from e
    except CryptoError as e:
        raise MultimodalEngineError(f"Cryptographic error: {str(e)}") from e

    chunk_sizes = {
        "image": len(chunk_img.payload),
        "audio": len(chunk_aud.payload),
        "video": len(chunk_vid.payload),
    }

    return MultimodalExtractionResult(
        plaintext=plaintext,
        message_id_hex=first_msg_id.hex(),
        envelope_bytes_length=len(envelope_bytes),
        chunk_count=3,
        chunk_sizes=chunk_sizes,
        verified=True,
        manifest=manifest_dict,
    )
