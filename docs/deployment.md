# Deployment Guide

This covers manual setup on a Linux server or Raspberry Pi, plus preparation for Docker deployment.

## Prerequisites

- Python 3.11+ (3.13 recommended)
- Git
- 512 MB RAM minimum (1 GB recommended)
- ~500 MB disk for data files

## Manual Setup (Linux / Raspberry Pi)

### 1. Clone and install

```bash
git clone https://github.com/Usefullatwork/Cot-ExplorerV2.git
cd Cot-ExplorerV2

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -e .

# For development tools (pytest, ruff, mypy)
pip install -e ".[dev]"
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env with your API keys (all optional)
```

See [configuration.md](configuration.md) for all available options.

### 3. Initialize the database

```bash
python -c "from src.db.engine import init_db; init_db()"
```

This creates `data/cot-explorer.db` with all 10 tables.

### 4. Run initial data fetch

```bash
# Fetch all data sources in sequence
python fetch_cot.py          # CFTC COT data
python fetch_calendar.py     # Economic calendar
python fetch_fundamentals.py # FRED macro data
python fetch_prices.py       # Price data from providers
python fetch_all.py          # Full analysis pipeline
```

### 5. Start the API server

```bash
uvicorn src.api.app:app --host 0.0.0.0 --port 8000
```

The API is available at `http://<your-ip>:8000`. OpenAPI docs at `/docs`.

### 6. Serve the frontend

The frontend is a static Vite build in `frontend/`. Serve it with any static file server or let uvicorn handle it.

```bash
# Development
cd frontend && npx vite

# Or serve via the API (if configured)
# The API serves static files from frontend/dist/
```

## Automated Data Updates (Cron)

The `update.sh` script runs the full pipeline. Schedule it 4 times daily during market hours.

```bash
# Edit crontab
crontab -e

# Add these lines (CET times: 07:45, 12:30, 14:15, 17:15)
45 7  * * 1-5 cd /home/pi/Cot-ExplorerV2 && /home/pi/Cot-ExplorerV2/.venv/bin/python -m src.pipeline.runner >> /var/log/cot-explorer.log 2>&1
30 12 * * 1-5 cd /home/pi/Cot-ExplorerV2 && /home/pi/Cot-ExplorerV2/.venv/bin/python -m src.pipeline.runner >> /var/log/cot-explorer.log 2>&1
15 14 * * 1-5 cd /home/pi/Cot-ExplorerV2 && /home/pi/Cot-ExplorerV2/.venv/bin/python -m src.pipeline.runner >> /var/log/cot-explorer.log 2>&1
15 17 * * 1-5 cd /home/pi/Cot-ExplorerV2 && /home/pi/Cot-ExplorerV2/.venv/bin/python -m src.pipeline.runner >> /var/log/cot-explorer.log 2>&1
```

Alternatively, use `update.sh` directly:

```bash
45 7 * * 1-5 /home/pi/Cot-ExplorerV2/update.sh
```

## Raspberry Pi Notes

### Performance

- Initial COT data fetch downloads ~20 MB from CFTC.gov (one-time).
- Subsequent updates are incremental and take 1-3 minutes on RPi 4.
- SQLite WAL mode handles concurrent reads well on SD cards.
- The backtest engine uses zero external dependencies (stdlib only), keeping memory footprint low.

### Recommended RPi setup

```bash
# Use external USB SSD instead of SD card for data/
# Mount it and symlink:
sudo mount /dev/sda1 /mnt/ssd
ln -s /mnt/ssd/cot-data data

# Reduce swap thrashing
echo "vm.swappiness=10" | sudo tee -a /etc/sysctl.conf
sudo sysctl -p
```

### Run as a systemd service

Create `/etc/systemd/system/cot-explorer.service`:

```ini
[Unit]
Description=Cot-ExplorerV2 API Server
After=network.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/Cot-ExplorerV2
Environment="PATH=/home/pi/Cot-ExplorerV2/.venv/bin"
EnvironmentFile=/home/pi/Cot-ExplorerV2/.env
ExecStart=/home/pi/Cot-ExplorerV2/.venv/bin/uvicorn src.api.app:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable cot-explorer
sudo systemctl start cot-explorer
```

## Docker (Phase I)

A Dockerfile will be created in Phase I. The container will:

1. Use `python:3.13-slim` base image
2. Install dependencies from `pyproject.toml`
3. Copy source and config
4. Expose port 8000
5. Mount `data/` as a volume for persistence
6. Run uvicorn as the entrypoint

Planned `docker-compose.yml` structure:

```yaml
services:
  api:
    build: .
    ports:
      - "8000:8000"
    volumes:
      - ./data:/app/data
    env_file:
      - .env
    restart: unless-stopped
```

## Reverse Proxy (Nginx)

For production, put Nginx in front of uvicorn:

```nginx
server {
    listen 80;
    server_name cot.example.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

## Health Check

The API exposes a health endpoint:

```bash
curl http://localhost:8000/api/v1/health
```

Use this for Docker health checks, uptime monitors, and systemd watchdog integration.
