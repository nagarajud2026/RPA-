"""
Email Tool - AWS SES
=============================================
Uses boto3 + AWS Simple Email Service.
No Azure App Registration needed.

Tools:
  - send_ses_email      -> sends email via AWS SES
  - list_ses_identities -> lists verified SES email addresses

Credentials from .env:
  AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_REGION
  SES_SENDER_EMAIL, SES_RECIPIENT_EMAIL

Standalone test:
  cd ai-bot
  python tools/email_tool.py
"""

import boto3
from botocore.exceptions import ClientError
from langchain.tools import tool
from dotenv import load_dotenv
import os

load_dotenv()


def get_ses_client():
    return boto3.client(
        "ses",
        region_name=os.environ.get("AWS_REGION", "ap-south-1"),
        aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY"),
    )


@tool
def send_ses_email(subject: str, body: str, recipient_email: str = "") -> str:
    """
    Sends an email via AWS SES (Simple Email Service).

    Args:
        subject: Email subject line
        body: Email body text
        recipient_email: Override recipient. If empty, uses SES_RECIPIENT_EMAIL from .env

    Returns:
        Confirmation string with AWS message ID
    """
    client    = get_ses_client()
    sender    = os.environ.get("SES_SENDER_EMAIL")
    recipient = recipient_email or os.environ.get("SES_RECIPIENT_EMAIL")

    if not sender:
        return "Error: SES_SENDER_EMAIL not set in .env"
    if not recipient:
        return "Error: SES_RECIPIENT_EMAIL not set in .env"

    try:
        response = client.send_email(
            Source=sender,
            Destination={"ToAddresses": [recipient]},
            Message={
                "Subject": {"Data": subject, "Charset": "UTF-8"},
                "Body":    {"Text": {"Data": body, "Charset": "UTF-8"}},
            },
        )
        message_id = response["MessageId"]
        return (
            "Email sent via AWS SES!\n"
            "   From:       " + sender + "\n"
            "   To:         " + recipient + "\n"
            "   Subject:    " + subject + "\n"
            "   Message ID: " + message_id
        )

    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        error_msg  = e.response["Error"]["Message"]

        if error_code == "MessageRejected":
            return (
                "ERROR - SES rejected the email: " + error_msg + "\n"
                "Fix: Verify " + sender + " in AWS Console -> SES -> Verified identities"
            )
        if error_code == "InvalidParameterValue":
            return (
                "ERROR - Invalid email address: " + error_msg + "\n"
                "Check SES_SENDER_EMAIL and SES_RECIPIENT_EMAIL in .env"
            )
        if "not authorized" in error_msg.lower():
            return (
                "ERROR - AWS credentials error: " + error_msg + "\n"
                "Check AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY in .env"
            )
        return "ERROR - SES error [" + error_code + "]: " + error_msg


@tool
def list_ses_identities(placeholder: str = "") -> str:  # ✅ FIXED: added placeholder arg to avoid NoneType parse error
    """
    Lists all verified email identities in your AWS SES account.

    Args:
        placeholder: Ignored. Required for LangChain tool compatibility.

    Returns:
        List of verified email addresses and their verification status
    """
    client = get_ses_client()

    try:
        response   = client.list_identities(IdentityType="EmailAddress", MaxItems=20)
        identities = response.get("Identities", [])

        if not identities:
            return (
                "No verified email identities found.\n"
                "Go to AWS Console -> SES -> Verified identities -> Create identity"
            )

        status_resp = client.get_identity_verification_attributes(Identities=identities)
        attrs = status_resp.get("VerificationAttributes", {})

        lines = ["Verified SES identities:\n"]
        for email in identities:
            status = attrs.get(email, {}).get("VerificationStatus", "Unknown")
            lines.append("  [" + status + "] " + email)

        return "\n".join(lines)

    except ClientError as e:
        return "ERROR listing identities: " + e.response["Error"]["Message"]


# Standalone test
if __name__ == "__main__":
    print("=" * 50)
    print("TESTING AWS SES EMAIL TOOL STANDALONE")
    print("=" * 50)

    print("\n1. Listing verified SES identities...")
    r = list_ses_identities.run({})
    print(r)

    print("\n2. Sending test email...")
    r = send_ses_email.run({
        "subject": "Test from AI Bot - AWS SES",
        "body":    (
            "This is a test email sent by the AI Bot.\n\n"
            "AWS SES integration is working correctly.\n"
            "JIRA + Email automation is live."
        ),
    })
    print(r)