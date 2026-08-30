$ErrorActionPreference = "Stop"

$Project = $env:GCP_PROJECT_ID
$Region  = $env:GCP_REGION
$ServiceName = "healthlink"

if (-not $Project) { throw "GCP_PROJECT_ID is not set in env." }
if (-not $Region)  { throw "GCP_REGION is not set in env." }

Write-Host "==> Deleting Cloud Run service '$ServiceName'..."
gcloud run services delete $ServiceName --project $Project --region $Region --quiet
if ($LASTEXITCODE -ne 0) { throw "Failed to delete service." }

Write-Host "==> Deleting container images..."
gcloud container images delete "gcr.io/$Project/healthlink" --quiet --force-delete-tags
if ($LASTEXITCODE -ne 0) { Write-Host "(image cleanup skipped)" }

Write-Host "DONE. Cloud Run service and images removed."
