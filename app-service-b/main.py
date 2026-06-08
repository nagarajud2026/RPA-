"""
Service B — Backend / Business Logic (Pod 2)
============================================
Port: 8001
- Classifies incoming request (bug/feature/deploy/test)
- Extracts priority
- Builds clean JIRA-ready summary
- Returns enriched payload to Service A
"""

from fastapi import FastAPI
from pydantic import BaseModel
from dotenv import load_dotenv
import re
from datetime import datetime

load_dotenv()

app = FastAPI(
    title="Service B — Backend Processor",
    version="1.0.0",
)


class ProcessRequest(BaseModel):
    data: str


class ProcessResponse(BaseModel):
    result: str
    enriched: dict
    timestamp: str


def classify_request(text: str) -> str:
    t = text.lower()
    if any(w in t for w in ["bug", "error", "crash", "fail", "broken", "issue"]):
        return "BUG_REPORT"
    if any(w in t for w in ["feature", "request", "add", "new", "enhance", "improve"]):
        return "FEATURE_REQUEST"
    if any(w in t for w in ["deploy", "release", "ship", "launch", "push"]):
        return "DEPLOYMENT"
    if any(w in t for w in ["test", "qa", "check", "verify", "validate"]):
        return "TEST_TASK"
    return "GENERAL_TASK"


def extract_priority(text: str) -> str:
    t = text.lower()
    if any(w in t for w in ["critical", "urgent", "asap", "blocker", "p0"]):
        return "Critical"
    if any(w in t for w in ["high", "important", "p1"]):
        return "High"
    if any(w in t for w in ["low", "minor", "p3", "someday"]):
        return "Low"
    return "Medium"


def build_jira_summary(text: str, category: str) -> str:
    prefix_map = {
        "BUG_REPORT":      "[BUG]",
        "FEATURE_REQUEST": "[FEATURE]",
        "DEPLOYMENT":      "[DEPLOY]",
        "TEST_TASK":       "[TEST]",
        "GENERAL_TASK":    "[TASK]",
    }
    clean = re.sub(r'\s+', ' ', text).strip()
    return f"{prefix_map.get(category, '[TASK]')} {clean}"[:100]


@app.get("/health")
def health_check():
    return {"status": "ok", "service": "service-b"}


@app.get("/")
def root():
    return {"service": "Service B — Backend Processor"}


@app.post("/process", response_model=ProcessResponse)
def process_data(req: ProcessRequest):
    category     = classify_request(req.data)
    priority     = extract_priority(req.data)
    jira_summary = build_jira_summary(req.data, category)

    enriched = {
        "original_input": req.data,
        "category":       category,
        "priority":       priority,
        "jira_summary":   jira_summary,
        "source_service": "service-b",
    }

    result = (
        f"Create a JIRA ticket with summary: '{jira_summary}', "
        f"priority: {priority}, category: {category}. "
        f"Description: {req.data}"
    )

    return ProcessResponse(
        result=result,
        enriched=enriched,
        timestamp=datetime.utcnow().isoformat() + "Z",
    )
