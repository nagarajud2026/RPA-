"""
Jira Tool
=========
Create once, update forever.

- If JIRA_TICKET_KEY is set in .env  → UPDATES that ticket + adds a comment
- If JIRA_TICKET_KEY is NOT set      → CREATES a new ticket and prints the key

Environment Variables Required:
    JIRA_URL          = https://yourcompany.atlassian.net
    JIRA_EMAIL        = your@email.com
    JIRA_API_TOKEN    = your_api_token
    JIRA_PROJECT      = MVP   (optional, default: MVP)
    JIRA_TICKET_KEY   = MVP-1 (optional, set after first run)
"""

import os
import datetime
from jira import JIRA
from langchain.tools import tool


# ═════════════════════════════════════════════════════════════════════════════
# HELPER — AUTO SAVE TICKET KEY TO .env
# ═════════════════════════════════════════════════════════════════════════════

def _save_ticket_key_to_env(ticket_key: str):
    """
    Automatically writes JIRA_TICKET_KEY=<key> into the .env file.
    Searches for .env in ai-bot/ and project root.
    Also sets it in os.environ so current run uses it immediately.
    """
    # Set in current process immediately
    os.environ["JIRA_TICKET_KEY"] = ticket_key

    # Find the .env file location
    _this_dir   = os.path.dirname(os.path.abspath(__file__))   # tools/
    _root_dir   = os.path.dirname(_this_dir)                    # ai-bot/
    _proj_dir   = os.path.dirname(_root_dir)                    # ai-project-aws/

    env_path = None
    for search_dir in [_root_dir, _proj_dir]:
        candidate = os.path.join(search_dir, ".env")
        if os.path.exists(candidate):
            env_path = candidate
            break

    if not env_path:
        print(f"WARNING: .env file not found. Set JIRA_TICKET_KEY={ticket_key} manually.")
        return

    # Read existing .env content
    with open(env_path, "r") as f:
        lines = f.readlines()

    # Check if JIRA_TICKET_KEY already exists → update it; else append
    key_found = False
    new_lines = []
    for line in lines:
        if line.strip().startswith("JIRA_TICKET_KEY"):
            new_lines.append(f"JIRA_TICKET_KEY={ticket_key}\n")
            key_found = True
        else:
            new_lines.append(line)

    if not key_found:
        # Add a blank line before if file doesn't end with one
        if new_lines and not new_lines[-1].endswith("\n"):
            new_lines.append("\n")
        new_lines.append(f"JIRA_TICKET_KEY={ticket_key}\n")

    # Write back
    with open(env_path, "w") as f:
        f.writelines(new_lines)

    print(f"✅ Auto-saved JIRA_TICKET_KEY={ticket_key} to {env_path}")


# ═════════════════════════════════════════════════════════════════════════════
# HELPER — NORMALIZE PRIORITY NAME
# ═════════════════════════════════════════════════════════════════════════════

# Default Jira priority scheme is: Highest, High, Medium, Low, Lowest.
# "Critical" is NOT a default Jira priority -- it only exists if an admin
# added a custom scheme. Map common synonyms onto the defaults so this
# never fails regardless of what an upstream classifier sends.
_PRIORITY_MAP = {
    "critical": "Highest",
    "highest":  "Highest",
    "blocker":  "Highest",
    "urgent":   "Highest",
    "high":     "High",
    "medium":   "Medium",
    "normal":   "Medium",
    "low":      "Low",
    "lowest":   "Lowest",
    "minor":    "Lowest",
}


def normalize_priority(priority: str) -> str:
    """Maps any incoming priority string onto a valid default Jira priority name."""
    return _PRIORITY_MAP.get((priority or "").strip().lower(), "Medium")


# ═════════════════════════════════════════════════════════════════════════════
# JIRA CLIENT
# ═════════════════════════════════════════════════════════════════════════════

def get_jira_client() -> JIRA:
    """Initialize and return an authenticated Jira client."""
    url   = os.environ.get("JIRA_URL")
    email = os.environ.get("JIRA_EMAIL")
    token = os.environ.get("JIRA_API_TOKEN")

    if not all([url, email, token]):
        missing = [k for k, v in {
            "JIRA_URL": url,
            "JIRA_EMAIL": email,
            "JIRA_API_TOKEN": token
        }.items() if not v]
        raise EnvironmentError(f"❌ Missing Jira credentials: {missing}")

    return JIRA(server=url, basic_auth=(email, token))


