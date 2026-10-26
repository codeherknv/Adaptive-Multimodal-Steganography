# Reliability-Aware Adaptive Multimodal Steganography

Research platform for adaptive payload allocation and machine-learning-based steganalysis across image, audio, and video carrier media.

## Project Structure
- `backend/`: FastAPI Python backend powering the research engine, cryptography, codec, and steganalysis.
- `frontend/`: React + TypeScript + Vite + Tailwind CSS dashboard.
- `docs/`: Academic documentation, architecture diagrams, methodology, and literature review.
- `data/`: Sample cover and stego media datasets.
- `outputs/`: Generated carrier files and intermediate artifacts.
- `results/`: Benchmarks and evaluation results (CSV exports, metric summaries).

---

## Current Status: Phase 7 Implemented & Verified

### Implemented Modules:
1. **Infrastructure & Monorepo (Phase 1)**: FastAPI application, Vite dev proxy, Pydantic configuration, dark minimal research workbench.
2. **Authenticated Encryption (Phase 2)**: AES-256-GCM with fresh 96-bit nonces, 128-bit authentication tags, PBKDF2-HMAC-SHA256 key derivation, and versioned binary envelope framing (`ENVELOPE_VERSION = 1`).
3. **Versioned Binary Payload Codec (Phase 2)**: Fixed 34-byte packet header (`b"ASTG"`), UUID4 message identifiers, CRC32 checksums, chunk splitting (equal or capacity-based), and order-independent reassembly.
4. **Spatial LSB Image Steganography (Phase 3)**: Lossless PNG carrier embedding/extraction with 14-byte binary framing (`b"PSTG"`), CRC32 integrity verification, RGBA alpha-channel preservation, and distortion metrics (MSE, PSNR, SSIM).
5. **PCM WAV Audio Steganography (Phase 4)**: Uncompressed 16-bit and 8-bit PCM WAV sample LSB embedding/extraction with 14-byte binary framing (`b"WSTG"`), interleaved multi-channel preservation (mono & stereo), audio header/duration preservation, and distortion metrics (normalized MSE, SNR in dB).
6. **Frame-Based Video Steganography (Phase 5)**: Multi-frame spatial LSB embedding/extraction across video frames using OpenCV and lossless codecs (FFV1 in AVI/MKV), 14-byte binary framing (`b"VSTG"`), video parameter preservation (resolution, FPS, frame count), and distortion metrics (average frame MSE, average frame PSNR).
7. **Unified Multimodal Allocation & Orchestration (Phase 6)**:
   - Carrier profiling (`profiler.py`): Measures Laplacian variance, RMS acoustic energy, and inter-frame temporal difference variance.
   - Allocation policies (`allocator.py`): Fixed baseline (equal split + water-filling) and adaptive feature-weighted rate-distortion strategy.
   - Unified orchestration (`engine.py`): Partitions encrypted envelope across PNG, WAV, and AVI carriers, packages bundle into a ZIP archive with non-secret manifest, and reassembles/decrypts from either ZIP or individual carriers.
8. **ML-Based Steganalysis & Detectability Evaluation (Phase 7)**:
   - Statistical feature extractors (`features.py`): 10 image features (LSB 1-ratio, Pairs-of-Values asymmetry, horizontal/vertical difference variance, kurtosis, Laplacian high-pass residual, LSB flip rate, cross-channel differences); 8 audio features (LSB ratio, sample PoV asymmetry, 1st/2nd difference variance & kurtosis, high-band spectral ratio, RMS energy); 7 video features (frame LSB ratio, inter-frame difference variance & kurtosis, inter-frame LSB flip rate, spatial difference variance).
   - Labeled benchmark dataset generator (`dataset_generator.py`): Procedural synthesizers for Image, Audio, and Video covers, paired with stego variants across Low, Medium, and High payload densities and Fixed/Adaptive strategies. Strict `source_id` tagging ensures zero data leakage. Zero secret leakage: no keys or plaintexts in feature sets.
   - Leak-free training engine (`trainer.py`): `GroupShuffleSplit` on `source_id` guarantees that a cover and all its stego variants never cross train/test splits. `StandardScaler` is fitted strictly on `X_train`. Trains explainable Random Forest and Logistic Regression baselines.
   - Single-file live inference classifier (`classifier.py`): Inspects uploaded media, automatically detects modality (PNG, WAV, AVI), calculates stego probability, and provides honest scientific disclaimers.
   - Interactive Steganalysis UI tab (`Steganalysis.tsx`): 3 sub-views for Live Carrier Inspection, Detector Training & Evaluation, and Dataset Exploration.
