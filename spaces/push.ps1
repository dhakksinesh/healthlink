# spaces/push.ps1 — one-click push of the HealthLink UI to Hugging Face Spaces (Windows)
# Usage:  powershell -ExecutionPolicy Bypass -File spaces\push.ps1
# Prereq:  git installed, HF token as password when prompted (or `huggingface-cli login`)
$ErrorActionPreference = "Stop"
$SpaceUrl = "https://huggingface.co/spaces/dkxy/healthlink"
$Dir = $PSScriptRoot

Write-Host "==> Pushing $Dir to $SpaceUrl"
Set-Location $Dir

if (-not (Test-Path ".git")) { git init }
git add app.py requirements.txt README.md
# allow empty commit if nothing changed
try { git commit -m "HealthLink UI" } catch { Write-Host "(nothing to commit)" }

if (-not (git remote | Select-String -Pattern "^space$")) {
    git remote add space $SpaceUrl
} else {
    Write-Host "remote 'space' already exists"
}

Write-Host "==> git push space main (use HF token as password)"
git branch -M main
git push space main

Write-Host "DONE — Space: $SpaceUrl"
Write-Host "Set secret in Space → Settings → Variables and secrets: API_BASE_URL = https://<your-cloud-run-url>/api/v1"
