"""Pydantic schemas for API request and response validation."""

from datetime import datetime, timezone
from typing import Dict, List, Literal, Optional, Union
from pydantic import BaseModel, Field, model_validator


class HealthResponse(BaseModel):
    """Safe health check response containing no sensitive system information."""
    status: Literal["healthy", "degraded", "unhealthy"] = "healthy"
    version: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ModuleStatus(BaseModel):
    """Actual progress status of a specific engineering module."""
    name: str
    phase: int
    status: Literal["implemented", "in_progress", "pending"]
    description: str
    capabilities: List[str] = Field(default_factory=list)


class SystemStatusResponse(BaseModel):
    """Overview of project implementation status across development phases."""
    project_name: str
    version: str
    current_phase: int
    modules: Dict[str, ModuleStatus]


# ---------------------------------------------------------
# Cryptographic Schemas (Phase 2)
# ---------------------------------------------------------

class EncryptRequest(BaseModel):
    """Request payload for AES-256-GCM encryption."""
    plaintext: str = Field(
        ...,
        max_length=1_000_000,
        description="Plaintext string message to be encrypted (max 1 MB)."
    )
    key: Optional[str] = Field(
        None,
        description="Optional 32-byte AES key (hex or base64). If omitted, a fresh random key is generated."
    )
    password: Optional[str] = Field(
        None,
        min_length=1,
        max_length=1024,
        description="Optional passphrase to derive a key via PBKDF2-HMAC-SHA256 (used only if key is omitted)."
    )
    salt: Optional[str] = Field(
        None,
        description="Optional salt for password key derivation (hex or base64). If omitted, a random 16-byte salt is generated."
    )
    encoding: Literal["base64", "hex"] = Field(
        "base64",
        description="Encoding format for keys, nonces, and output envelope ('base64' or 'hex')."
    )

    @model_validator(mode="after")
    def check_key_and_password(self):
        if self.key and self.password:
            raise ValueError("Provide either 'key' or 'password', not both.")
        return self


class EncryptResponse(BaseModel):
    """Response containing ciphertext envelope and key management metadata."""
    key: str = Field(
        ...,
        description="The 32-byte AES-256 key in requested encoding format. Keep separate from carrier files!"
    )
    key_encoding: Literal["base64", "hex"] = Field(
        ...,
        description="Encoding format used for key, nonce, and envelope."
    )
    salt: Optional[str] = Field(
        None,
        description="16-byte salt in requested encoding if PBKDF2 password derivation was used."
    )
    envelope_version: int = Field(
        1,
        description="Binary envelope framing version."
    )
    nonce: str = Field(
        ...,
        description="Fresh 96-bit (12-byte) initialization vector / nonce in requested encoding."
    )
    ciphertext: str = Field(
        ...,
        description="Encrypted payload including 128-bit authentication tag in requested encoding."
    )
    envelope: str = Field(
        ...,
        description="Self-contained serialized binary envelope in requested encoding (ready for carrier embedding)."
    )
    envelope_bytes_length: int = Field(
        ...,
        description="Exact byte length of the binary envelope."
    )
    plaintext_bytes_length: int = Field(
        ...,
        description="Byte length of the original plaintext."
    )
    warning: str = Field(
        "Educational Key Workflow: Keep this key separate from carrier media. Anyone possessing this key can decrypt the secret payload.",
        description="Educational security advisory."
    )


class DecryptRequest(BaseModel):
    """Request payload for authenticating and decrypting a ciphertext envelope."""
    envelope: str = Field(
        ...,
        description="Serialized encrypted envelope in base64 or hex format."
    )
    key: Optional[str] = Field(
        None,
        description="32-byte AES key in base64 or hex format."
    )
    password: Optional[str] = Field(
        None,
        description="Passphrase used during PBKDF2 key derivation (requires matching salt)."
    )
    salt: Optional[str] = Field(
        None,
        description="16-byte salt used during PBKDF2 password derivation (required if password is used)."
    )
    encoding: Literal["base64", "hex"] = Field(
        "base64",
        description="Encoding format of the supplied envelope and key/salt ('base64' or 'hex')."
    )

    @model_validator(mode="after")
    def check_key_or_password(self):
        if not self.key and not self.password:
            raise ValueError("Must provide either 'key' or 'password' to decrypt.")
        if self.key and self.password:
            raise ValueError("Provide either 'key' or 'password', not both.")
        if self.password and not self.salt:
            raise ValueError("Salt is required when decrypting with a derived password.")
        return self


