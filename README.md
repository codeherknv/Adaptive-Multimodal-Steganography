# Reliability-Aware Adaptive Multimodal Steganography

Research platform for adaptive payload allocation and machine-learning-based steganalysis across image, audio, and video carrier media.

## Project Structure
- `backend/`: FastAPI Python backend powering the research engine, cryptography, and steganalysis.
- `frontend/`: React + TypeScript + Vite + Tailwind CSS dashboard.
- `docs/`: Academic documentation, architecture diagrams, methodology, and literature review.
- `data/`: Sample cover and stego media datasets.
- `outputs/`: Generated carrier files and intermediate artifacts.
- `results/`: Benchmarks and evaluation results (CSV exports, metric summaries).

## Quick Start (Phase 1)

### Backend Setup
```bash
cd backend
python -m venv venv
.\venv\Scripts\Activate.ps1   # On Windows PowerShell
pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 8000
```
Health check endpoint: `http://localhost:8000/api/health`

### Frontend Setup
```bash
cd frontend
npm install
npm run dev
```
Development dashboard: `http://localhost:5173`
