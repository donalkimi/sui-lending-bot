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

# Install npm packages in subdirectories (separate RUN for each for better caching)
RUN if [ -f data/alphalend/package.json ]; then cd data/alphalend && npm install; fi
RUN if [ -f data/suilend/package.json ]; then cd data/suilend && npm install; fi
RUN if [ -f data/scallop_shared/package.json ]; then cd data/scallop_shared && npm install; fi
RUN if [ -f data/navi/package.json ]; then cd data/navi && npm install; fi
RUN if [ -f data/pebble/package.json ]; then cd data/pebble && npm install; fi
RUN if [ -f package.json ]; then npm install; fi

# Set NODE_PATH to include all subdirectory node_modules
# This tells Node.js where to find packages when scripts are called from Python
ENV NODE_PATH=/app/data/alphalend/node_modules:/app/data/suilend/node_modules:/app/data/scallop_shared/node_modules:/app/data/navi/node_modules:/app/data/pebble/node_modules:/app/node_modules

# Verify node_modules directories exist and show their locations
RUN echo "=== Verifying node_modules directories ===" && \
    find /app/data -name "node_modules" -type d && \
    echo "=== NODE_PATH set to: ===" && \
    echo $NODE_PATH

# Default command (Railway cron will override this)
CMD ["python", "main.py"]