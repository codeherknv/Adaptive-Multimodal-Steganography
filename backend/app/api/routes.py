"""FastAPI route definitions for health and system status."""
from datetime import datetime, timezone
from fastapi import APIRouter
from app.config import settings
from app.schemas import HealthResponse, SystemStatusResponse, ModuleStatus

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
            status="pending",
            description="AES-256-GCM encryption with fresh nonce, tag authentication, and key serialization.",
            capabilities=[]
        ),
        "payload_codec": ModuleStatus(
            name="Versioned Binary Payload Codec",
            phase=2,
            status="pending",
            description="Binary framing with magic bytes, message ID, chunk index, chunk count, and payload length validation.",
            capabilities=[]
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
        current_phase=1,
        modules=modules
    )
