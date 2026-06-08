FROM python:3.11-slim
WORKDIR /app
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .

# ✅ Heavy packages first (largest downloads) so Docker cache saves progress
# If any package times out, next build resumes from that package only
RUN pip install --no-cache-dir --timeout=300 --retries=10 \
    boto3==1.34.144

RUN pip install --no-cache-dir --timeout=300 --retries=10 \
    langchain==0.3.25 \
    langchain-groq==0.2.4 \
    langchain-community==0.3.24 \
    langchain-core==0.3.59

RUN pip install --no-cache-dir --timeout=300 --retries=10 \
    jira==3.8.0

RUN pip install --no-cache-dir --timeout=300 --retries=10 \
    fastapi==0.111.1 \
    uvicorn==0.30.1 \
    python-dotenv==1.0.1 \
    requests==2.32.3 \
    pydantic==2.8.2

RUN pip install --no-cache-dir --timeout=300 --retries=10 \
    robocorp==1.4.3 \
    robocorp-tasks==2.9.3

COPY . .
EXPOSE 8002
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8002"]