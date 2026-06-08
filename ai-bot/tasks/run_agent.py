"""
Robocorp Task Runner
====================
Entry point when Robocorp Control Room runs the robot.

4 tasks:
  1. run_ai_agent      -- full agent run (JIRA + email via LLM)
  2. test_jira_only    -- smoke test JIRA credentials only
  3. test_email_only   -- smoke test AWS SES credentials only
  4. test_full_flow    -- smoke test JIRA + SES together (no LLM)

Run locally:
  cd ai-bot
  rcc run --task "Run AI Agent"
  rcc run --task "Test JIRA Only"
  rcc run --task "Test Email Only"
  rcc run --task "Test Full Flow"
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from robocorp.tasks import task
from dotenv import load_dotenv

load_dotenv()


def extract_output(result: dict) -> str:
    """
    ✅ Robustly extract final output from agent result.
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
    Reads AGENT_TASK from .env (or Control Room env variable).
    Runs the full LangChain agent -- creates JIRA ticket + sends email.
    """
    from main import agent_executor

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

    result = agent_executor.invoke({"input": agent_task})
    output = extract_output(result)  # ✅ FIXED: robust extraction instead of result.get("output","")

    print("\n" + "=" * 60)
    print("AGENT RESULT:")
    print(output)
    print("=" * 60 + "\n")

    return output


@task
def test_jira_only():
    """
    Smoke test: directly creates a JIRA ticket without LLM.
    Run this first to verify JIRA credentials before the full agent.
    """
    from tools.jira_tool import create_jira_ticket

    print("\n" + "=" * 50)
    print("SMOKE TEST - JIRA")
    print("=" * 50)

    result = create_jira_ticket.run({
        "summary":     "Robocorp Smoke Test - JIRA Connection",
        "description": "Auto-created by Robocorp smoke test. Safe to delete.",
        "priority":    "Low",
    })
    print(result)

    if "Key:" in result or "created" in result.lower():
        print("\nJIRA PASSED - credentials are correct")
    else:
        print("\nJIRA FAILED - check JIRA_URL, JIRA_EMAIL, JIRA_API_TOKEN in .env")
        raise RuntimeError("JIRA smoke test failed")


@task
def test_email_only():
    """
    Smoke test: directly sends an email via AWS SES without LLM.
    Run this to verify AWS SES credentials before the full agent.
    """
    from tools.email_tool import send_ses_email, list_ses_identities

    print("\n" + "=" * 50)
    print("SMOKE TEST - AWS SES EMAIL")
    print("=" * 50)

    print("\nStep 1: Checking verified SES identities...")
    identities = list_ses_identities.run({})
    print(identities)

    print("\nStep 2: Sending test email...")
    result = send_ses_email.run({
        "subject": "Robocorp Smoke Test - AWS SES Connection",
        "body":    "This is a smoke test email from the Robocorp AI Bot.\nAWS SES is working correctly.",
    })
    print(result)

    if "Message ID" in result:
        print("\nAWS SES PASSED - email sent successfully")
    else:
        print("\nAWS SES FAILED - check AWS credentials and SES verified identities in .env")
        raise RuntimeError("AWS SES smoke test failed")


@task
def test_full_flow():
    """
    Full smoke test: creates JIRA ticket + sends email -- no LLM.
    Both tools called directly to isolate credential issues.
    """
    from tools.jira_tool import create_jira_ticket
    from tools.email_tool import send_ses_email

    print("\n" + "=" * 60)
    print("FULL FLOW SMOKE TEST - JIRA + AWS SES")
    print("=" * 60)

    # Step 1: JIRA
    print("\n[1/2] Creating JIRA ticket...")
    jira_result = create_jira_ticket.run({
        "summary":     "Full Flow Smoke Test - JIRA + AWS SES",
        "description": "End-to-end smoke test. Both JIRA and SES email tested together.",
        "priority":    "Low",
    })
    print(jira_result)

    # Step 2: Email
    print("\n[2/2] Sending confirmation email via AWS SES...")
    email_result = send_ses_email.run({
        "subject": "Robocorp: Full Flow Smoke Test Passed",
        "body":    (
            "Full flow smoke test completed.\n\n"
            "JIRA result:\n" + jira_result + "\n\n"
            "Both JIRA and AWS SES are working correctly."
        ),
    })
    print(email_result)

    # Summary
    jira_ok  = "Key:" in jira_result or "created" in jira_result.lower()
    email_ok = "Message ID" in email_result

    print("\n" + "=" * 60)
    print("JIRA:    " + ("PASSED" if jira_ok  else "FAILED"))
    print("AWS SES: " + ("PASSED" if email_ok else "FAILED"))
    print("=" * 60)

    if not jira_ok or not email_ok:
        raise RuntimeError("One or more smoke tests failed. Check credentials in .env")

    print("\nALL SMOKE TESTS PASSED - ready for full agent run!")