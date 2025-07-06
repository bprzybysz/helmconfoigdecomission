# syntax=docker/dockerfile:1.4

# Build stage
FROM python:3.11-slim-bookworm as builder

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONHASHSEED=random \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_DEFAULT_TIMEOUT=100 \
    POETRY_VERSION=1.5.1

# Install system dependencies
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update && \
    apt-get install -y --no-install-recommends \
    git \
    curl \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Poetry
RUN pip install "poetry==$POETRY_VERSION"

# Set work directory
WORKDIR /app

# Copy only the files needed for dependency installation
COPY pyproject.toml poetry.lock* ./

# Install dependencies
RUN --mount=type=cache,target=/root/.cache/pypoetry \
    poetry config virtualenvs.in-project true && \
    poetry install --only main --no-interaction --no-ansi

# Runtime stage
FROM python:3.11-slim-bookworm as runtime

# Install runtime dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    git \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN addgroup --system app && adduser --system --group app

# Set work directory
WORKDIR /app

# Copy Python environment from builder
COPY --from=builder /app/.venv .venv
ENV PATH="/app/.venv/bin:$PATH"

# Copy application code
COPY --chown=app:app . .

# Switch to non-root user
USER app

# Set default command
CMD ["python", "-m", "decommission_tool", "--help"]