class DecryptResponse(BaseModel):
    """Response containing authenticated plaintext message."""
    plaintext: str = Field(
        ...,
        description="Authenticated and decrypted plaintext string."
    )
    authenticated: bool = Field(
        True,
        description="Cryptographic integrity verification status (True indicates valid GCM auth tag)."
    )
    envelope_version: int = Field(
        ...,
        description="Version of the decrypted envelope."
    )
    plaintext_bytes_length: int = Field(
        ...,
        description="Exact byte length of the recovered plaintext."
    )


# ---------------------------------------------------------
# Image Steganography Schemas (Phase 3)
# ---------------------------------------------------------

class ImageCapacityResponse(BaseModel):
    """Capacity estimation metrics for a carrier image."""
    width: int
    height: int
    channels: int
    color_mode: str
    embeddable_channels_per_pixel: int
    total_carrier_bits: int
    total_carrier_bytes: int
    header_overhead_bytes: int
    max_usable_payload_bytes: int


class ImageQualityMetricsResponse(BaseModel):
    """Distortion fidelity metrics computed between cover and stego image."""
    mse: float
    psnr: Union[float, str]
    psnr_display: str
    ssim: float
    embedded_bytes: int
    framed_bytes: int
    capacity_used_ratio: float
    bits_per_pixel: float


class ImageEmbedResponse(BaseModel):
    """Response containing stego image payload and distortion metrics."""
    stego_image_data_url: str = Field(
        ...,
        description="Base64 data URL (data:image/png;base64,...) for immediate browser display and download."
    )
    filename: str = Field("stego_carrier.png", description="Suggested output filename.")
    embedded_bytes: int
    metrics: ImageQualityMetricsResponse
    message: str = Field("Payload successfully embedded with spatial LSB.", description="Status message.")


class ImageExtractResponse(BaseModel):
    """Response containing extracted encrypted envelope."""
    envelope: str = Field(
        ...,
        description="Extracted Phase 2 binary envelope encoded in requested format."
    )
    encoding: Literal["base64", "hex"]
    envelope_bytes_length: int
    envelope_version: int
    status: Literal["verified"] = "verified"
    message: str = Field(
        "Successfully extracted authenticated envelope from image carrier.",
        description="Status message."
    )


# ---------------------------------------------------------
# Audio Steganography Schemas (Phase 4)
# ---------------------------------------------------------

class AudioCapacityResponse(BaseModel):
    """Capacity estimation metrics for a WAV audio carrier."""
    num_channels: int
    channel_layout: str
    sample_rate: int
    sample_width: int
    bits_per_sample: int
    num_frames: int
    duration_seconds: float
    total_samples: int
    total_carrier_bits: int
    total_carrier_bytes: int
    header_overhead_bytes: int
    max_usable_payload_bytes: int


class AudioQualityMetricsResponse(BaseModel):
    """Distortion fidelity metrics computed between cover and stego audio."""
    mse: float
    snr: Union[float, str]
    snr_display: str
    embedded_bytes: int
    framed_bytes: int
    capacity_used_ratio: float
    bits_per_sample_used: float


class AudioEmbedResponse(BaseModel):
    """Response containing stego audio data URL and distortion metrics."""
    stego_audio_data_url: str = Field(
        ...,
        description="Base64 data URL (data:audio/wav;base64,...) for immediate browser playback and download."
    )
    filename: str = Field("stego_carrier.wav", description="Suggested output filename.")
    embedded_bytes: int
    metrics: AudioQualityMetricsResponse
    message: str = Field(
        "Payload successfully embedded into WAV audio using sample LSB.",
        description="Status message."
    )


class AudioExtractResponse(BaseModel):
    """Response containing extracted encrypted envelope from audio carrier."""
    envelope: str = Field(
        ...,
        description="Extracted Phase 2 binary envelope encoded in requested format."
    )
    encoding: Literal["base64", "hex"]
    envelope_bytes_length: int
    envelope_version: int
    status: Literal["verified"] = "verified"
    message: str = Field(
        "Successfully extracted authenticated envelope from audio carrier.",
        description="Status message."
    )
