FROM python:3.11-slim

WORKDIR /code
COPY . /code

RUN apt-get update && apt-get install -y \
    gcc g++ curl libpq-dev cmake libopenblas-dev liblapack-dev \
    libx11-dev libgtk-3-dev && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir -r requirements.txt

EXPOSE 8000

CMD ["python", "app/main.py"]
