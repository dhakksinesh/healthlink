#!/usr/bin/env bash
set -euo pipefail

PROJECT="${GCP_PROJECT_ID:?GCP_PROJECT_ID not set in env}"
REGION="${GCP_REGION:?GCP_REGION not set in env}"
SERVICE="healthlink"
IMAGE="gcr.io/$PROJECT/healthlink:latest"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

read_key() {
  if [ -f "$SCRIPT_DIR/.env" ]; then
    grep -E "^\s*$1\s*=" "$SCRIPT_DIR/.env" | head -n1 | sed -E "s/^\s*$1\s*=\s*//" | tr -d '"' | xargs
  else
    printenv "$1" 2>/dev/null || true
  fi
}

OPENROUTER_KEY="$(read_key OPENROUTER_API_KEY)"
PINECONE_KEY="$(read_key PINECONE_API_KEY)"
MODEL_NAME="$(read_key OPENROUTER_MODEL || true)"; [ -z "$MODEL_NAME" ] && MODEL_NAME="$(read_key LLM_MODEL_NAME || true)"
INDEX_NAME="$(read_key PINECONE_INDEX_NAME || true)"
EMBEDDING="$(read_key EMBEDDING_MODEL || true)"
DIMENSION="$(read_key PINECONE_DIMENSION || true)"

collect_extra_env() {
  local k v pairs=""
  local tmpfile
  tmpfile=$(mktemp)
  grep -E "^\s*[^#\s][^=]*=" "$SCRIPT_DIR/.env" 2>/dev/null > "$tmpfile" || true
  while IFS='=' read -r k v; do
    k=$(echo "$k" | xargs)
    v=$(echo "$v" | xargs)
    if [ -z "$k" ]; then continue; fi
    case "$k" in \#*) continue;; esac
    case "$k" in OPENROUTER_API_KEY|PINECONE_API_KEY|OPENROUTER_MODEL|PINECONE_INDEX_NAME|EMBEDDING_MODEL|PINECONE_DIMENSION|GCP_PROJECT_ID|GCP_REGION) continue;; esac
    v=$(read_key "$k" || true)
    if [ -z "$v" ]; then continue; fi
    if [ -z "$pairs" ]; then pairs="${k}=${v}"; else pairs="${pairs},${k}=${v}"; fi
  done < "$tmpfile"
  rm -f "$tmpfile"
  echo "${pairs}"
}
EXTRA_ENV=$(collect_extra_env)

[ -z "$OPENROUTER_KEY" ] && { echo "OPENROUTER_API_KEY not set" >&2; exit 1; }
[ -z "$PINECONE_KEY" ] && { echo "PINECONE_API_KEY not set" >&2; exit 1; }
[ -z "$MODEL_NAME" ] && { echo "OPENROUTER_MODEL not set" >&2; exit 1; }
[ -z "$INDEX_NAME" ] && { echo "PINECONE_INDEX_NAME not set" >&2; exit 1; }
[ -z "$EMBEDDING" ] && { echo "EMBEDDING_MODEL not set" >&2; exit 1; }
[ -z "$DIMENSION" ] && { echo "PINECONE_DIMENSION not set" >&2; exit 1; }

echo "==> Building image with Cloud Build ($IMAGE)..."
gcloud builds submit --tag "$IMAGE" "$SCRIPT_DIR"

echo "==> Deploying Cloud Run service '$SERVICE'..."
BASE_ENV="OPENROUTER_API_KEY=$OPENROUTER_KEY,PINECONE_API_KEY=$PINECONE_KEY,OPENROUTER_MODEL=$MODEL_NAME,PINECONE_INDEX_NAME=$INDEX_NAME,EMBEDDING_MODEL=$EMBEDDING,PINECONE_DIMENSION=$DIMENSION,LOAD_KB_ON_STARTUP=true"
if [ -n "$EXTRA_ENV" ]; then BASE_ENV="$BASE_ENV,$EXTRA_ENV"; fi
gcloud run deploy "$SERVICE" \
  --image "$IMAGE" \
  --project "$PROJECT" \
  --region "$REGION" \
  --platform managed \
  --allow-unauthenticated \
  --port 8080 \
  --min-instances 0 --max-instances 2 \
  --set-env-vars "$BASE_ENV"

URL="$(gcloud run services describe "$SERVICE" --project "$PROJECT" --region "$REGION" --format 'value(status.url)')"
echo ""
echo "DONE."
echo "  API / docs: $URL/docs"
echo "  Health:     $URL/health"
echo "Run ./teardown.sh to delete the service and stop billing."
