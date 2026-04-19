param(
  [Parameter(Mandatory = $true)][string]$HostName,
  [Parameter(Mandatory = $true)][string]$UserName,
  [Parameter(Mandatory = $true)][string]$ProjectDir,
  [string]$Branch = "master",
  [string]$SshKey = "",
  [int]$Port = 22,
  [string]$HealthUrl = "http://127.0.0.1/health"
)

$ErrorActionPreference = "Stop"

$sshArgs = @("-p", "$Port", "-o", "StrictHostKeyChecking=accept-new")
if ($SshKey -ne "") {
  $sshArgs += @("-i", $SshKey)
}

$remote = "$UserName@$HostName"

$remoteScript = @'
set -euo pipefail

cd "__PROJECT_DIR__"

if [[ ! -f ".env" ]]; then
  echo "ERROR: .env is missing in __PROJECT_DIR__"
  exit 1
fi

if [[ ! -d ".git" ]]; then
  echo "ERROR: __PROJECT_DIR__ is not a git repository"
  exit 1
fi

if ! command -v docker >/dev/null 2>&1; then
  echo "ERROR: docker is not installed on server"
  exit 1
fi

if ! docker compose version >/dev/null 2>&1; then
  echo "ERROR: docker compose plugin is not available on server"
  exit 1
fi

CURRENT_COMMIT=$(git rev-parse --short HEAD)
echo "Current commit: $CURRENT_COMMIT"

git fetch --all --prune
git checkout "__BRANCH__" >/dev/null 2>&1 || git checkout -B "__BRANCH__" "origin/__BRANCH__"
git pull --ff-only origin "__BRANCH__"

NEW_COMMIT=$(git rev-parse --short HEAD)
echo "Target commit: $NEW_COMMIT"

set +e
docker compose -f docker-compose.prod.yml up -d --build
DEPLOY_EXIT=$?
set -e

if [[ $DEPLOY_EXIT -ne 0 ]]; then
  echo "Deploy step failed, rollback to $CURRENT_COMMIT"
  git checkout "$CURRENT_COMMIT"
  docker compose -f docker-compose.prod.yml up -d --build
  git checkout "__BRANCH__" >/dev/null 2>&1 || true
  exit 1
fi

for i in $(seq 1 40); do
  if curl -fsS "__HEALTH_URL__" >/dev/null 2>&1; then
    echo "Health check passed"
    exit 0
  fi
  sleep 3
done

echo "Health check failed, rollback to $CURRENT_COMMIT"
git checkout "$CURRENT_COMMIT"
docker compose -f docker-compose.prod.yml up -d --build
git checkout "__BRANCH__" >/dev/null 2>&1 || true
exit 1
'@

$remoteScript = $remoteScript.Replace("__PROJECT_DIR__", $ProjectDir)
$remoteScript = $remoteScript.Replace("__BRANCH__", $Branch)
$remoteScript = $remoteScript.Replace("__HEALTH_URL__", $HealthUrl)
$remoteScript = $remoteScript -replace "`r", ""

Write-Host "Deploying to ${remote}:$ProjectDir (branch=$Branch)"
$remoteScript | ssh @sshArgs $remote "bash -s"
if ($LASTEXITCODE -ne 0) {
  throw "Remote deploy failed with exit code $LASTEXITCODE"
}
