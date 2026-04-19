FROM python:3.11-slim

WORKDIR /app

# System dependencies required by your OCR stack
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    libtesseract-dev \
    libleptonica-dev \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    && rm -rf /var/lib/apt/lists/*

# Install python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy app
COPY . .

# Render provides PORT
ENV PORT=10000

# Change app.main:app to your actual FastAPI import path
CMD ["sh", "-c", "gunicorn -k uvicorn.workers.UvicornWorker app.main:app --bind 0.0.0.0:$PORT"]