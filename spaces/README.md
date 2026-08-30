---
title: HealthLink
emoji: 🏥
colorFrom: blue
colorTo: green
sdk: docker
pinned: false
---

# HealthLink on Hugging Face Spaces

This Space hosts the **patient-facing Streamlit UI** of HealthLink. It is a thin
client: it calls the HealthLink API (the FastAPI monolith) over HTTP.

## Set up

1. Deploy the HealthLink API to Google Cloud Run (`../deploy.ps1`) and copy the
   URL (e.g. `https://healthlink-xxx-uc.a.run.app/api/v1`).
2. In the Space settings add a **Secret**:
   - `API_BASE_URL` = `https://<your-cloud-run-url>/api/v1`

That's it - the UI reads `API_BASE_URL` at startup. The Space itself needs no
LLM or Pinecone keys because all intelligence lives in the API service.

## Push this folder as the Space

```bash
# from this folder (spaces/)
git init && git add . && git commit -m "HealthLink UI"
git remote add space https://huggingface.co/spaces/<your-username>/healthlink
git push space main
```

The full monolith (FastAPI + agents + data) lives at the repository root; this
folder is a self-contained copy of the UI only.