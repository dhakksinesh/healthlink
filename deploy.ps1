$ErrorActionPreference = "Stop"

$Project = $env:GCP_PROJECT_ID
$Region  = $env:GCP_REGION
$ServiceName = "healthlink"
$Image = "gcr.io/$Project/healthlink:latest"

if (-not $Project) { throw "GCP_PROJECT_ID is not set in env." }
if (-not $Region)  { throw "GCP_REGION is not set in env." }

Write-Host "==> gcloud project: $Project (region $Region)"

$EnvFile = Join-Path $PSScriptRoot ".env"
function Read-Key($name) {
    if (Test-Path $EnvFile) {
        $line = Select-String -Path $EnvFile -Pattern "^\s*$name\s*=" | Select-Object -First 1
        if ($null -ne $line) { return ($line.Line -replace "^\s*$name\s*=", "").Trim().Trim('"').Trim("'") }
    }
    return [Environment]::GetEnvironmentVariable($name)
}

$OpenRouterKey  = Read-Key "OPENROUTER_API_KEY"
$PineconeKey    = Read-Key "PINECONE_API_KEY"
$ModelName      = Read-Key "OPENROUTER_MODEL";      if (-not $ModelName)      { $ModelName = Read-Key "LLM_MODEL_NAME" }
$IndexName      = Read-Key "PINECONE_INDEX_NAME"
$EmbeddingModel = Read-Key "EMBEDDING_MODEL"
$Dimension      = Read-Key "PINECONE_DIMENSION"

# --- Collect all non-secret tuning vars from .env (so Cloud Run mirrors local) ---
function Collect-EnvVars {
    $pairs = @()
    if (Test-Path $EnvFile) {
        Get-Content $EnvFile | ForEach-Object {
            $l = $_.Trim()
            if (-not $l -or $l.StartsWith("#")) { return }
            if ($l -notmatch "=") { return }
            $k = ($l -split "=",2)[0].Trim()
            # Skip the 7 already handled above (with special validation) and GCP infra vars
            if ($k -in @("OPENROUTER_API_KEY","PINECONE_API_KEY","OPENROUTER_MODEL","PINECONE_INDEX_NAME","EMBEDDING_MODEL","PINECONE_DIMENSION","GCP_PROJECT_ID","GCP_REGION")) { return }
            $v = Read-Key $k
            if ($v) { $pairs += "$k=$v" }
        }
    }
    return $pairs
}
$ExtraEnv = Collect-EnvVars
# LangSmith is env-gated — explicitly validate if enabled, but allow disabled (0/false)
# No throw for LANGCHAIN_*; they are optional per shared/config.py

if (-not $OpenRouterKey)  { throw "OPENROUTER_API_KEY not found in .env or environment." }
if (-not $PineconeKey)    { throw "PINECONE_API_KEY not found in .env or environment." }
if (-not $ModelName)      { throw "OPENROUTER_MODEL not found in .env or environment." }
if (-not $IndexName)      { throw "PINECONE_INDEX_NAME not found in .env or environment." }
if (-not $EmbeddingModel) { throw "EMBEDDING_MODEL not found in .env or environment." }
if (-not $Dimension)      { throw "PINECONE_DIMENSION not found in .env or environment." }

Write-Host "==> Building image with Cloud Build ($Image)..."
gcloud builds submit --tag $Image $PSScriptRoot --project $Project --only-show-errors
if ($LASTEXITCODE -ne 0) { throw "Cloud Build failed." }

Write-Host "==> Deploying Cloud Run service '$ServiceName'..."
$BaseEnv = "OPENROUTER_API_KEY=$OpenRouterKey,PINECONE_API_KEY=$PineconeKey,OPENROUTER_MODEL=$ModelName,PINECONE_INDEX_NAME=$IndexName,EMBEDDING_MODEL=$EmbeddingModel,PINECONE_DIMENSION=$Dimension,LOAD_KB_ON_STARTUP=true"
if ($ExtraEnv.Count -gt 0) { $BaseEnv += "," + ($ExtraEnv -join ",") }
gcloud run deploy $ServiceName `
    --image $Image `
    --project $Project `
    --region $Region `
    --platform managed `
    --allow-unauthenticated `
    --port 8080 `
    --min-instances 0 --max-instances 2 `
    --set-env-vars $BaseEnv `
    --only-show-errors
if ($LASTEXITCODE -ne 0) { throw "Cloud Run deploy failed." }

$Url = gcloud run services describe $ServiceName --project $Project --region $Region --format "value(status.url)"
Write-Host ""
Write-Host "DONE."
Write-Host "  API / docs: $Url/docs"
Write-Host "  Health:     $Url/health"
Write-Host "Note: first request after idle may be slow (cold start)."
Write-Host "Run .\teardown.ps1 to delete the service and stop billing."
