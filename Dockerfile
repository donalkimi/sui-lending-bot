# Dockerfile for Sui Lending Bot on Railway
# Includes both Python and Node.js for protocol SDK support

FROM python:3.11-slim

# Install Node.js and npm
RUN apt-get update && \
    apt-get install -y nodejs npm curl && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Verify installations
RUN python --version && node --version && npm --version

# Set working directory
WORKDIR /app

# Copy requirements first for Docker layer caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy entire application
COPY . .

# Default command (Railway cron will override this)
CMD ["python", "main.py"]