9. **Multimodal Triad Workbench**: Full-featured React workbench for 3-carrier profiling, strategy comparison, bundle download, and unified extraction.

---

## Supported Media Formats & Codecs

| Carrier Type | Supported Formats | Recommended Codec / Specification | Framing Signature | Lossless Guarantee |
|---|---|---|---|---|
| **Image** | PNG (`.png`) | Lossless Deflate RGB / RGBA | `b"PSTG"` (14 bytes) | Bit-exact recovery |
| **Audio** | WAV (`.wav`) | Linear PCM 16-bit / 8-bit, Mono / Stereo | `b"WSTG"` (14 bytes) | Bit-exact recovery |
| **Video** | AVI (`.avi`), MKV (`.mkv`) | FFV1 (RFC 9043) / HFYU (HuffYUV) | `b"VSTG"` (14 bytes) | Bit-exact recovery |

> [!IMPORTANT]
> **Video Codec Limitations & Research Note**: Lossy video codecs (such as H.264/AVC, H.265/HEVC, VP9, or MPEG-4) employ lossy discrete cosine transform (DCT) quantization, motion compensation residuals, and chroma subsampling that alter pixel values and completely destroy spatial LSB modifications. The video engine strictly enforces lossless encoding (FFV1 or HuffYUV) to guarantee mathematical bit-level recovery. Average frame MSE and PSNR measure spatial fidelity relative to the cover; they do **not** guarantee invisibility or prove resistance to statistical or machine-learning video steganalysis.

---

## Quick Start

### 1. Running the Backend Server
```powershell
cd backend
.\venv\Scripts\Activate.ps1
python -m uvicorn app.main:app --reload --port 8000
```
- Interactive API Documentation (Swagger UI): `http://127.0.0.1:8000/docs`
- Health check: `http://127.0.0.1:8000/api/health`
- Implementation status: `http://127.0.0.1:8000/api/status`

### 2. Running Automated Tests
```powershell
cd backend
.\venv\Scripts\pytest -v
```
Currently passes **156 automated tests** (API integration, AES-GCM cryptography, binary payload codec, PNG LSB steganography, PCM WAV audio steganography, video frame steganography, carrier profiling, fixed & adaptive allocation, multimodal orchestration, and ML steganalysis pipelines).

### 3. Running the Frontend Development Server
```powershell
cd frontend
npm run dev
```
Development dashboard: `http://localhost:5173`

---

## API Examples

### 1. Encrypt a Message (`POST /api/crypto/encrypt`)
```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/crypto/encrypt" -Method Post -ContentType "application/json" -Body '{
  "plaintext": "Secret message to be split across carriers",
  "encoding": "base64"
}'
```

### 2. Generate Steganalysis Dataset (`POST /api/steganalysis/dataset/generate`)
```powershell
curl -X POST "http://127.0.0.1:8000/api/steganalysis/dataset/generate" \
  -H "Content-Type: application/json" \
  -d '{"modality": "image", "num_sources": 10, "payload_fractions": [0.10, 0.35, 0.55]}'
```

### 3. Train ML Steganalyzer (`POST /api/steganalysis/train`)
```powershell
curl -X POST "http://127.0.0.1:8000/api/steganalysis/train" \
  -H "Content-Type: application/json" \
  -d '{"modality": "image", "model_type": "random_forest", "test_size": 0.30}'
```

### 4. Inspect Media for Steganography (`POST /api/steganalysis/classify`)
```powershell
curl -X POST "http://127.0.0.1:8000/api/steganalysis/classify" \
  -F "file=@suspect_image.png" \
  -F "model_type=random_forest"
```

### 5. Check Video Capacity (`POST /api/video/capacity`)
```powershell
curl -X POST "http://127.0.0.1:8000/api/video/capacity" -F "video=@sample_cover.avi"
```

### 6. Embed Encrypted Envelope in Video (`POST /api/video/embed`)
```powershell
curl -X POST "http://127.0.0.1:8000/api/video/embed" \
  -F "video=@sample_cover.avi" \
  -F "envelope=<ENVELOPE_BASE64_STRING>" \
  -F "encoding=base64"
```

### 7. Extract Envelope from Stego Video (`POST /api/video/extract`)
```powershell
curl -X POST "http://127.0.0.1:8000/api/video/extract" \
  -F "video=@stego_output.avi" \
  -F "encoding=base64"
```

### 8. Decrypt a Message (`POST /api/crypto/decrypt`)
```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/crypto/decrypt" -Method Post -ContentType "application/json" -Body '{
  "envelope": "<ENVELOPE_STRING>",
  "key": "<KEY_STRING>",
  "encoding": "base64"
}'
```
