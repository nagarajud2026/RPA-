FROM python:3.11-slim
WORKDIR /app
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .

# ✅ Individual installs with timeout+retry for slow/corporate networks
RUN pip install --no-cache-dir --timeout=300 --retries=10 \
    fastapi==0.111.1 \
    uvicorn==0.30.1 \
    httpx==0.27.0 \
    python-dotenv==1.0.1 \
    pydantic==2.8.2

COPY . .
EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]