FROM python:3.11-slim

# Create non-root user
RUN groupadd -r iotuser && useradd -r -g iotuser iotuser

# Set up application directory
WORKDIR /app

# Install system dependencies for snappy compression
RUN apt-get update && apt-get install -y \
    build-essential \
    libsnappy-dev \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Copy requirements first for better layer caching
COPY requirements.txt /app/requirements.txt

# Install Python dependencies with uv
RUN pip install uv && \
    uv pip install --system --no-cache -r requirements.txt

# Copy application code
COPY . /app/

# Create logs directory
RUN mkdir -p /app/logs && chown -R iotuser:iotuser /app

# Switch to non-root user
USER iotuser

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD python -c "import paho.mqtt.client as mqtt; exit(0)" || exit 1

# Run the application
CMD ["python", "connector.py"]