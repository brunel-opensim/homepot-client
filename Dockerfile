# Multi-stage build for HOMEPOT Client
# Stage 1: Build stage
FROM python:3.11-slim as builder

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies including PostgreSQL client libraries
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Create and set the working directory
WORKDIR /app

# Copy backend dependency files and source
COPY backend/pyproject.toml ./
COPY README.md ../README.md
COPY backend/src/ src/

# Install Python dependencies
RUN pip install --upgrade pip && \
    pip install .

# Stage 2: Production stage
FROM python:3.11-slim as production

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HOMEPOT_ENV=production \
    PYTHONPATH=/app

# Install runtime dependencies including PostgreSQL client
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    libpq5 \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd -r homepot && useradd -r -g homepot homepot

# Create application directory
WORKDIR /app

# Copy installed packages from builder stage
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application source
COPY --from=builder /app/src /app/src
COPY --chown=homepot:homepot backend/pyproject.toml ./
COPY --chown=homepot:homepot README.md ../README.md

# Create necessary directories and set permissions
RUN mkdir -p /app/logs && \
    chown -R homepot:homepot /app && \
    chmod -R 755 /app/logs

# Switch to non-root user
USER homepot

# Expose port
EXPOSE 8000

# Health check with longer start period for database initialization
HEALTHCHECK --interval=30s --timeout=30s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Use the properly installed package
CMD ["uvicorn", "homepot.main:app", "--host", "0.0.0.0", "--port", "8000", "--log-level", "info"]
