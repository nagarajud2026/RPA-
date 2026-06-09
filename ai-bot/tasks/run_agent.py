"""
Robocorp Task Runner
====================
Entry point when Robocorp Control Room runs the robot.

4 tasks:
  1. run_ai_agent      -- full agent run (JIRA + email via LLM)
  2. test_jira_only    -- smoke test JIRA credentials only
  3. test_email_only   -- smoke test AWS SES credentials only
  4. test_full_flow    -- smoke test JIRA + SES together (no LLM)
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from robocorp.tasks import task
from dotenv import load_dotenv


def load_secrets():
    """
    Load secrets from Robocorp Vault if running in Control Room,
    fallback to .env file for local development.
    """
    try:
        from robocorp import vault
        secrets = vault.get_secret("ai-bot-secrets")
        for key, value in secrets.items():
            os.environ[key] = str(value)
        print("INFO: Secrets loaded from Robocorp Vault")
        return
    except Exception as e:
        print("INFO: Vault not available (expected locally): " + str(e))

    # Fallback to .env for local development
    load_dotenv()
    print("INFO: Secrets loaded from .env file")


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


@task
def run_ai_agent():
    """
    Main Robocorp task.
    Runs the full LangChain agent -- creates JIRA ticket + sends email.
    """
    load_secrets()

    from main import build_agent

    agent_task = os.environ.get(
        "AGENT_TASK",
        "Create a JIRA ticket titled 'Automated Task from Robocorp AI Bot' "
        "with description 'This ticket was created automatically by the AI Bot running in Robocorp.' "
        "priority Medium. Then send an email with subject "
        "'AI Bot: New JIRA Ticket Created' confirming the ticket was created.",
    )

    print("\n" + "=" * 60)
    print("AGENT TASK:")
    print(agent_task)
    print("=" * 60 + "\n")

    agent_executor = build_agent()
    result = agent_executor.invoke({"input": agent_task})
    output = extract_output(result)

    print("\n" + "=" * 60)
    print("AGENT RESULT:")
    print(output)
    print("=" * 60 + "\n")

    return output


@task
def test_jira_only():
    """
    Smoke test: directly creates a JIRA ticket without LLM.
    """
    load_secrets()

    from tools.jira_tool import create_jira_ticket

    print("\n" + "=" * 50)
    print("SMOKE TEST - JIRA")
    print("=" * 50)

    print("JIRA_URL set:       " + ("YES" if os.environ.get("JIRA_URL") else "NO"))
    print("JIRA_EMAIL set:     " + ("YES" if os.environ.get("JIRA_EMAIL") else "NO"))
    print("JIRA_API_TOKEN set: " + ("YES" if os.environ.get("JIRA_API_TOKEN") else "NO"))

    result = create_jira_ticket.run({
        "summary":     "Robocorp Control Room Smoke Test - JIRA",
        "description": "Auto-created by Robocorp Control Room smoke test. Safe to delete.",
        "priority":    "Low",
    })
    print(result)

    if "Key:" in result or "created" in result.lower():
        print("\nPASSED - JIRA credentials are correct")
    else:
        print("\nFAILED - check credentials in Control Room Vault")
        raise RuntimeError("JIRA smoke test failed: " + result)


@task
def test_email_only():
    """
    Smoke test: directly sends an email via AWS SES without LLM.
    """
    load_secrets()

    from tools.email_tool import send_ses_email, list_ses_identities

    print("\n" + "=" * 50)
    print("SMOKE TEST - AWS SES EMAIL")
    print("=" * 50)

    print("AWS_ACCESS_KEY_ID set:     " + ("YES" if os.environ.get("AWS_ACCESS_KEY_ID") else "NO"))
    print("AWS_SECRET_ACCESS_KEY set: " + ("YES" if os.environ.get("AWS_SECRET_ACCESS_KEY") else "NO"))
    print("AWS_REGION set:            " + ("YES" if os.environ.get("AWS_REGION") else "NO"))
    print("SES_SENDER_EMAIL set:      " + ("YES" if os.environ.get("SES_SENDER_EMAIL") else "NO"))
    print("SES_RECIPIENT_EMAIL set:   " + ("YES" if os.environ.get("SES_RECIPIENT_EMAIL") else "NO"))

    print("\nStep 1: Checking verified SES identities...")
    identities = list_ses_identities.run({})
    print(identities)

    print("\nStep 2: Sending test email...")
    result = send_ses_email.run({
        "subject": "Robocorp Control Room Smoke Test - AWS SES",
        "body":    (
            "This is a smoke test email from Robocorp Control Room.\n\n"
            "AWS SES integration is working correctly.\n"
            "Sent from: Robocorp Cloud Worker"
        ),
    })
    print(result)

    if "Message ID" in result:
        print("\nPASSED - AWS SES email sent successfully")
    else:
        print("\nFAILED - check AWS credentials in Control Room Vault")
        raise RuntimeError("AWS SES smoke test failed: " + result)


@task
def test_full_flow():
    """
    Full smoke test: creates JIRA ticket + sends email -- no LLM.
    """
    load_secrets()

    from tools.jira_tool import create_jira_ticket
    from tools.email_tool import send_ses_email

    print("\n" + "=" * 60)
    print("FULL FLOW SMOKE TEST - JIRA + AWS SES")
    print("=" * 60)

    print("\n[1/2] Creating JIRA ticket...")
    jira_result = create_jira_ticket.run({
        "summary":     "Robocorp Control Room - Full Flow Test",
        "description": "End-to-end smoke test from Control Room. Safe to delete.",
        "priority":    "Low",
    })
    print(jira_result)

    print("\n[2/2] Sending confirmation email via AWS SES...")
    email_result = send_ses_email.run({
        "subject": "Robocorp Control Room: Full Flow Test Passed",
        "body":    (
            "Full flow smoke test completed from Robocorp Control Room.\n\n"
            "JIRA result:\n" + jira_result + "\n\n"
            "Both JIRA and AWS SES are working correctly from Control Room."
        ),
    })
    print(email_result)

    jira_ok  = "Key:" in jira_result or "created" in jira_result.lower()
    email_ok = "Message ID" in email_result

    print("\n" + "=" * 60)
    print("JIRA:    " + ("PASSED" if jira_ok  else "FAILED"))
    print("AWS SES: " + ("PASSED" if email_ok else "FAILED"))
    print("=" * 60)

    if not jira_ok or not email_ok:
        raise RuntimeError("One or more smoke tests failed. Check credentials in Control Room Vault")

    print("\nALL SMOKE TESTS PASSED from Control Room!")