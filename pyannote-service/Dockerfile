FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Install Python dependencies
RUN pip install --no-cache-dir \
    pyannote.audio==3.3.1 \
    flask==3.0.0 \
    torch==2.5.1 \
    torchaudio==2.5.1 \
    gunicorn==21.2.0

# Copy application files
COPY app.py /app/

# Expose port
EXPOSE 8001

# Run with gunicorn for production
CMD ["gunicorn", "--bind", "0.0.0.0:8001", "--timeout", "300", "--workers", "1", "app:app"]
