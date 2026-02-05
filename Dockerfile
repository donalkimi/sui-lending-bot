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

# Install npm packages for each protocol that needs them
# Check if package.json exists before running npm install
RUN if [ -f data/alphalend/package.json ]; then cd data/alphalend && npm install; fi
RUN if [ -f data/suilend/package.json ]; then cd data/suilend && npm install; fi
RUN if [ -f data/scallop_shared/package.json ]; then cd data/scallop_shared && npm install; fi
RUN if [ -f data/navi/package.json ]; then cd data/navi && npm install; fi
RUN if [ -f data/pebble/package.json ]; then cd data/pebble && npm install; fi

# Also install from root if package.json exists there
RUN if [ -f package.json ]; then npm install; fi

# Default command (Railway cron will override this)
CMD ["python", "main.py"]