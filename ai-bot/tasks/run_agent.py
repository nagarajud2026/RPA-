"""
Robocorp Task Runner
====================
Entry point when Robocorp Control Room runs the robot.

4 tasks:
  1. run_ai_agent    -- full agent run (JIRA update + email via LLM)
  2. test_jira_only  -- smoke test: update/create JIRA ticket only
  3. test_email_only -- smoke test: AWS SES email only
  4. test_full_flow  -- smoke test: JIRA + SES together (no LLM)

Important:
  - First run (no JIRA_TICKET_KEY in .env) → CREATES a new ticket
  - After first run → add JIRA_TICKET_KEY=MVP-1 to .env
  - All future runs → UPDATES that same ticket, never creates new ones

Folder structure:
  ai-project-aws/
  └── ai-bot/
      ├── tasks/
      │   └── run_agent.py     <- THIS FILE
      ├── tools/
      │   ├── jira_tool.py
      │   └── email_tool.py
      ├── main.py
      ├── .env
      ├── robot.yaml
      └── conda.yaml
"""

import sys
import os
import datetime

# -- Make sure ai-bot/ root is in Python path ---------------------------------
_TASKS_DIR  = os.path.dirname(os.path.abspath(__file__))   # ai-bot/tasks/
ROOT_DIR    = os.path.dirname(_TASKS_DIR)                  # ai-bot/
PROJECT_DIR = os.path.dirname(ROOT_DIR)                    # ai-project-aws/

sys.path.insert(0, ROOT_DIR)

from robocorp.tasks import task
from dotenv import load_dotenv



# =============================================================================
# HELPERS
# =============================================================================

def load_secrets():
    """
    Load secrets in priority order:
      1. Robocorp Vault        (Control Room with Vault configured)
      2. Environment Variables (Control Room Process -> Configure -> Env Vars)
      3. .env file in ai-bot/  (local development)
      4. .env file in project root (fallback)
    """

    # Way 1: Robocorp Vault
    try:
        from robocorp import vault

        def load_secrets():

        secret = vault.get_secret("aibotsecrets")

        return secret
    
        secrets = vault.get_secret("aibotsecrets")
        for key, value in secrets.items():
            os.environ[key] = str(value)
        print("INFO: Secrets loaded from Robocorp Vault")
        return
    except Exception as e:
        print(f"INFO: Vault not available -> {e}")

    # Way 2: Control Room Environment Variables
    required_keys = [
        "JIRA_URL", "JIRA_EMAIL", "JIRA_API_TOKEN",
        "AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY",
        "SES_SENDER_EMAIL", "SES_RECIPIENT_EMAIL"
    ]
    keys_present = [k for k in required_keys if os.environ.get(k)]
    if len(keys_present) >= 4:
        print(f"INFO: Secrets loaded from Environment Variables "
              f"({len(keys_present)}/{len(required_keys)} keys found)")
        return

    # Way 3 & 4: .env file -- check ai-bot/ then project root
    for search_dir in [ROOT_DIR, PROJECT_DIR]:
        env_path = os.path.join(search_dir, ".env")
        if os.path.exists(env_path):
            load_dotenv(dotenv_path=env_path, override=True)
            if os.environ.get("JIRA_URL"):
                print(f"INFO: Secrets loaded from .env -> {env_path}")
                return

    # Nothing worked
    print("ERROR: No credentials found in Vault, Env Vars, or .env file")
    print(f"ERROR: Checked .env in: {ROOT_DIR}")
    print(f"ERROR: Checked .env in: {PROJECT_DIR}")
    print("ERROR: Add credentials to ai-bot/.env for local development")
    raise EnvironmentError("Missing credentials. Cannot proceed.")


def extract_output(result: dict) -> str:
    """Robustly extract final output from LangChain agent result."""
    output = (result.get("output") or "").strip()
    if not output:
        steps = result.get("intermediate_steps", [])
        summaries = [
            str(observation).strip()
            for _, observation in steps
            if observation and str(observation).strip()
        ]
        if summaries:
            output = "Agent completed tasks:\n\n" + "\n\n".join(summaries)
    return output or "Agent completed with no output."


def print_section(title: str, width: int = 60):
    print("\n" + "=" * width)
    print(title)
    print("=" * width + "\n")


def now() -> str:
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# =============================================================================
# TASK 1 -- FULL AI AGENT (LLM + JIRA UPDATE + SES EMAIL)
# =============================================================================

