# syntax=docker/dockerfile:1
# ---------------------------------------------------------------------------
# Ours — single image: builds the React SPA, then runs the FastAPI backend
# which serves both the /api and the built frontend from one origin.
# ---------------------------------------------------------------------------

# ---- Stage 1: build the frontend ----
FROM node:20-slim AS frontend
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ---- Stage 2: Python runtime ----
FROM python:3.12-slim AS runtime
ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    FRONTEND_DIST=/app/frontend/dist

WORKDIR /app
COPY backend/ /app/backend/
RUN pip install -e /app/backend

# The compiled SPA (index.html + assets/) served by app.main at "/".
COPY --from=frontend /app/frontend/dist /app/frontend/dist

WORKDIR /app/backend
EXPOSE 8000

# Apply migrations (enables PostGIS + creates the schema on a fresh DB), then
# start the server. Render provides $PORT.
CMD alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
