FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY services/kafka_timescale_sink/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy shared models
COPY services/shared/ /app/shared/

# Copy application code
COPY services/kafka_timescale_sink/ .

# Create non-root user for security
RUN useradd --create-home --shell /bin/bash app \
    && chown -R app:app /app
USER app

# Run the application
CMD ["python", "sink.py"]