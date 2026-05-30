# Start from the official Playwright image matching your python version
FROM mcr.microsoft.com/playwright/python:v1.44.0-jammy

WORKDIR /app

# Install Python dependencies with a strict timeout bypass
COPY requirements.txt .
RUN pip install --no-cache-dir --default-timeout=1000 --retries=10 -r requirements.txt

# Copy source code (this will now be instant thanks to .dockerignore)
COPY . .

# Output volume for CSV exports
RUN mkdir -p /app/output

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]