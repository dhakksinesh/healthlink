#!/usr/bin/env bash
set -euo pipefail

PROJECT="${GCP_PROJECT_ID:?GCP_PROJECT_ID not set in env}"
REGION="${GCP_REGION:?GCP_REGION not set in env}"
SERVICE="healthlink"

echo "==> Deleting Cloud Run service '$SERVICE'..."
gcloud run services delete "$SERVICE" --project "$PROJECT" --region "$REGION" --quiet

echo "==> Deleting container images..."
gcloud container images delete "gcr.io/$PROJECT/healthlink" --quiet --force-delete-tags || true

echo "DONE. Cloud Run service and images removed."
