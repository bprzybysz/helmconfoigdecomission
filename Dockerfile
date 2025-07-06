# syntax=docker/dockerfile:1.4
FROM python:3.11-slim-bookworm

# Metadata
LABEL org.opencontainers.image.title="Decommission Tool"
LABEL org.opencontainers.image.description="PostgreSQL database decommissioning tool"
LABEL org.opencontainers.image.version="0.1.0"

# Environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONHASHSEED=random \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_DEFAULT_TIMEOUT=100 \
    DEBIAN_FRONTEND=noninteractive

# Install system dependencies
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update && \
    apt-get install -y --no-install-recommends \
        git \
        curl \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN groupadd --gid 1000 app && \
    useradd --uid 1000 --gid app --shell /bin/bash --create-home app

# Set work directory
WORKDIR /app

# Copy project files
COPY --chown=app:app pyproject.toml ./
COPY --chown=app:app . .

# Install Python dependencies
RUN --mount=type=cache,target=/root/.cache/pip \
    python -m pip install --upgrade pip setuptools wheel && \
    python -m pip install .

# Switch to non-root user
USER app

# Health check for container readiness (simple process check)
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import decommission_tool; print('OK')" || exit 1

# Default command
CMD ["python", "-m", "decommission_tool", "--help"]