# ═════════════════════════════════════════════════════════════════════════════
# TOOL 1 — CREATE OR UPDATE TICKET
# ═════════════════════════════════════════════════════════════════════════════

@tool
def create_jira_ticket(summary: str, description: str = "", priority: str = "Medium") -> str:
    """
    Creates a new Jira ticket OR updates the existing one.

    - If JIRA_TICKET_KEY is set in environment → updates that ticket + adds comment.
    - If not set → creates a brand new ticket.

    Args:
        summary     : Title/summary of the ticket
        description : Detailed description
        priority    : Low / Medium / High / Critical
    """
    try:
        jira         = get_jira_client()
        existing_key = os.environ.get("JIRA_TICKET_KEY", "").strip()
        run_time     = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Map incoming priority (e.g. "Critical") onto a valid Jira default
        original_priority = priority
        priority = normalize_priority(priority)
        if original_priority != priority:
            print(f"INFO: Priority '{original_priority}' mapped to Jira default '{priority}'")

        # ── UPDATE existing ticket ────────────────────────────────────────────
        if existing_key:
            issue = jira.issue(existing_key)

            # Update fields
            issue.update(
                summary=summary,
                description=(
                    f"{description}\n\n"
                    f"_Last updated by Robocorp Bot at {run_time}_"
                ),
                priority={"name": priority}
            )

            # Add comment so every run is tracked
            jira.add_comment(
                existing_key,
                (
                    f"🔄 *Robocorp Bot Update*\n\n"
                    f"*Run Time:*    {run_time}\n"
                    f"*Summary:*     {summary}\n"
                    f"*Description:* {description}\n"
                    f"*Priority:*    {priority}"
                )
            )

            print(f"\n✅ Updated existing Jira ticket: {existing_key}")
            return (
                f"✅ Updated existing Jira ticket.\n"
                f"Key: {existing_key}\n"
                f"Summary: {summary}\n"
                f"Priority: {priority}\n"
                f"URL: {os.environ['JIRA_URL']}/browse/{existing_key}"
            )

        # ── CREATE new ticket (first run only) ───────────────────────────────
        else:
            issue = jira.create_issue(
                project=os.environ.get("JIRA_PROJECT", "MVP"),
                summary=summary,
                description=(
                    f"{description}\n\n"
                    f"_Created by Robocorp Bot at {run_time}_"
                ),
                issuetype={"name": "Task"},
                priority={"name": priority}
            )

            # ── Auto-save ticket key to .env file ────────────────────────
            _save_ticket_key_to_env(issue.key)

            print(f"\n{'='*55}")
            print(f"✅ NEW TICKET CREATED: {issue.key}")
            print(f"✅ JIRA_TICKET_KEY={issue.key} auto-saved to .env")
            print(f"   (All future runs will UPDATE this ticket automatically)")
            print(f"{'='*55}\n")

            return (
                f"✅ Created new Jira ticket.\n"
                f"Key: {issue.key}\n"
                f"Summary: {summary}\n"
                f"Priority: {priority}\n"
                f"URL: {os.environ['JIRA_URL']}/browse/{issue.key}"
            )

    except EnvironmentError as e:
        return str(e)
    except Exception as e:
        return f"❌ Jira operation failed: {str(e)}"


# ═════════════════════════════════════════════════════════════════════════════
# TOOL 2 — UPDATE TICKET STATUS
# ═════════════════════════════════════════════════════════════════════════════

@tool
def update_jira_ticket_status(ticket_key: str = "", status: str = "In Progress") -> str:
    """
    Transitions a Jira ticket to a new status.

    Args:
        ticket_key : Jira ticket key e.g. MVP-1 (uses JIRA_TICKET_KEY env var if empty)
        status     : Target status e.g. 'In Progress', 'Done', 'To Do'
    """
    try:
        jira = get_jira_client()
        key  = (ticket_key or os.environ.get("JIRA_TICKET_KEY", "")).strip()

        if not key:
            return "❌ No ticket key provided. Set JIRA_TICKET_KEY in .env or pass ticket_key."

        transitions = jira.transitions(key)
        matched     = next(
            (t for t in transitions if status.lower() in t["name"].lower()),
            None
        )

        if not matched:
            available = [t["name"] for t in transitions]
            return (
                f"❌ Status '{status}' not found on ticket {key}.\n"
                f"Available transitions: {available}"
            )

        jira.transition_issue(key, matched["id"])
        return f"✅ Ticket {key} transitioned to '{matched['name']}'"

    except EnvironmentError as e:
        return str(e)
    except Exception as e:
        return f"❌ Status update failed: {str(e)}"


