#!/bin/bash
set -e

echo "Installing dependencies..."

# First install numpy and cmake
pip install --no-cache-dir numpy==1.24.3 cmake==3.27.7

# Try to find pre-built dlib wheel
echo "Attempting to install dlib..."
pip install --no-cache-dir \
    --find-links https://github.com/jloh02/dlib-wheels/raw/master/ \
    dlib==19.24.1 || \
    pip install --no-cache-dir dlib==19.24.1

# Install other dependencies
pip install --no-cache-dir -r requirements.txt

echo "Dependencies installed successfully!"
