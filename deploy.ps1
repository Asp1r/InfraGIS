$ErrorActionPreference = "Stop"

if (-not (Test-Path ".env")) {
  throw "Missing .env file in project root"
}

Write-Host "Building and starting InfraGIS..."
docker compose -f docker-compose.prod.yml up -d --build

Write-Host "Waiting for health endpoint..."
for ($i = 0; $i -lt 40; $i++) {
  try {
    Invoke-WebRequest -Uri "http://127.0.0.1/health" -UseBasicParsing | Out-Null
    Write-Host "InfraGIS is healthy"
    exit 0
  } catch {
    Start-Sleep -Seconds 3
  }
}

Write-Host "Health check failed"
docker compose -f docker-compose.prod.yml ps
exit 1
