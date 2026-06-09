"""
AI Bot - LangChain Agent with JIRA + AWS SES
=============================================
Port: 8002

LLM: Groq (free - get key from console.groq.com)

Tools available to the agent:
  JIRA:  create_jira_ticket, get_open_jira_tickets,
         update_jira_ticket_status, add_jira_comment
  Email: send_ses_email, list_ses_identities

Run locally:
  cd ai-bot
  uvicorn main:app --reload --port 8002

Run via Robocorp:
  rcc run --task "Run AI Agent"
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from langchain_groq import ChatGroq
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from dotenv import load_dotenv
import os
import logging

from tools.jira_tool import (
    create_jira_ticket,
    get_open_jira_tickets,
    update_jira_ticket_status,
    add_jira_comment,
)
from tools.email_tool import (
    send_ses_email,
    list_ses_identities,
)

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="AI Bot - LangChain Agent",
    description="LangChain agent with JIRA and AWS SES email tools",
    version="1.0.0",
)


def build_agent() -> AgentExecutor:
    """
    Build and return the LangChain agent.
    Called at FastAPI startup AND by Robocorp tasks after secrets are loaded.
    """
    groq_api_key = os.environ.get("GROQ_API_KEY")
    if not groq_api_key:
        raise EnvironmentError(
            "GROQ_API_KEY not set. "
            "Get free key from: https://console.groq.com"
        )

    llm = ChatGroq(
        model="llama-3.3-70b-versatile",  # ✅ updated from llama3-70b-8192
        temperature=0,
        groq_api_key=groq_api_key,
    )

    tools = [
        create_jira_ticket,
        get_open_jira_tickets,
        update_jira_ticket_status,
        add_jira_comment,
        send_ses_email,
        list_ses_identities,
    ]

    prompt = ChatPromptTemplate.from_messages([
        (
            "system",
            """You are an AI assistant that manages JIRA tickets and sends emails via AWS SES.

When given a task:
1. Understand what action is needed (create ticket, update ticket, send email, or combination).
2. Use the appropriate tool(s) to complete the task.
3. Always confirm what you did with ticket keys and email subjects in your final answer.
4. If creating a ticket AND sending an email, do BOTH.
5. Be concise and factual in your responses.
6. After completing all tool calls, always provide a plain text final answer summarising what was done.

Available tools:
  JIRA:  create_jira_ticket, get_open_jira_tickets, update_jira_ticket_status, add_jira_comment
  Email: send_ses_email, list_ses_identities""",
        ),
        ("human", "{input}"),
        MessagesPlaceholder("agent_scratchpad"),
    ])

    agent = create_tool_calling_agent(llm, tools, prompt)

    return AgentExecutor(
        agent=agent,
        tools=tools,
        verbose=True,
        max_iterations=5,
        handle_parsing_errors="I completed the requested actions. Please check the tool outputs above for details.",
        return_intermediate_steps=True,
    )


# ✅ Build agent at startup ONLY if GROQ_API_KEY is already available
# When running via Robocorp tasks, build_agent() is called directly
# in run_agent.py AFTER secrets are loaded via load_secrets()
agent_executor = None
try:
    if os.environ.get("GROQ_API_KEY"):
        agent_executor = build_agent()
        logger.info("LangChain agent initialised successfully with Groq")
    else:
        logger.warning(
            "GROQ_API_KEY not set at startup - agent not initialised. "
            "Set it in .env for local run or Vault for Control Room."
        )
except Exception as e:
    logger.error("Failed to build agent: " + str(e))
    agent_executor = None


class TaskRequest(BaseModel):
    task: str


class AgentResponse(BaseModel):
    result: str
    status: str


def extract_output(result: dict) -> str:
    """
    Robustly extract final output from agent result.
    Falls back to intermediate step results if output is empty/None.
    """
    output = result.get("output") or ""

    if not output or output.strip() == "":
        steps = result.get("intermediate_steps", [])
        if steps:
            summaries = []
            for action, observation in steps:
                if observation and str(observation).strip():
                    summaries.append(str(observation).strip())
            if summaries:
                output = "Agent completed tasks:\n\n" + "\n\n".join(summaries)

    return output or "Agent completed with no output."


@app.get("/health")
def health_check():
    return {
        "status":      "ok",
        "service":     "ai-bot",
        "llm":         "groq/llama-3.3-70b-versatile",
        "agent_ready": agent_executor is not None,
    }


@app.get("/")
def root():
    return {
        "service": "AI Bot - LangChain Agent (Groq llama-3.3-70b-versatile)",
        "endpoints": [
            "GET  /health",
            "POST /run    - run agent with a task string",
            "GET  /tools  - list available tools",
        ]
    }


@app.get("/tools")
def list_tools():
    if not agent_executor:
        raise HTTPException(status_code=503, detail="Agent not initialised")
    return {
        "tools": [t.name for t in agent_executor.tools],
        "count": len(agent_executor.tools),
    }


@app.post("/run", response_model=AgentResponse)
async def run_agent(req: TaskRequest):
    """
    Run the LangChain agent with a task.

    Example body:
    {
      "task": "Create a JIRA ticket for login bug in Pod1 and email the team."
    }
    """
    if not agent_executor:
        raise HTTPException(
            status_code=503,
            detail="Agent not initialised. Check GROQ_API_KEY in .env"
        )
    if not req.task.strip():
        raise HTTPException(status_code=400, detail="task cannot be empty")

    logger.info("Running agent: " + req.task)

    try:
        result = agent_executor.invoke({"input": req.task})
        output = extract_output(result)
        logger.info("Agent result: " + output)
        return AgentResponse(result=output, status="success")
    except Exception as e:
        logger.error("Agent error: " + str(e))
        raise HTTPException(status_code=500, detail="Agent error: " + str(e))