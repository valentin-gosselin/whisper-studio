FROM python:3.11-slim

# Force Python to output logs immediately (unbuffered)
ENV PYTHONUNBUFFERED=1

# Install ffmpeg, cron, and postgresql-client
RUN apt-get update && \
    apt-get install -y ffmpeg cron postgresql-client && \
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
COPY ollama_client.py .
COPY docx_generator.py .
COPY prompts.py .
COPY models.py .
COPY database.py .
COPY auth.py .
COPY auth_routes.py .
COPY admin_routes.py .
COPY email_utils.py .
COPY init_db.py .
COPY templates ./templates
COPY static ./static

# Create necessary directories
RUN mkdir -p /tmp/uploads /tmp/outputs /tmp/flask_sessions

# Setup cron job for automatic cleanup (every hour, removes files older than 1h)
RUN echo "0 * * * * find /tmp/uploads -type f -mmin +60 -delete 2>&1 | logger -t cleanup-uploads" > /etc/cron.d/cleanup && \
    echo "0 * * * * find /tmp/outputs -type f -mmin +60 -delete 2>&1 | logger -t cleanup-outputs" >> /etc/cron.d/cleanup && \
    chmod 0644 /etc/cron.d/cleanup && \
    crontab /etc/cron.d/cleanup

# Expose port
EXPOSE 7860

# Create startup script that runs DB init, cron, and the app
RUN echo '#!/bin/bash\n\
# Wait for PostgreSQL to be ready\n\
echo "Waiting for PostgreSQL..."\n\
while ! pg_isready -h postgres -U whisper 2>/dev/null; do\n\
  sleep 1\n\
done\n\
echo "PostgreSQL is ready!"\n\
\n\
# Initialize database\n\
python init_db.py\n\
\n\
# Start cron\n\
service cron start\n\
\n\
# Start application\n\
python app.py' > /start.sh && chmod +x /start.sh

# Run the startup script
CMD ["/start.sh"]
