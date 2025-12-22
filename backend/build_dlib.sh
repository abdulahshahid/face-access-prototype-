#!/bin/bash
set -e

echo "=== Installing dlib system dependencies ==="
apt-get update
apt-get install -y \
    libdlib-dev \
    libdlib19 \
    libdlib-data

echo "=== Installing Python dlib ==="
# Try to install dlib with specific build flags
pip install --no-cache-dir \
    --global-option=build_ext \
    --global-option="-DUSE_AVX_INSTRUCTIONS=ON" \
    dlib==19.24.0 || \
    pip install --no-cache-dir dlib==19.24.0
