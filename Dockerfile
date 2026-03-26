# ---------- Stage 1: Frontend build ----------
FROM node:20-slim AS frontend-build

WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --production=false
COPY frontend/ ./
RUN npm run build

# ---------- Stage 2: Python dependencies ----------
FROM python:3.11-slim AS python-deps

WORKDIR /app
COPY pyproject.toml ./
RUN pip install --no-cache-dir -e . && pip cache purge

# ---------- Stage 3: Production ----------
FROM python:3.11-slim AS production

LABEL maintainer="Cot-ExplorerV2"
LABEL description="COT + SMC trading signal platform API"

# Security: run as non-root
RUN groupadd -r cotuser && useradd -r -g cotuser cotuser

WORKDIR /app

# Copy Python environment from deps stage
COPY --from=python-deps /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=python-deps /usr/local/bin /usr/local/bin

# Copy application source
COPY pyproject.toml ./
COPY src/ ./src/
COPY alembic/ ./alembic/
COPY alembic.ini ./

# Copy thin wrappers (needed for backward-compat CLI)
COPY fetch_all.py fetch_cot.py fetch_prices.py fetch_fundamentals.py \
     fetch_calendar.py push_signals.py smc.py \
     build_timeseries.py build_price_history.py build_combined.py ./

# Copy built frontend
COPY --from=frontend-build /app/frontend/dist ./frontend/dist/

# Create data directory with correct ownership
RUN mkdir -p data && chown -R cotuser:cotuser /app

# Install the package in editable mode
RUN pip install --no-cache-dir -e .

USER cotuser

EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

# Default command: run API server
CMD ["uvicorn", "src.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
