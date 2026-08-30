# 🏥 HealthLink

> **Multi-Agent AI Powered Smart Health Management System**

HealthLink is an Agentic AI platform that transforms fragmented healthcare touchpoints into a seamless, empathetic care flow. Using **multi-agent collaboration** and **Retrieval-Augmented Generation (RAG)**, it understands patient concerns in natural language, identifies the right specialists, automates scheduling, and generates contextual summaries for both patients and doctors.

---

## 📋 Table of Contents

- [Key Features](#-key-features)
- [Live Demo](#-live-demo)
- [How It Works](#️-how-it-works)
- [Multi-Agent Architecture](#-multi-agent-architecture)
- [Prerequisites](#-prerequisites)
- [Installation](#-installation)
- [Configuration](#-configuration)
- [Usage](#-usage)
- [API Reference](#-api-reference)
- [Deployment](#-deployment)
- [Project Structure](#-project-structure)
- [Demo Scenario](#-demo-scenario)
- [Troubleshooting](#-troubleshooting)
- [Development](#-development)
- [Technology Stack](#-technology-stack)
- [Sources](#-sources)

---

## ✨ Key Features

### Multi-Agent Reasoning Pipeline
Four specialized AI agents collaborate in sequence to extract symptoms, rank specialists, propose appointments, and synthesize summaries — orchestrated by a LangGraph `StateGraph`.

### Clarifying Questions
Symptom agent detects vague input and asks up to 3 follow-ups (e.g. *“Do you also have nausea or vision problems?”*), then re-evaluates with answers — no infinite loop.

### Hybrid RAG — Vector + Keyword + RRF
**Pinecone** (`llama-text-embed-v2`, batched 90) + **BM25** in-memory index + **Reciprocal Rank Fusion** (`k=60`) over `symptoms_kb.json` (200 records). Vector captures paraphrase (`can't breathe` ≈ `dyspnea`), BM25 catches exact terms (`G43`, `paracetamol`), RRF fuses `top-10 + top-10 → top-5` for `format_retrieval_context`.

### Live Doctor Ranking
100 doctors / 30 specialties seeded from `doctors.csv` into SQLite (Pandas, idempotent). Specialty is picked by LLM, then ranked by rating and filtered by location/consultation preference.

### Appointment Booking
Generates 14-day weekday slots, picks the best by urgency/date/time-of-day, and supports **book / list / cancel** with simulated reminders.

### Dual Summaries
Patient-facing empathetic summary + doctor-facing structured record (overview, presenting symptoms, key points, follow-ups) — both guard-railed.

### Tracing & Guardrails
Structured JSON logs (`request_id` + per-agent `latency_ms`), LangSmith traces (env-gated), and rule-based guardrails (hallucinated diagnosis, PII, harmful advice).

### Modern Web UI
Streamlit top-nav webpage: gradient hero, 4-step strip, dashboards tab, SQLite viewer, and wake-API pill.

---

## 🚀 Live Demo

Try HealthLink live at:
- **Streamlit Cloud (UI):** [Live Demo](https://healthlink-dkxy.streamlit.app/)
- **Cloud Run API:** [Live API](https://healthlink-staging-406419876805.us-central1.run.app/)

---

## ⚙️ How It Works

```
Patient Input
    │
    ├─► Symptom Agent — extracts symptoms, urgency, clarifying_questions (RAG + LLM)
    │
    ├─► Doctor Agent — maps to specialty, queries SQLite, ranks by rating
    │
    ├─► Scheduling Agent — generates slots, LLM picks best by urgency/preferences
    │
    └─► Summary Agent — patient + doctor summaries (guard-railed)
            │
            └─► Response: symptom_analysis + doctor_recommendations + scheduling_options + health_summary + doctor_summary + trace
```

For a detailed breakdown of agents, data flow, and system design, see [ARCHITECTURE.md](ARCHITECTURE.md).

---

## 🤖 Multi-Agent Architecture

| Agent | Role | Tools |
|-------|------|-------|
| **Symptom Understanding Agent** | Extracts symptoms, severity, duration, urgency, clarifying questions | LLM (OpenRouter/Nvidia), **Hybrid RAG** (Pinecone + BM25 + RRF) |
| **Doctor Recommendation Agent** | Picks specialty and ranks doctors from SQLite | LLM, SQLAlchemy |
| **Appointment Scheduling Agent** | Generates weekday slots and selects best by urgency/preferences | LLM, Python datetime |
| **Summary Generation Agent** | Produces patient + doctor summaries | LLM, Guardrails |

Orchestrator: **LangGraph `StateGraph`** (`symptom → doctor → scheduling → summary`) with per-step latency tracing (`app/observability.py`).

---

## ✅ Prerequisites

- **Python 3.13+** installed
- **pip** package manager
- **Pinecone API key** ([pinecone.io](https://www.pinecone.io/))
- **OpenRouter API key** ([openrouter.ai/keys](https://openrouter.ai/keys)) or **Nvidia API key** ([build.nvidia.com](https://build.nvidia.com/))
- **Git** (for cloning)

---

## 📦 Installation

### Clone
```bash
git clone https://github.com/dhakksinesh/healthlink.git
cd healthlink
```

### Virtual Environment (recommended)
**Windows (PowerShell):**
```powershell
python -m venv venv
.\venv\Scripts\activate
```
**Mac / Linux:**
```bash
python3 -m venv venv
source venv/bin/activate
```

### Install Dependencies
```bash
pip install -r requirements.txt
```

### Set Up Environment
**Windows:**
```powershell
copy .env.example .env
```
**Mac / Linux:**
```bash
cp .env.example .env
```
Then fill `OPENROUTER_API_KEY` / `PINECONE_API_KEY` in `.env` (see [Configuration](#-configuration)).

---

## 🔧 Configuration

`.env` is sectioned into 7 blocks (lean required + optional defaults in `shared/config.py`):

| Variable | Required | Default | Get It |
|----------|----------|---------|--------|
| `OPENROUTER_API_KEY` | Yes | — | `nvapi-...` (Nvidia) or `sk-or-...` (OpenRouter) |
| `OPENROUTER_MODEL` | Yes | `openai/gpt-4o-mini` | [openrouter.ai/models](https://openrouter.ai/models) |
| `OPENROUTER_BASE_URL` | No | `https://openrouter.ai/api/v1` | Nvidia: `https://integrate.api.nvidia.com/v1` |
| `PINECONE_API_KEY` | Yes | — | [pinecone.io](https://www.pinecone.io/) |
| `PINECONE_INDEX_NAME` | Yes | `healthlink` | your Pinecone console |
| `PINECONE_DIMENSION` | Yes | `1024` | must match embedding model |
| `EMBEDDING_MODEL` | Yes | `llama-text-embed-v2` | Pinecone built-in |
| `API_BASE_URL` | No | `http://localhost:8080/api/v1` | Streamlit → API |
| `DATABASE_URL` | No | `sqlite:///./data/healthlink.db` | Cloud SQL in prod |
| `GCP_REGION` | No | `us-central1` | Cloud Run region |
| `LANGCHAIN_TRACING_V2` | No | `false` | `true` to enable tracing |
| `LANGCHAIN_API_KEY` | No | — | [smith.langchain.com](https://smith.langchain.com) → Settings → API Keys (`lsv2_pt_...`) |
| `LANGCHAIN_PROJECT` | No | `healthlink` | LangSmith project name |

---

## 🎯 Usage

**Run API + UI (two terminals):**
```bash
# Terminal 1
python -m uvicorn app.main:app --port 8080 --reload

# Terminal 2
streamlit run streamlit_app.py
```
Then open `http://localhost:8501`.

**Or Docker:**
```bash
docker compose up --build
# UI http://localhost:8501  API http://localhost:8080/docs
```

### First-Time Setup
1. Set `LOAD_KB_ON_STARTUP=true` in `.env` once → restart `uvicorn` → watch `Loaded 200 document chunks` (batched 90), then set back to `false`
2. SQLite seeds automatically from `data/doctors.csv` (100 doctors, idempotent)
3. Try the demo prompt below

---

## 🔌 API Reference

All endpoints are served by the monolithic FastAPI app (`app/main.py`). Interactive docs at `/docs` (Swagger) and `/redoc`.

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/` | Root info (`name`, `version`, `endpoints`) |
| `GET` | `/health` | Health probe (also `GET /api/v1/health`) — `app`, `database`, `llm`, `pinecone` |
| `POST` | `/api/v1/assess` | Full 4-agent assessment — body `HealthAssessmentRequest` → `HealthAssessmentResponse` |
| `GET` | `/api/v1/doctors` | List all doctors (100) |
| `GET` | `/api/v1/doctors/{doctor_id}` | Get single doctor by id |
| `GET` | `/api/v1/specialties` | List distinct specialties |
| `POST` | `/api/v1/appointments` | Book appointment — body `{"user_id","slot_id"}` → `Appointment` |
| `GET` | `/api/v1/appointments?user_id=...` | List appointments for a user |
| `PATCH` | `/api/v1/appointments/{id}?status=cancelled` | Update status (`scheduled`/`completed`/`cancelled`) |
| `GET` | `/docs` | Swagger UI |
| `GET` | `/redoc` | ReDoc |
| `GET` | `/openapi.json` | OpenAPI spec |

Example:
```bash
curl -X POST http://127.0.0.1:8080/api/v1/assess \
  -H "Content-Type: application/json" \
  -d '{"user_input":"persistent headache for 3 days","user_id":"u1"}'
```

---

## ☁️ Deployment

### GitHub Actions CI/CD

The repository includes automated CI/CD workflows:

- **CI** (`.github/workflows/01-ci.yaml`): Runs linting and tests on every push/PR
- **CD** (`.github/workflows/02-deploy.yaml`): Builds Docker image, runs smoke tests, and deploys to Cloud Run on main branch pushes

**Required GitHub Secrets:**
Set these in **Settings → Secrets and variables → Actions → Secrets**:
- `GCP_PROJECT_ID`: Your Google Cloud project ID
- `GCP_SA_KEY`: Service account key JSON (with Cloud Run and Artifact Registry permissions)
- `OPENROUTER_API_KEY`: Your OpenRouter API key
- `PINECONE_API_KEY`: Your Pinecone API key

**Required GitHub Variables:**
Set these in **Settings → Secrets and variables → Actions → Variables**:
- `GCP_REGION`: Your GCP region (e.g., `us-central1`)
- `OPENROUTER_MODEL`: Model name (e.g., `openai/gpt-4o-mini`)
- `PINECONE_INDEX_NAME`: Your Pinecone index name
- `PINECONE_DIMENSION`: Embedding dimension (e.g., `1024`)
- `EMBEDDING_MODEL`: Embedding model (e.g., `llama-text-embed-v2`)

### Google Cloud Run
```powershell
# Windows
gcloud auth login
$env:GCP_PROJECT_ID="your-project-id"
./deploy.ps1            # builds with Cloud Build → GCR → deploys to Cloud Run (prints URL)
./teardown.ps1          # deletes service + images (stops billing, scales to zero = ~$0 idle)
```
```bash
# Mac / Linux
export GCP_PROJECT_ID=your-project-id
./deploy.sh
./teardown.sh
```
The scripts read `OPENROUTER_API_KEY` / `PINECONE_API_KEY` and Pinecone config from `.env` and pass them as Cloud Run env vars — keys are never baked into the image. Free tier: 2M requests + 360k vCPU-seconds/month free, scales to zero.

### Hugging Face Spaces
See [`spaces/`](spaces/README.md) — push `spaces/app.py` as a Space with `API_BASE_URL` secret pointing at your Cloud Run URL.

```powershell
# One-click push
powershell -ExecutionPolicy Bypass -File spaces\push.ps1  # Windows
# or
bash spaces/push.sh                                        # Mac/Linux
```
Then in the Space → **Settings → Variables and secrets** → `API_BASE_URL = https://<your-cloud-run-url>/api/v1`.

---

## 📁 Project Structure

<details>
<summary>Click to expand project tree</summary>

```
HealthLink/
├── streamlit_app.py        # Modern webpage UI (top nav + Wake API pill, hero, dashboards tab, SQLite viewer)
├── spaces/
│   ├── app.py              # Hugging Face Spaces UI (same as streamlit_app.py)
│   ├── requirements.txt    # Spaces deps (streamlit + requests)
│   ├── README.md           # Spaces frontmatter
│   ├── push.ps1 / push.sh  # One-click HF push (Windows / Mac/Linux)
│   └── _chunks.json        # (gitignored) BM25 persistence
├── app/
│   ├── main.py             # FastAPI monolith (assess, doctors, appointments, dual /health)
│   ├── orchestrator.py     # LangGraph StateGraph (symptom → doctor → scheduling → summary + Trace)
│   ├── agents/             # symptom.py, doctor.py, scheduling.py, summary.py
│   ├── rag.py              # Hybrid: Pinecone (batched 90) + BM25 (k1=1.5) + RRF (k=60)
│   ├── database.py         # SQLAlchemy doctors + appointments (file DB, Postgres-ready)
│   ├── seed.py             # Pandas CSV seeding (doctors.csv → SQLite, idempotent)
│   ├── security.py         # validate_input, prompt-injection, mask_pii, RateLimiter (0=unlimited)
│   ├── guardrails.py       # scan/soften/harmful/PII checks + disclaimer
│   └── observability.py    # Trace + timed() per-agent latency
├── shared/
│   ├── config.py           # Settings from .env (6 required + 25 optional defaults, sectioned)
│   ├── llm.py              # ChatOpenAI (OpenRouter/Nvidia, max_tokens=0=unlimited) + fallback
│   ├── schemas.py          # Pydantic wire contract (PatientProfile, clarifying_questions, etc.)
│   ├── logging.py          # JSON logs with request_id ContextVar
│   └── tracing.py          # LangSmith env-gated (LANGCHAIN_TRACING_V2)
├── data/
│   ├── doctors.csv         # 100 doctors, 30 specialties
│   ├── symptoms_kb.json    # 200 symptom records
│   └── _chunks.json        # (gitignored) BM25 corpus cache
├── tests/                  # pytest (45 tests: security, guardrails, agents, api, tracing, rag)
├── Dockerfile              # python:3.13-slim single image
├── docker-compose.yml      # api (8000) + ui (8501)
├── .env / .env.example     # Sectioned 7 blocks (LLM/Pinecone/RAG/DB/Security/API/Observability)
├── deploy.ps1 / deploy.sh  # Cloud Run (Cloud Build → GCR → gcloud run)
├── teardown.ps1 / teardown.sh  # delete Cloud Run service + images
├── .github/workflows/      # 01-ci.yaml (lint+pytest) + 02-deploy.yaml (GCR→Cloud Run)
├── ARCHITECTURE.md         # System diagram, data flow, RAG, DB schema
├── README.md               # This file
└── requirements.txt        # FastAPI, LangChain/Graph, Pinecone, Pandas, Streamlit, etc.
```
</details>

---

## 🧪 Demo Scenario

**Input (Streamlit or curl):**

> *“I’ve been having a persistent headache and dizziness for two days, with mild fever 38C and sensitivity to light. Age 34, female.”*

```bash
curl -X POST http://127.0.0.1:8080/api/v1/assess \
  -H "Content-Type: application/json" \
  -d '{"user_input":"I have had a persistent headache and dizziness for two days, with mild fever 38C and sensitivity to light","user_id":"u1","patient_profile":{"age":34,"gender":"Female"}}'
```

**Output:** `symptom_analysis` (4 symptoms, urgency=medium, 3 clarifying Qs first pass → high after answers) + `doctor_recommendations` (Neurology, 2 doctors) + `scheduling_options` (160 slots) + `health_summary` + `doctor_summary` + `metadata.trace` (per-agent ms).

Second request with `clarifying_answers: ["moderate","nausea, vomiting","no other pains"]` → `clarifying_questions=[]` and final assessment.

---

## 🔍 Troubleshooting

| Issue | Likely Cause | Fix |
|-------|--------------|-----|
| `ModuleNotFoundError` | Missing deps | `pip install -r requirements.txt` |
| `OPENROUTER_API_KEY not set` | Missing `.env` | `copy .env.example .env` and fill keys |
| `Cannot reach API` in Streamlit | API not running | `python -m uvicorn app.main:app --port 8000` |
| `Retrieved 0 documents` | KB not indexed | Set `LOAD_KB_ON_STARTUP=true` once and restart |
| `Input length 200 exceeded 96` | Old rag.py | Pull latest `app/rag.py` (batched 90) |
| `429 Too Many Requests` | Rate limit | Set `RATE_LIMIT_MAX=0` for unlimited |
| `JSON decode error` / markdown fallback | Model returned markdown | Switch to `openai/gpt-4o-mini` or `nvidia/nemotron-3-nano-30b-a3b` |
| `streamlit command not found` | venv not active | `.\venv\Scripts\activate` |

---

## 👨‍💻 Development

### Adding New Agents
1. Create `app/agents/my_agent.py` with `def my_agent(...) -> MyOutput`
2. Add schema in `shared/schemas.py`
3. Register node in `app/orchestrator.py` `StateGraph`

### Model Configuration
Any OpenRouter/Nvidia model with `tools`/`structured_outputs` works. Free fast options: `liquid/lfm-2.5-2.6b:free`, `nvidia/nemotron-3-nano-30b-a3b`, `z-ai/glm-5.2:free`. Set `OPENROUTER_MODEL` and `OPENROUTER_BASE_URL` accordingly.

---

## 🛠️ Technology Stack

| Layer | Technology |
|-------|------------|
| Language | Python 3.13 |
| UI | Streamlit |
| Multi-Agent Framework | LangGraph + LangChain + ChatOpenAI |
| LLM Gateway | OpenRouter / Nvidia |
| RAG Framework | LangChain Text Splitters |
| Vector DB | Pinecone |
| Embeddings | llama-text-embed-v2 |
| Keyword Search | BM25 |
| Score Fusion | Reciprocal Rank Fusion |
| Database | SQLite + SQLAlchemy + Pandas |
| Validation | Pydantic v2 |
| Testing | pytest |
| API | FastAPI |
| Tracing | LangSmith + JSON logging |
| Container | Docker |
| Deployment | Google Cloud Run + Hugging Face Spaces |
| CI/CD | GitHub Actions + GCR |

---

## 📚 Sources

- **Doctor dataset:** `data/doctors.csv` (synthetic, 100 records)
- **Symptom KB:** `data/symptoms_kb.json` (200 records, built from medical handbooks)
- **Deployment:** Google Cloud Run (`deploy.ps1`/`deploy.sh`), Hugging Face Spaces (`spaces/`)
