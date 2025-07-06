FROM python:3.11-slim-bookworm

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Set work directory
WORKDIR /app

# Copy project files
COPY pyproject.toml ./
COPY . .

# Install the package and dependencies
RUN pip install --no-cache-dir .

# Create non-root user
RUN addgroup --system app && adduser --system --group app
USER app

# Default command
CMD ["python", "-m", "decommission_tool", "--help"]
