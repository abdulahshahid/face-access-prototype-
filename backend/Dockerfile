# Use 3.10 for dlib compatibility
FROM python:3.10-slim

WORKDIR /app

# Install build dependencies (System CMake is installed here)
RUN apt-get update && apt-get install -y \
    gcc g++ make cmake curl libpq-dev \
    libopenblas-dev liblapack-dev \
    libx11-dev libgtk-3-dev \
    libjpeg-dev libpng-dev libtiff-dev \
    wget unzip pkg-config \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# 1. Upgrade pip
# 2. Install numpy ONLY (Do not install cmake via pip)
# 3. Install requirements with --no-build-isolation to force usage of pre-installed numpy/system tools
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir numpy==1.24.3 && \
    pip install --no-cache-dir --no-build-isolation -r requirements.txt

COPY . .

# Non-root user setup
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000
CMD ["python", "app/main.py"]
