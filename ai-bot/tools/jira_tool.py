"""
JIRA Tool - LangChain Tool Definitions
=======================================
Tools:
  - create_jira_ticket        -> creates a new JIRA issue
  - get_open_jira_tickets     -> lists open tickets
  - update_jira_ticket_status -> transitions ticket status
  - add_jira_comment          -> adds comment to a ticket

Credentials from .env:
  JIRA_URL, JIRA_EMAIL, JIRA_API_TOKEN, JIRA_PROJECT_KEY

Standalone test:
  cd ai-bot
  python tools/jira_tool.py
"""

from jira import JIRA
from langchain.tools import tool
from dotenv import load_dotenv
import os

load_dotenv()


def get_jira_client():
    url   = os.environ.get("JIRA_URL")
    email = os.environ.get("JIRA_EMAIL")
    token = os.environ.get("JIRA_API_TOKEN")
    if not all([url, email, token]):
        raise EnvironmentError(
            "Missing JIRA credentials. Set JIRA_URL, JIRA_EMAIL, JIRA_API_TOKEN in .env"
        )
    return JIRA(server=url, basic_auth=(email, token))


@tool
def create_jira_ticket(summary: str, description: str, priority: str = "Medium") -> str:
    """
    Creates a new JIRA ticket in the configured project.

    Args:
        summary: Short title for the ticket (max 100 chars)
        description: Detailed description of the issue
        priority: Highest / High / Medium / Low / Lowest

    Returns:
        Confirmation with ticket key and URL
    """
    jira        = get_jira_client()
    project_key = os.environ.get("JIRA_PROJECT_KEY", "PROJ")

    issue = jira.create_issue(fields={
        "project":     {"key": project_key},
        "summary":     summary[:100],
        "description": description,
        "issuetype":   {"name": "Task"},
        "priority":    {"name": priority},
    })

    url = os.environ["JIRA_URL"] + "/browse/" + issue.key
    return (
        "JIRA ticket created successfully!\n"
        "   Key:      " + issue.key + "\n"
        "   Summary:  " + summary + "\n"
        "   Priority: " + priority + "\n"
        "   URL:      " + url
    )


@tool
def get_open_jira_tickets(max_results: int = 10) -> str:
    """
    Fetches the latest open JIRA tickets from the project.

    Args:
        max_results: Number of tickets to return (default 10, max 50)

    Returns:
        Formatted list of open tickets
    """
    jira        = get_jira_client()
    project_key = os.environ.get("JIRA_PROJECT_KEY", "PROJ")

    # ✅ FIXED: safely cast max_results in case LLM passes a string
    try:
        max_results = min(int(max_results), 50)
    except (TypeError, ValueError):
        max_results = 10

    issues = jira.search_issues(
        "project=" + project_key + " AND status != Done ORDER BY created DESC",
        maxResults=max_results,
    )

    if not issues:
        return "No open tickets in project " + project_key

    lines = ["Open tickets in " + project_key + " (" + str(len(issues)) + " found):\n"]
    for i in issues:
        lines.append("  " + i.key + ": [" + i.fields.priority.name + "] " + i.fields.summary)
    return "\n".join(lines)


@tool
def update_jira_ticket_status(ticket_key: str, status: str) -> str:
    """
    Transitions a JIRA ticket to a new status.

    Args:
        ticket_key: e.g. PROJ-42
        status: e.g. 'In Progress', 'Done', 'To Do'

    Returns:
        Confirmation or available statuses
    """
    jira        = get_jira_client()
    transitions = jira.transitions(ticket_key)
    matched     = [t for t in transitions if status.lower() in t["name"].lower()]

    if not matched:
        available = [t["name"] for t in transitions]
        return (
            "Status '" + status + "' not found for " + ticket_key + ". "
            "Available: " + ", ".join(available)
        )

    jira.transition_issue(ticket_key, matched[0]["id"])
    return "Ticket " + ticket_key + " moved to '" + matched[0]["name"] + "'"


@tool
def add_jira_comment(ticket_key: str, comment: str) -> str:
    """
    Adds a comment to an existing JIRA ticket.

    Args:
        ticket_key: e.g. PROJ-42
        comment: Comment text to add

    Returns:
        Confirmation message
    """
    jira = get_jira_client()
    jira.add_comment(ticket_key, comment)
    return "Comment added to " + ticket_key


# Standalone test
if __name__ == "__main__":
    print("=" * 50)
    print("TESTING JIRA TOOL STANDALONE")
    print("=" * 50)

    print("\n1. Creating ticket...")
    r = create_jira_ticket.run({
        "summary":     "Standalone test ticket from AI Bot",
        "description": "Created by jira_tool.py standalone test. Safe to delete.",
        "priority":    "Low",
    })
    print(r)

    print("\n2. Fetching open tickets...")
    r = get_open_jira_tickets.run({"max_results": 3})
    print(r)