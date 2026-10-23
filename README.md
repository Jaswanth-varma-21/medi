# MedTruth AI — Multi-X-ray Research Prototype

MedTruth AI is a research prototype for explaining radiology report text and exploring image-analysis workflows for chest, bone/joint, spine, and dental X-rays.

## Current scope

The project includes a React + Vite frontend and a FastAPI backend with a four-agent report-explanation pipeline (analysis, evidence retrieval, explanation, and verification). The image workflow validates uploaded images and routes requested modalities to configured model adapters.

**Important:** A modality selector does not mean a model is available for that modality. When a suitable model is not configured, the application must return a no-model/unsupported status and must not fabricate findings. Bone, spine, and dental model support, their evidence resources, and their evaluation need separate implementation and validation. This is not a clinically validated diagnostic device and must not be used as a substitute for qualified clinical review.

## Project layout

- `frontend/` — React + Vite user interface
- `backend/` — FastAPI app, agents, image validation, model routing, tests
- `backend/requirements-models.txt` — optional model dependencies
- `setup_wsl.sh` — Debian/Ubuntu on WSL setup helper

## Setup on Debian / WSL

Install Python, Node.js, Tesseract OCR, Poppler, Git, and Ollama as required by the project. Then from the project root:

```bash
bash setup_wsl.sh
```

For manual setup:

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --port 8000
```

In a second terminal:

```bash
cd frontend
npm install
npm run dev
```

Never commit real API keys, `.env` files, patient images/reports, virtual environments, or local model weights. Check the `.gitignore` before pushing.

## Image API

The image workflow documents `POST /api/image/analyze?modality=chest|bone|spine|dental&view=...`. Supported view values and actual available models are determined by the implementation/configuration. Do not infer clinical accuracy from a successful API response.

## Validation requirements

Each specialty needs task-specific data permissions, model/license review, patient-level data splits, held-out evaluation, uncertainty and failure-case tests, privacy/security controls, and qualified clinician review before any clinical deployment.
