FROM python:3.12-slim

# Install cron
RUN apt-get update && apt-get install -y --no-install-recommends cron && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy app code
COPY *.py ./

# Copy entrypoint and run scripts
COPY entrypoint.sh run.sh ./
RUN chmod +x entrypoint.sh run.sh

ENTRYPOINT ["/app/entrypoint.sh"]
