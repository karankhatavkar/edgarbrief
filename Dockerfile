# Single-container deploy (Option A): build the React SPA, then serve it and the
# FastAPI API from one uvicorn process on the same origin.

# ---- Stage 1: build the React SPA ----
FROM node:22-slim AS frontend
WORKDIR /web

# Public, browser-safe build-time config. Vite inlines VITE_* into the static
# bundle at build time, so these must be present here (passed as build args by
# docker-compose). No secrets — only the anon key / project URL / API path.
ARG VITE_API_BASE_URL=/api
ARG VITE_SUPABASE_URL
ARG VITE_SUPABASE_ANON_KEY
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL \
    VITE_SUPABASE_URL=$VITE_SUPABASE_URL \
    VITE_SUPABASE_ANON_KEY=$VITE_SUPABASE_ANON_KEY

RUN npm install -g pnpm@9

# Install deps first (cached unless the lockfile/manifest change). .npmrc carries
# the minimum-release-age policy; --frozen-lockfile pins exact versions.
COPY frontend/package.json frontend/pnpm-lock.yaml frontend/.npmrc ./
RUN pnpm install --frozen-lockfile

COPY frontend/ ./
RUN pnpm build   # -> /web/dist

# ---- Stage 2: Python runtime serving API + the built SPA ----
FROM python:3.12-slim AS runtime

# Install uv from PyPI rather than pulling ghcr.io/astral-sh/uv. The self-hosted
# runner's Docker can't reliably pull from ghcr (anonymous 403), and PyPI is the
# one source we already depend on — so this keeps the build to a single registry.
RUN pip install --no-cache-dir uv

WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy

# Install dependencies first (cached unless the lockfile changes), then the
# project itself once the source is copied in.
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY backend/ ./
RUN uv sync --frozen --no-dev

# The built frontend, served by FastAPI when FRONTEND_DIST is set (see main.py).
COPY --from=frontend /web/dist ./frontend_dist
ENV FRONTEND_DIST=/app/frontend_dist

EXPOSE 8000
CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
