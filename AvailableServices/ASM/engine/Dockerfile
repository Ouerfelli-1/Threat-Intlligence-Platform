FROM python:3.11-slim

WORKDIR /app

# Install system dependencies including nmap for active scanning
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    libpq-dev \
    git \
    nmap \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy modules (recon engine code)
COPY modules/ ./modules/
COPY worker.py .
COPY config.ini .

# Create directories
RUN mkdir -p /app/results /app/wordlists

# Run worker
CMD ["python", "worker.py"]