@task
def run_ai_agent():
    """
    Main task: Runs the full LangChain agent.
    Updates the existing JIRA ticket + sends a confirmation email via AWS SES.
    """
    load_secrets()

    from main import build_agent

    ticket_key = os.environ.get("JIRA_TICKET_KEY", "the existing ticket")
    run_time   = now()

    agent_task = os.environ.get(
        "AGENT_TASK",
        (
            f"Update the JIRA ticket {ticket_key} with summary "
            f"'Robocorp AI Bot Run -- {run_time}' "
            f"and description 'This ticket was updated automatically by the "
            f"Robocorp AI Bot. Run time: {run_time}.' "
            f"priority Medium. "
            f"Then send an email with subject "
            f"'AI Bot: Ticket {ticket_key} Updated -- {run_time}' "
            f"and body confirming the ticket was updated successfully."
        ),
    )

    print_section("AGENT TASK")
    print(agent_task)

    try:
        agent_executor = build_agent()
        result         = agent_executor.invoke({"input": agent_task})
        output         = extract_output(result)
    except Exception as e:
        print(f"ERROR: Agent failed -> {e}")
        raise

    print_section("AGENT RESULT")
    print(output)
    return output


# =============================================================================
# TASK 2 -- SMOKE TEST: JIRA ONLY
# =============================================================================

@task
def test_jira_only():
    """
    Smoke test: Directly creates/updates a JIRA ticket -- no LLM involved.
    First run  -> creates a new ticket, prints key -> add to .env as JIRA_TICKET_KEY
    Later runs -> updates the same ticket
    """
    load_secrets()

    from tools.jira_tool import create_jira_ticket

    ticket_key = os.environ.get("JIRA_TICKET_KEY", "NOT SET -- will create new")

    print_section(f"SMOKE TEST -- JIRA ONLY | Ticket: {ticket_key}", 55)

    print("Credential check:")
    print(f"  JIRA_URL        : {'SET' if os.environ.get('JIRA_URL')        else 'MISSING'}")
    print(f"  JIRA_EMAIL      : {'SET' if os.environ.get('JIRA_EMAIL')      else 'MISSING'}")
    print(f"  JIRA_API_TOKEN  : {'SET' if os.environ.get('JIRA_API_TOKEN')  else 'MISSING'}")
    print(f"  JIRA_TICKET_KEY : {ticket_key}")

    missing = [k for k in ["JIRA_URL", "JIRA_EMAIL", "JIRA_API_TOKEN"]
               if not os.environ.get(k)]
    if missing:
        raise EnvironmentError(f"Missing JIRA credentials: {missing}")

    print(f"\nRunning at: {now()}")
    print("Calling Jira tool...\n")

    result = create_jira_ticket.run({
        "summary":     f"Robocorp Smoke Test -- {now()}",
        "description": f"Smoke test run at {now()}. Safe to delete if this is a new ticket.",
        "priority":    "Low",
    })
    print(result)

    if "Key:" in result or "created" in result.lower() or "updated" in result.lower():
        print(f"\nPASSED -- Jira is working correctly")
        if not os.environ.get("JIRA_TICKET_KEY"):
            print("ACTION REQUIRED: Copy the ticket Key above and add to ai-bot/.env:")
            print("   JIRA_TICKET_KEY=<KEY FROM ABOVE>")
    else:
        print(f"\nFAILED -- Check JIRA credentials")
        raise RuntimeError(f"Jira smoke test failed: {result}")


# =============================================================================
# TASK 3 -- SMOKE TEST: AWS SES EMAIL ONLY
# =============================================================================

