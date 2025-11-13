FROM python:3.11-slim

# Force Python to output logs immediately (unbuffered)
ENV PYTHONUNBUFFERED=1

# Install ffmpeg and cron for audio conversion and cleanup
RUN apt-get update && \
    apt-get install -y ffmpeg cron && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY app.py .
COPY srt_utils.py .
COPY video_utils.py .
COPY templates ./templates

# Create necessary directories
RUN mkdir -p /tmp/uploads /tmp/outputs

# Setup cron job for automatic cleanup (every hour, removes files older than 1h)
RUN echo "0 * * * * find /tmp/uploads -type f -mmin +60 -delete 2>&1 | logger -t cleanup-uploads" > /etc/cron.d/cleanup && \
    echo "0 * * * * find /tmp/outputs -type f -mmin +60 -delete 2>&1 | logger -t cleanup-outputs" >> /etc/cron.d/cleanup && \
    chmod 0644 /etc/cron.d/cleanup && \
    crontab /etc/cron.d/cleanup

# Expose port
EXPOSE 7860

# Create startup script that runs cron and the app
RUN echo '#!/bin/bash\nservice cron start\npython app.py' > /start.sh && chmod +x /start.sh

# Run the startup script
CMD ["/start.sh"]
