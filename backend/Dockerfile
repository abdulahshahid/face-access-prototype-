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

# Install dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir numpy==1.24.3 && \
    pip install --no-cache-dir -r requirements.txt

# --- CHANGED HERE ---
# Copy the entire backend directory, not just ./app contents
COPY . .

# Set PYTHONPATH to include the root /app so imports work correctly
ENV PYTHONPATH=/app:$PYTHONPATH

# Non-root user setup
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

# --- CHANGED HERE ---
# Point to the file inside the app directory
CMD ["python", "app/main.py"]
