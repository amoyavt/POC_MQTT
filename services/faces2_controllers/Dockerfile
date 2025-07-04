FROM ghcr.io/astral-sh/uv:python3.11-bookworm-slim

# Set working directory
WORKDIR /app

# Copy shared models
COPY services/shared/ /app/shared/

# Copy faces2_controllers service files
COPY services/faces2_controllers/requirements.txt /app/requirements.txt
COPY services/faces2_controllers/simulator.py /app/simulator.py

# Install Python dependencies using uv and create certs directory
RUN uv pip install --system --no-cache -r requirements.txt && \
	mkdir -p /app/certs

# Run the simulator
CMD ["python", "simulator.py"]