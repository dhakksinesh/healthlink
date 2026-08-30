#!/usr/bin/env bash
# spaces/push.sh — one-click push to Hugging Face Spaces (macOS/Linux/Git-Bash)
# Usage:  bash spaces/push.sh
set -euo pipefail
SPACE_URL="https://huggingface.co/spaces/dkxy/healthlink"
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
echo "==> Pushing $DIR to $SPACE_URL"
cd "$DIR"
if [ ! -d .git ]; then git init; fi
git add app.py requirements.txt README.md
git commit -m "HealthLink UI" || echo "(nothing to commit)"
if ! git remote | grep -q "^space$"; then
  git remote add space "$SPACE_URL"
else
  echo "remote 'space' already exists"
fi
echo "==> git push space main (use HF token as password)"
git branch -M main
git push space main
echo "DONE — Space: $SPACE_URL"
echo "Set secret in Space → Settings → Variables and secrets: API_BASE_URL = https://<your-cloud-run-url>/api/v1"