@task
def test_email_only():
    """
    Smoke test: Sends a test email via AWS SES -- no LLM involved.
    """
    load_secrets()

    from tools.email_tool import send_ses_email, list_ses_identities

    ticket_key = os.environ.get("JIRA_TICKET_KEY", "N/A")

    print_section("SMOKE TEST -- AWS SES EMAIL ONLY", 55)

    print("Credential check:")
    print(f"  AWS_ACCESS_KEY_ID     : {'SET' if os.environ.get('AWS_ACCESS_KEY_ID')     else 'MISSING'}")
    print(f"  AWS_SECRET_ACCESS_KEY : {'SET' if os.environ.get('AWS_SECRET_ACCESS_KEY') else 'MISSING'}")
    print(f"  AWS_REGION            : {'SET' if os.environ.get('AWS_REGION')            else 'MISSING'}")
    print(f"  SES_SENDER_EMAIL      : {'SET' if os.environ.get('SES_SENDER_EMAIL')      else 'MISSING'}")
    print(f"  SES_RECIPIENT_EMAIL   : {'SET' if os.environ.get('SES_RECIPIENT_EMAIL')   else 'MISSING'}")

    missing = [k for k in ["AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY",
                            "SES_SENDER_EMAIL", "SES_RECIPIENT_EMAIL"]
               if not os.environ.get(k)]
    if missing:
        raise EnvironmentError(f"Missing AWS/SES credentials: {missing}")

    print("\nStep 1: Listing verified SES identities...")
    try:
        identities = list_ses_identities.run({})
        print(identities)
    except Exception as e:
        print(f"WARNING: Could not list SES identities -> {e}")

    print("\nStep 2: Sending test email...")
    result = send_ses_email.run({
        "subject": f"Robocorp Smoke Test -- AWS SES Email | {now()}",
        "body": (
            f"AWS SES smoke test email from Robocorp Bot.\n\n"
            f"Run Time  : {now()}\n"
            f"Ticket    : {ticket_key}\n"
            f"Sender    : {os.environ.get('SES_SENDER_EMAIL', 'N/A')}\n"
            f"Recipient : {os.environ.get('SES_RECIPIENT_EMAIL', 'N/A')}\n"
            f"Region    : {os.environ.get('AWS_REGION', 'N/A')}\n\n"
            f"AWS SES integration is working correctly."
        ),
    })
    print(result)

    if "Message ID" in result:
        print(f"\nPASSED -- AWS SES email sent successfully")
    else:
        print(f"\nFAILED -- Check AWS credentials and SES verified identities")
        raise RuntimeError(f"AWS SES smoke test failed: {result}")


# =============================================================================
# TASK 4 -- FULL FLOW SMOKE TEST (JIRA UPDATE + SES EMAIL, NO LLM)
# =============================================================================

@task
def test_full_flow():
    """
    Full smoke test: Updates JIRA ticket + sends confirmation email.
    No LLM -- validates both integrations work together end-to-end.
    """
    load_secrets()

    from tools.jira_tool import create_jira_ticket
    from tools.email_tool import send_ses_email

    ticket_key = os.environ.get("JIRA_TICKET_KEY", "")
    run_time   = now()

    print_section(f"FULL FLOW TEST -- JIRA + AWS SES | Ticket: {ticket_key or 'NEW'}")

    # Step 1: JIRA
    print(f"[1/2] {'Updating' if ticket_key else 'Creating'} JIRA ticket...")
    try:
        jira_result = create_jira_ticket.run({
            "summary":     f"Robocorp Full Flow Test -- {run_time}",
            "description": f"End-to-end test run at {run_time}.",
            "priority":    "Low",
        })
        print(jira_result)
        jira_ok = any(w in jira_result.lower() for w in ["key:", "created", "updated"])
    except Exception as e:
        jira_result = f"Exception: {e}"
        jira_ok     = False
        print(f"ERROR: JIRA step failed -> {e}")

    # Step 2: Email
    print(f"\n[2/2] Sending confirmation email via AWS SES...")
    try:
        email_result = send_ses_email.run({
            "subject": f"Robocorp Full Flow Test -- Ticket {ticket_key or 'Created'} | {run_time}",
            "body": (
                f"Full flow smoke test completed.\n\n"
                f"Run Time : {run_time}\n"
                f"Ticket   : {ticket_key or 'Newly created -- check JIRA result below'}\n\n"
                f"JIRA Result:\n{jira_result}\n\n"
                f"Both JIRA and AWS SES are working correctly."
            ),
        })
        print(email_result)
        email_ok = "Message ID" in email_result
    except Exception as e:
        email_result = f"Exception: {e}"
        email_ok     = False
        print(f"ERROR: Email step failed -> {e}")

    # Summary
    print_section("RESULTS")
    print(f"  JIRA    : {'PASSED' if jira_ok  else 'FAILED'}")
    print(f"  AWS SES : {'PASSED' if email_ok else 'FAILED'}")

    if not ticket_key and jira_ok:
        print(f"\nACTION REQUIRED: Add the new ticket key to ai-bot/.env:")
        print(f"   JIRA_TICKET_KEY=<KEY FROM JIRA RESULT ABOVE>")

    if not jira_ok or not email_ok:
        raise RuntimeError(
            f"One or more tests FAILED.\n"
            f"  JIRA  : {jira_result}\n"
            f"  Email : {email_result}"
        )

    print(f"\nALL TESTS PASSED!")