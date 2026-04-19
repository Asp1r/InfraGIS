# InfraGIS Deployment Guide

## 1. Server prerequisites

- Ubuntu 22.04+ (or similar Linux with Docker support)
- Docker Engine + Docker Compose plugin
- Open ports: `80/tcp` (and `443/tcp` if you add TLS proxy)

## 2. Prepare environment

```bash
cp .env.example .env
```

Required production values in `.env`:
- `POSTGRES_PASSWORD`
- `JWT_SECRET`
- `ADMIN_PASSWORD`

## 3. Start production stack

```bash
docker compose -f docker-compose.prod.yml up -d --build
```

## 4. Verify

```bash
curl http://127.0.0.1/health
docker compose -f docker-compose.prod.yml ps
```

## 5. Update release

```bash
git pull
docker compose -f docker-compose.prod.yml up -d --build
```

## 6. Rollback (quick option)

If deploy failed after pull, checkout previous commit and rebuild:

```bash
git checkout <previous_commit_sha>
docker compose -f docker-compose.prod.yml up -d --build
```

## 7. Fully automatic deploy over SSH

Before first run:
- clone repo on server into `PROJECT_DIR`
- create `.env` on server (do not store it in git)
- ensure user can run `docker compose` without sudo

Linux/macOS client:

```bash
chmod +x scripts/deploy-remote.sh
./scripts/deploy-remote.sh \
  --host <SERVER_IP> \
  --user <SSH_USER> \
  --project-dir <PROJECT_DIR_ON_SERVER> \
  --branch master \
  --key ~/.ssh/id_rsa
```

Windows PowerShell client:

```powershell
.\scripts\deploy-remote.ps1 `
  -HostName "<SERVER_IP>" `
  -UserName "<SSH_USER>" `
  -ProjectDir "<PROJECT_DIR_ON_SERVER>" `
  -Branch "master" `
  -SshKey "$HOME/.ssh/id_rsa"
```

What the script does:
- connects to server via SSH
- validates `.env` and git repo
- saves current commit as rollback point
- updates branch with `git pull --ff-only`
- runs `docker compose -f docker-compose.prod.yml up -d --build`
- waits for health endpoint
- automatically rolls back to previous commit if deploy or healthcheck fails

## 8. Troubleshooting

- `Docker Compose is configured to build using Bake, but buildx isn't installed`:
  this warning is safe to ignore; deployment still works.
- Backend in `Restarting/Unhealthy`:
  run `docker logs --tail=200 infragis-backend-1` and check app startup traceback.
- Frontend build fails on `npm ci` because lockfile is missing:
  project uses `npm install` in Docker build intentionally.
- API check:
  `curl -fsS http://127.0.0.1/health` must return `{"status":"ok"}`.

## 9. Auto-update with systemd

This project includes:
- `scripts/auto-update.sh` (git pull + deploy + healthcheck + rollback)
- `deploy/systemd/infragis-auto-update.service`
- `deploy/systemd/infragis-auto-update.timer`

Server installation steps:

```bash
cd /home/infragis
chmod +x scripts/auto-update.sh
sed -i 's/\r$//' scripts/auto-update.sh
sudo cp deploy/systemd/infragis-auto-update.service /etc/systemd/system/
sudo cp deploy/systemd/infragis-auto-update.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now infragis-auto-update.timer
sudo systemctl list-timers | grep infragis-auto-update
```

Manual run / logs:

```bash
sudo systemctl start infragis-auto-update.service
sudo systemctl status infragis-auto-update.service --no-pager
journalctl -u infragis-auto-update.service -n 100 --no-pager
```
