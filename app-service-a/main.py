"""
Service A — Frontend / API Gateway (Pod 1)
==========================================
Port: 8000
- Receives task requests
- Forwards to Service B for processing
- Triggers AI Bot for JIRA + SES email
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import httpx
import os
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(
    title="Service A — API Gateway",
    version="1.0.0",
)

SERVICE_B_URL = os.getenv("SERVICE_B_URL", "http://app-service-b:8001")
AI_BOT_URL    = os.getenv("AI_BOT_URL",    "http://ai-bot:8002")


class TaskRequest(BaseModel):
    task: str
    notify: bool = True


class ProcessRequest(BaseModel):
    data: str


@app.get("/health")
def health_check():
    return {"status": "ok", "service": "service-a"}


@app.get("/")
def root():
    return {
        "service": "Service A — API Gateway",
        "endpoints": [
            "GET  /health",
            "POST /trigger  — send task to AI bot",
            "POST /process  — forward data to Service B",
            "GET  /status   — check all downstream services",
        ]
    }


@app.post("/trigger")
async def trigger_ai_bot(req: TaskRequest):
    """
    Full flow:
    1. Send data to Service B for classification + enrichment
    2. Pass enriched task to AI Bot
    3. AI Bot creates JIRA ticket + sends AWS SES email
    """
    async with httpx.AsyncClient(timeout=60.0) as client:

        # Step 1 — Service B pre-processing
        try:
            b_resp = await client.post(
                f"{SERVICE_B_URL}/process",
                json={"data": req.task},
            )
            b_resp.raise_for_status()
            processed = b_resp.json().get("result", req.task)
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"Service B error: {str(e)}")

        # Step 2 — AI Bot
        agent_task = processed
        if req.notify:
            agent_task += " Also send an email notification to the team."

        try:
            bot_resp = await client.post(
                f"{AI_BOT_URL}/run",
                json={"task": agent_task},
            )
            bot_resp.raise_for_status()
            bot_result = bot_resp.json()
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"AI Bot error: {str(e)}")

    return {
        "status": "success",
        "service_b_output": processed,
        "ai_bot_result":    bot_result.get("result"),
    }


@app.post("/process")
async def forward_to_service_b(req: ProcessRequest):
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            r = await client.post(f"{SERVICE_B_URL}/process", json={"data": req.data})
            r.raise_for_status()
            return r.json()
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"Service B error: {str(e)}")


@app.get("/status")
async def check_status():
    results = {}
    async with httpx.AsyncClient(timeout=5.0) as client:
        for name, url in [("service-b", SERVICE_B_URL), ("ai-bot", AI_BOT_URL)]:
            try:
                r = await client.get(f"{url}/health")
                results[name] = "ok" if r.status_code == 200 else "degraded"
            except Exception:
                results[name] = "unreachable"
    return {"service-a": "ok", **results}
