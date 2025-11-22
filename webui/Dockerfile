FROM python:3.11-slim

# Force Python to output logs immediately (unbuffered)
ENV PYTHONUNBUFFERED=1

# Install ffmpeg, cron, postgresql-client, and WeasyPrint dependencies
RUN apt-get update && \
    apt-get install -y ffmpeg cron postgresql-client \
    # WeasyPrint dependencies
    libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz-subset0 \
    libffi-dev libcairo2 libgdk-pixbuf-2.0-0 shared-mime-info && \
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
COPY library_routes.py .
COPY rgpd_routes.py .
COPY email_utils.py .
COPY init_db.py .
COPY cleanup_cron.py .
COPY inactivity_cleanup.py .
COPY create_test_inactive_user.py .
COPY file_security.py .
COPY migrate_user_folders.py .
COPY migrate_inactivity.py .
COPY rgpd_templates.py .
COPY migrate_rgpd.py .
COPY update_legal_texts.py .
COPY templates ./templates
COPY static ./static

# Create necessary directories
RUN mkdir -p /tmp/uploads /tmp/outputs /tmp/flask_sessions

# Setup cron jobs
# 1. Cleanup cron: Runs every hour, removes uploads after 1h, outputs after 24h (but protects library files)
# 2. Inactivity cron: Runs daily at 3 AM, checks for inactive users (RGPD compliance)
RUN chmod +x /app/cleanup_cron.py && \
    chmod +x /app/inactivity_cleanup.py && \
    echo "0 * * * * cd /app && /usr/local/bin/python /app/cleanup_cron.py >> /var/log/cron.log 2>&1" > /etc/cron.d/cleanup && \
    echo "0 3 * * * cd /app && /usr/local/bin/python /app/inactivity_cleanup.py >> /var/log/inactivity.log 2>&1" >> /etc/cron.d/cleanup && \
    chmod 0644 /etc/cron.d/cleanup && \
    crontab /etc/cron.d/cleanup

# Expose port
EXPOSE 7860

# Create startup script that runs DB init, migrations, cron, and the app
RUN echo '#!/bin/bash\n\
# Wait for PostgreSQL to be ready\n\
echo "Waiting for PostgreSQL..."\n\
while ! pg_isready -h postgres -U whisper 2>/dev/null; do\n\
  sleep 1\n\
done\n\
echo "PostgreSQL is ready!"\n\
\n\
# Initialize database (creates tables)\n\
python init_db.py\n\
\n\
# Run RGPD migrations (add new columns)\n\
python migrate_rgpd.py\n\
\n\
# Run inactivity migration (add deletion_notified_at column)\n\
python migrate_inactivity.py\n\
\n\
# Update legal texts from templates\n\
python update_legal_texts.py\n\
\n\
# Start cron\n\
service cron start\n\
\n\
# Start application\n\
python app.py' > /start.sh && chmod +x /start.sh

# Run the startup script
CMD ["/start.sh"]
