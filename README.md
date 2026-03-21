# FinWise

FinWise is a full-stack financial analysis platform that ingests statements (CSV/PDF/image/text), extracts transactions, performs anomaly detection and forecasting, and provides AI-driven recommendations.

## What Was Audited and Implemented

This repository now includes the requested end-to-end pieces:

- Dummy data fallback removed from dashboard, transactions, and insights views.
- Frontend API routing aligned to backend through `/api` proxying.
- Extraction pipeline hardened for OCR-heavy and non-table statement layouts.
- Firebase Authentication integrated:
  - Frontend: email/password sign-in and account creation.
  - Backend: Firebase ID token verification for protected endpoints.
- Neon PostgreSQL per-user JSON metadata persistence added:
  - Protected `/documents` APIs for list/create/delete.
  - Frontend Documents & Uploads page for authenticated management.
  - Upload analysis flow now stores metadata automatically per signed-in user.

## Repository Structure

- `backend/`: FastAPI backend workspace
- `backend/app/`: FastAPI source code
- `backend/models_store/`: persisted ML artifacts
- `frontend/`: React + Vite + TypeScript frontend
- `backend/requirements.txt`: backend dependencies

## Backend Setup

1. Create a Python environment.
2. Install dependencies:

```bash
cd backend
pip install -r requirements.txt
```

3. Configure environment variables in `backend/.env`:

```env
APP_NAME=FinWise AI
DEBUG=true

# Existing app settings
DB_URL=sqlite:///./finwise.db
PDF_PARSER=auto

# Optional OpenDataLoader parser mode
# - auto: try OpenDataLoader first, fallback to native parser
# - opendataloader: force OpenDataLoader only
# - native: use existing internal parser only
# Requires Java 11+ when OpenDataLoader is used.

# Neon Postgres for per-user documents metadata
NEON_DATABASE_URL=postgresql://<user>:<password>@<host>/<db>?sslmode=require

# Firebase Admin SDK for backend token verification
FIREBASE_CREDENTIALS_PATH=C:/path/to/firebase-service-account.json
# OR
# FIREBASE_CREDENTIALS_JSON={"type":"service_account",...}

# Optional: Gemini AI Studio for RLM-powered deep queries
GEMINI_API_KEY=<your-ai-studio-key>

# RLM provider switch: gemini | openrouter
RLM_PROVIDER=openrouter
RLM_MODEL=openrouter/auto
RLM_RECURSIVE_MODEL=openrouter/auto

# Optional OpenRouter support (free-model routing)
OPENROUTER_API_KEY=<your-openrouter-key>
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1/chat/completions
OPENROUTER_FREE_MODELS=meta-llama/llama-3.3-8b-instruct:free,google/gemma-3-27b-it:free,qwen/qwen-2.5-7b-instruct:free
```

4. Start API:

```bash
cd backend
uvicorn app.main:app --reload
```

## Frontend Setup

1. Install dependencies:

```bash
cd frontend
npm install
```

2. Create `frontend/.env` with Firebase Web SDK config:

```env
VITE_API_BASE=/api

VITE_FIREBASE_API_KEY=<firebase-web-api-key>
VITE_FIREBASE_AUTH_DOMAIN=<project-id>.firebaseapp.com
VITE_FIREBASE_PROJECT_ID=<project-id>
VITE_FIREBASE_STORAGE_BUCKET=<project-id>.appspot.com
VITE_FIREBASE_MESSAGING_SENDER_ID=<sender-id>
VITE_FIREBASE_APP_ID=<app-id>
```

3. Start frontend:

```bash
npm run dev
```

The Vite dev server proxies `/api/*` to `http://localhost:8000/*`.

## Auth + Documents Flow

1. Open the frontend and navigate to `Documents`.
2. Sign in or create an account using Firebase email/password auth.
3. Upload a statement file from the Documents page (or any existing upload flow).
4. The app will:
   - Analyze the file with backend `/analyze`.
   - Persist a per-user JSON metadata record via protected `/documents` API.
5. View and delete saved metadata records from the Documents page.

## Key Endpoints

- `POST /analyze`: analyze statement file
- `POST /query`: RAG query endpoint
- `GET /health`: health check
- `GET /documents`: list authenticated user's document metadata
- `POST /documents`: create authenticated user's metadata record
- `DELETE /documents/{document_id}`: delete authenticated user's metadata record

## Notes

- Backend `/documents` endpoints require a valid Firebase ID token.
- Neon table is created automatically on first metadata operation.
- OCR behavior supports environments without external Tesseract install by using `easyocr` first and `pytesseract` fallback when available.
