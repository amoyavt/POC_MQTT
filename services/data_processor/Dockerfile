FROM python:3.11-slim

WORKDIR /app

# Copy shared models first
COPY shared /app/shared

# Install shared dependencies
RUN pip install --no-cache-dir -r /app/shared/requirements.txt

# Copy service requirements and install
COPY services/data_processor/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy service code
COPY services/data_processor/ .

CMD ["python", "processor.py"]