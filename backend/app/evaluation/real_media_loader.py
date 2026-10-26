"""Real media loader and dataset provenance manager for Phase 8 evaluation.

Enforces clear separation between:
1. 'synthetic_procedural': Programmatically synthesized carriers (seed-reproducible).
2. 'user_provided_real': Physical external files provided by the researcher.

Supports loading and validation of real PNG, WAV, and AVI carriers.
"""

from dataclasses import dataclass
import os
import glob
from typing import Dict, List, Literal, Optional, Tuple

from app.media.image_stego import load_image_as_rgb_array, get_image_capacity
from app.media.audio_stego import load_wav_audio, get_audio_capacity
from app.media.video_stego import load_video_from_bytes, get_video_capacity
from app.steganalysis.dataset_generator import (
    generate_procedural_image,
    generate_procedural_audio,
    generate_procedural_video,
)

DEFAULT_REAL_MEDIA_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "data", "real_media")
)


@dataclass(frozen=True)
class CarrierTriadSource:
    """A paired collection of Image, Audio, and Video covers from an identified source."""
    source_id: str
    provenance: Literal["synthetic_procedural", "user_provided_real"]
    image_bytes: bytes
    audio_bytes: bytes
    video_bytes: bytes
    image_metadata: Dict[str, object]
    audio_metadata: Dict[str, object]
    video_metadata: Dict[str, object]
    description: str = ""


def load_synthetic_triad(source_index: int) -> CarrierTriadSource:
    """Generate a reproducible procedural carrier triad tagged as synthetic."""
    img_bytes = generate_procedural_image(source_index=source_index, width=96, height=96)
    aud_bytes = generate_procedural_audio(source_index=source_index, duration_sec=1.0)
    vid_bytes = generate_procedural_video(source_index=source_index, num_frames=12, width=64, height=64)

    img_cap = get_image_capacity(img_bytes)
    aud_cap = get_audio_capacity(aud_bytes)
    vid_cap = get_video_capacity(vid_bytes)

    return CarrierTriadSource(
        source_id=f"syn_src_{source_index:03d}",
        provenance="synthetic_procedural",
        image_bytes=img_bytes,
        audio_bytes=aud_bytes,
        video_bytes=vid_bytes,
        image_metadata=img_cap,
        audio_metadata=aud_cap,
        video_metadata=vid_cap,
        description=f"Procedural synthetic triad (seed {source_index})",
    )


def load_user_real_media_triads(media_dir: str = DEFAULT_REAL_MEDIA_DIR) -> List[CarrierTriadSource]:
    """Scan directory for user-provided real media triads (matching stem names).
    
    Expected naming convention in media_dir:
      source_01.png, source_01.wav, source_01.avi (or .mkv)
    """
    if not os.path.isdir(media_dir):
        return []

    png_files = sorted(glob.glob(os.path.join(media_dir, "*.png")))
    triads: List[CarrierTriadSource] = []

    for png_path in png_files:
        stem = os.path.splitext(os.path.basename(png_path))[0]
        wav_path = os.path.join(media_dir, f"{stem}.wav")
        avi_path = os.path.join(media_dir, f"{stem}.avi")
        if not os.path.exists(avi_path):
            avi_path = os.path.join(media_dir, f"{stem}.mkv")

        if os.path.exists(wav_path) and os.path.exists(avi_path):
            try:
                with open(png_path, "rb") as f:
                    img_bytes = f.read()
                with open(wav_path, "rb") as f:
                    aud_bytes = f.read()
                with open(avi_path, "rb") as f:
                    vid_bytes = f.read()

                img_cap = get_image_capacity(img_bytes)
                aud_cap = get_audio_capacity(aud_bytes)
                vid_cap = get_video_capacity(vid_bytes)

                triads.append(
                    CarrierTriadSource(
                        source_id=f"real_{stem}",
                        provenance="user_provided_real",
                        image_bytes=img_bytes,
                        audio_bytes=aud_bytes,
                        video_bytes=vid_bytes,
                        image_metadata=img_cap,
                        audio_metadata=aud_cap,
                        video_metadata=vid_cap,
                        description=f"Real user media triad '{stem}' from {media_dir}",
                    )
                )
            except Exception:
                continue

    return triads
