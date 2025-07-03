FROM python:3.11-slim

# Create non-root user
RUN groupadd -r iotuser && useradd -r -g iotuser iotuser

# Set up application directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Copy requirements first for better layer caching
COPY services/kafka_timescale_sink/requirements.txt /app/requirements.txt
COPY services/shared/requirements.txt /app/shared_requirements.txt

# Install Python dependencies with uv
RUN pip install uv && \
    uv pip install --system --no-cache -r requirements.txt -r shared_requirements.txt

# Copy application code
COPY services/kafka_timescale_sink/ /app/
COPY services/shared/ /app/shared/

# Create logs directory
RUN mkdir -p /app/logs && chown -R iotuser:iotuser /app

# Switch to non-root user
USER iotuser

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD python -c "import sys; sys.path.append('/app/shared'); from models import IotMeasurement; exit(0)" || exit 1

# Run the application
CMD ["python", "sink.py"]