# Uses the official Playwright Python image — Chromium and all system
# libraries are pre-installed, so no "executable not found" errors.
FROM mcr.microsoft.com/playwright/python:v1.40.0-jammy

WORKDIR /app

# Install Python dependencies first (layer cache)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

EXPOSE 8080

# Single worker (shared in-memory job state) + 4 threads (serve /status polls
# while the background pipeline thread runs) + 300s timeout (pipeline takes 2-5 min)
CMD ["gunicorn", "server:app", \
     "--workers=1", "--threads=4", "--timeout=300", \
     "--bind=0.0.0.0:8080", \
     "--access-logfile=-", "--error-logfile=-"]
