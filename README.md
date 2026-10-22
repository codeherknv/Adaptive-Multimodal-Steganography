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

## Current Status: Phase 4 Implemented & Verified

### Implemented Modules:
1. **Infrastructure & Monorepo (Phase 1)**: FastAPI application, Vite dev proxy, Pydantic configuration, dark minimal research workbench.
2. **Authenticated Encryption (Phase 2)**: AES-256-GCM with fresh 96-bit nonces, 128-bit authentication tags, PBKDF2-HMAC-SHA256 key derivation, and versioned binary envelope framing (`ENVELOPE_VERSION = 1`).
3. **Versioned Binary Payload Codec (Phase 2)**: Fixed 34-byte packet header (`b"ASTG"`), UUID4 message identifiers, CRC32 checksums, chunk splitting (equal or capacity-based), and order-independent reassembly.
4. **Spatial LSB Image Steganography (Phase 3)**: Lossless PNG carrier embedding/extraction with 14-byte binary framing (`b"PSTG"`), CRC32 integrity verification, RGBA alpha-channel preservation, and distortion metrics (MSE, PSNR, SSIM).
5. **PCM WAV Audio Steganography (Phase 4)**: Uncompressed 16-bit and 8-bit PCM WAV sample LSB embedding/extraction with 14-byte binary framing (`b"WSTG"`), interleaved multi-channel preservation (mono & stereo), audio header/duration preservation, and distortion metrics (normalized MSE, SNR in dB).
6. **Interactive Multimodal Sender & Receiver Workflows (Phase 4)**: React + TypeScript UI supporting both PNG Image and WAV Audio carrier modes for end-to-end encryption, capacity checks, embedding, stego audio/image download, in-browser playback/preview, and authenticated decryption.

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
Currently passes **90 automated tests** (API integration, AES-GCM cryptography, binary payload codec, PNG LSB steganography, PCM WAV audio steganography, and media distortion metrics).

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

### 2. Check Image Capacity (`POST /api/image/capacity`)
```powershell
curl -X POST "http://127.0.0.1:8000/api/image/capacity" -F "image=@sample_cover.png"
```

### 3. Embed Encrypted Envelope in PNG (`POST /api/image/embed`)
```powershell
curl -X POST "http://127.0.0.1:8000/api/image/embed" \
  -F "image=@sample_cover.png" \
  -F "envelope=<ENVELOPE_BASE64_STRING>" \
  -F "encoding=base64"
```

### 4. Extract Envelope from Stego PNG (`POST /api/image/extract`)
```powershell
curl -X POST "http://127.0.0.1:8000/api/image/extract" \
  -F "image=@stego_output.png" \
  -F "encoding=base64"
```

### 5. Check Audio Capacity (`POST /api/audio/capacity`)
```powershell
curl -X POST "http://127.0.0.1:8000/api/audio/capacity" -F "audio=@sample_cover.wav"
```

### 6. Embed Encrypted Envelope in WAV Audio (`POST /api/audio/embed`)
```powershell
curl -X POST "http://127.0.0.1:8000/api/audio/embed" \
  -F "audio=@sample_cover.wav" \
  -F "envelope=<ENVELOPE_BASE64_STRING>" \
  -F "encoding=base64"
```

### 7. Extract Envelope from Stego WAV Audio (`POST /api/audio/extract`)
```powershell
curl -X POST "http://127.0.0.1:8000/api/audio/extract" \
  -F "audio=@stego_output.wav" \
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
