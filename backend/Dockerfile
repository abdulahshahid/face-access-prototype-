# syntax=docker/dockerfile:1
FROM python:3.10-slim-bullseye

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    cmake \
    libopenblas-dev \
    liblapack-dev \
    libx11-dev \
    libgtk-3-dev \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# --- OPTIMIZED HERE ---
# 1. Removed '--no-cache-dir' so pip uses cache
# 2. Added BuildKit mount (optional but recommended) to persist cache across builds
#    If this line fails, just remove the "--mount=..." part.
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --upgrade pip && \
    pip install numpy==1.24.3 && \
    pip install -r requirements.txt

# Copy the entire backend directory
COPY . .

# Set PYTHONPATH to include the root /app so imports work correctly
ENV PYTHONPATH=/app:$PYTHONPATH

# Non-root user setup
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

# Point to the file inside the app directory
CMD ["python", "app/main.py"]