# ═════════════════════════════════════════════════════════════════════════════
# TOOL 3 — GET OPEN JIRA TICKETS
# ═════════════════════════════════════════════════════════════════════════════

@tool
def get_open_jira_tickets(project_key: str = "") -> str:
    """
    Fetches all open/in-progress tickets from a Jira project.

    Args:
        project_key : Jira project key e.g. GSK (uses JIRA_PROJECT env var if empty)
    """
    try:
        jira    = get_jira_client()
        project = (project_key or os.environ.get("JIRA_PROJECT", "")).strip()

        if not project:
            return "❌ No project key provided. Set JIRA_PROJECT in .env or pass project_key."

        jql    = f'project = {project} AND status in ("To Do", "In Progress") ORDER BY created DESC'
        issues = jira.search_issues(jql, maxResults=20)

        if not issues:
            return f"✅ No open tickets found in project {project}."

        lines = [f"📋 Open tickets in {project} ({len(issues)} found):\n"]
        for issue in issues:
            lines.append(
                f"  [{issue.key}] {issue.fields.summary}\n"
                f"           Status: {issue.fields.status.name} | "
                f"Priority: {issue.fields.priority.name}\n"
                f"           URL: {os.environ.get('JIRA_URL')}/browse/{issue.key}\n"
            )

        return "\n".join(lines)

    except EnvironmentError as e:
        return str(e)
    except Exception as e:
        return f"❌ Failed to fetch open tickets: {str(e)}"


# ═════════════════════════════════════════════════════════════════════════════
# TOOL 4 — GET SINGLE TICKET DETAILS
# ═════════════════════════════════════════════════════════════════════════════

@tool
def get_jira_ticket(ticket_key: str = "") -> str:
    """
    Fetches and returns current details of a Jira ticket.

    Args:
        ticket_key : Jira ticket key e.g. MVP-1 (uses JIRA_TICKET_KEY env var if empty)
    """
    try:
        jira = get_jira_client()
        key  = (ticket_key or os.environ.get("JIRA_TICKET_KEY", "")).strip()

        if not key:
            return "❌ No ticket key provided. Set JIRA_TICKET_KEY in .env or pass ticket_key."

        issue = jira.issue(key)
        return (
            f"📋 Jira Ticket Details\n"
            f"Key         : {issue.key}\n"
            f"Summary     : {issue.fields.summary}\n"
            f"Status      : {issue.fields.status.name}\n"
            f"Priority    : {issue.fields.priority.name}\n"
            f"Assignee    : {getattr(issue.fields.assignee, 'displayName', 'Unassigned')}\n"
            f"Description : {str(issue.fields.description or '')[:200]}\n"
            f"URL         : {os.environ.get('JIRA_URL')}/browse/{key}"
        )

    except EnvironmentError as e:
        return str(e)
    except Exception as e:
        return f"❌ Failed to fetch ticket: {str(e)}"


# ═════════════════════════════════════════════════════════════════════════════
# TOOL 5 — ADD COMMENT TO TICKET
# ═════════════════════════════════════════════════════════════════════════════

@tool
def add_jira_comment(ticket_key: str = "", comment: str = "") -> str:
    """
    Adds a comment to a Jira ticket.

    Args:
        ticket_key : Jira ticket key e.g. GSK-1344 (uses JIRA_TICKET_KEY env var if empty)
        comment    : Text of the comment to add
    """
    try:
        jira = get_jira_client()
        key  = (ticket_key or os.environ.get("JIRA_TICKET_KEY", "")).strip()

        if not key:
            return "❌ No ticket key provided. Set JIRA_TICKET_KEY in .env or pass ticket_key."
        if not comment or not comment.strip():
            return "❌ No comment text provided."

        jira.add_comment(key, comment)
        return f"✅ Comment added to ticket {key}"

    except EnvironmentError as e:
        return str(e)
    except Exception as e:
        return f"❌ Failed to add comment: {str(e)}"