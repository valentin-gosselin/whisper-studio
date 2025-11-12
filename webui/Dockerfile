FROM python:3.11-slim

# Force Python to output logs immediately (unbuffered)
ENV PYTHONUNBUFFERED=1

# Install ffmpeg for audio conversion
RUN apt-get update && \
    apt-get install -y ffmpeg && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY app.py .
COPY templates ./templates

# Create necessary directories
RUN mkdir -p /tmp/uploads /tmp/outputs

# Expose port
EXPOSE 7860

# Run the application
CMD ["python", "app.py"]
