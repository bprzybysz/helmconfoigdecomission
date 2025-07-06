# 🐳 Docker & Containerization Best Practices for Python

## 🎯 Core Principles

### Base Image Selection
- **Choose minimal official Python images:**
  - ✅ `python:3.11-slim` or `python:3.12-slim` for production.
  - Reduces attack surface and image size.
- **Avoid Alpine unless necessary:**
  - May cause issues with C extensions in Python packages.

```dockerfile
# ✅ Good: Minimal base image
FROM python:3.12-slim

# ❌ Bad: Large base image
# FROM python:3.12

# ❌ Risky: Alpine might cause compatibility issues if C extensions are used
# FROM python:3.12-alpine
```

### Multi-Stage Builds
- Separate build and runtime stages.
- Prevents build tools and dev dependencies from entering production image.

```dockerfile
# ✅ Multi-stage build for lean images
# Stage 1: Build dependencies
FROM python:3.12-slim as builder
WORKDIR /app
COPY requirements.txt .
RUN apt-get update && apt-get install -y --no-install-recommends gcc \
    && pip wheel --no-cache-dir --no-deps --wheel-dir /app/wheels -r requirements.txt \
    && apt-get autoremove -y gcc \
    && rm -rf /var/lib/apt/lists/*

# Stage 2: Production image
FROM python:3.12-slim
WORKDIR /app
COPY --from=builder /app/wheels /wheels
COPY --from=builder /app/requirements.txt .
RUN pip install --no-cache-dir /wheels/*
COPY . /app

CMD ["python", "app.py"]
```

## 📦 Dependency Management

### Pin All Dependencies
- Pin exact versions in `requirements.txt` (`package==1.2.3`).
- Ensures reproducible builds and mitigates supply chain attacks.

### Maximize Docker Cache
- Copy `requirements.txt` and install dependencies **before** copying your application code.

```dockerfile
# ✅ Maximize cache utilization
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . /app # Application code last
```

### Production vs. Development Dependencies
- Use separate `requirements.txt` files (e.g., `requirements-dev.txt`).

## 🚀 Container Optimization

### Environment Variables
- Set Python environment variables for performance and cleanliness.

```dockerfile
# ✅ Optimize Python behavior
ENV PYTHONDONTWRITEBYTECODE 1 # No .pyc files
ENV PYTHONUNBUFFERED 1      # Unbuffered stdout/stderr
```

### Minimize Layers
- Combine `RUN` commands where possible to reduce image layers.
- Clean up after commands (e.g., `rm -rf /var/lib/apt/lists/*`).

```dockerfile
# ✅ Combine commands and clean up
RUN apt-get update && apt-get install -y some-package \
    && rm -rf /var/lib/apt/lists/* # Clean up apt cache
```

### Health Checks
- Add health checks to ensure the container is running correctly.

```dockerfile
# ✅ Health check for application readiness
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD ["curl", "-f", "http://localhost:8000/health"] || exit 1
```

## 🔒 Security Hardening

### Run as Non-Root User
- Create a dedicated non-root user and switch to it.

```dockerfile
# ✅ Create and switch to non-root user
RUN useradd --create-home --shell /bin/bash appuser
USER appuser
```

### Read-Only Filesystem
- Run containers with `--read-only` flag at runtime if possible.
- Limits potential write access for attackers.

### Vulnerability Scanning
- Integrate container vulnerability scanners (e.g., Snyk, Trivy) into CI/CD.

### Pin Base Image Versions
- Always use specific, immutable tags for base images (e.g., `python:3.12-slim-bookworm`), not `latest`.

## 📋 Dockerization Checklist

- [ ] Using minimal base image (`-slim` variant).
- [ ] Multi-stage builds implemented.
- [ ] All dependencies pinned in `requirements.txt`.
- [ ] Dependencies installed before application code.
- [ ] `PYTHONDONTWRITEBYTECODE` and `PYTHONUNBUFFERED` set.
- [ ] Minimized `RUN` layers and cleaned up apt/pip caches.
- [ ] Running as a non-root user.
- [ ] Health checks configured.
- [ ] Image vulnerability scanning in CI/CD.
- [ ] Base image versions explicitly pinned.
- [ ] Secrets injected via environment variables (not hardcoded). 