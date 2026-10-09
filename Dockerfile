# Backend / worker image (Roadmap Phase 10).
#
# NOTE: Docker was not available on the dev machine when this file was written —
# it is written to standard uv/Django practice but has NOT been built or run
# locally (see docs/PHASE_REPORTS/PHASE_10.md for the honest verification status).
#
# MetaTrader5 is excluded on Linux via the PEP 508 marker in pyproject.toml;
# the MT5 connector degrades to "unavailable" inside the container by design.

FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app

# Dependency layer (cached unless pyproject/uv.lock change).
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project

# Application code.
COPY . .
RUN uv sync --frozen

EXPOSE 8000

# Default: HTTP API. The worker service overrides the command in docker-compose.
CMD ["uv", "run", "gunicorn", "nazbeen_forex_ai.wsgi:application", \
     "--bind", "0.0.0.0:8000", "--workers", "3", "--timeout", "60"]
