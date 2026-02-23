FROM python:3.12-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app/ app/

# Create a non-root user and group to run the admin API
RUN groupadd -r appgroup && useradd -r -g appgroup appuser \
    && chown -R appuser:appgroup /app

# Run the service as the non-root user
USER appuser
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "9000"]
