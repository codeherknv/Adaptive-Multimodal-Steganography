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

## Current Status: Phase 2 Implemented & Verified

### Implemented Modules:
1. **Infrastructure & Monorepo (Phase 1)**: FastAPI application, Vite dev proxy, Pydantic configuration, dark minimal research workbench.
2. **Authenticated Encryption (Phase 2)**: AES-256-GCM with fresh 96-bit nonces, 128-bit authentication tags, PBKDF2-HMAC-SHA256 key derivation, and versioned binary envelope framing (`ENVELOPE_VERSION = 1`).
3. **Versioned Binary Payload Codec (Phase 2)**: Fixed 34-byte packet header (`b"ASTG"`), UUID4 message identifiers, CRC32 checksums, chunk splitting (equal or capacity-based), and order-independent reassembly.

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
Currently passes **47 automated tests** (API integration, AES-GCM cryptography, and binary payload codec).

### 3. Running the Frontend Development Server
```powershell
cd frontend
npm run dev
```
Development dashboard: `http://localhost:5173`

---

## Cryptographic API Examples

### Encrypt a Message (`POST /api/crypto/encrypt`)
```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/crypto/encrypt" -Method Post -ContentType "application/json" -Body '{
  "plaintext": "Secret message to be split across carriers",
  "encoding": "base64"
}'
```

### Decrypt a Message (`POST /api/crypto/decrypt`)
```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/crypto/decrypt" -Method Post -ContentType "application/json" -Body '{
  "envelope": "<ENVELOPE_STRING>",
  "key": "<KEY_STRING>",
  "encoding": "base64"
}'
```
