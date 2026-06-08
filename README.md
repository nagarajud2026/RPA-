# AI Project — Complete Execution Guide
## AWS SES + JIRA + LangChain + Robocorp + Docker

---

## What This Project Does

```
You type a task  →  Service A receives it
                 →  Service B classifies it (bug/feature/priority)
                 →  AI Bot (LangChain) creates JIRA ticket
                 →  AI Bot sends email via AWS SES
                 →  You get real JIRA ticket + real email in inbox
```

---

## Folder Structure

```
ai-project-aws/
├── .env                         ← YOUR CREDENTIALS (fill this first)
├── .gitignore
├── docker-compose.yml
├── test_e2e.py                  ← run after docker-compose up
├── app-service-a/               ← Pod 1 - API Gateway  (port 8000)
│   ├── Dockerfile
│   ├── requirements.txt
│   └── main.py
├── app-service-b/               ← Pod 2 - Business Logic (port 8001)
│   ├── Dockerfile
│   ├── requirements.txt
│   └── main.py
├── ai-bot/                      ← Pod 3 - AI Agent (port 8002)
│   ├── Dockerfile
│   ├── robot.yaml               ← Robocorp task definitions
│   ├── conda.yaml               ← Robocorp Python environment
│   ├── requirements.txt
│   ├── main.py                  ← LangChain agent
│   ├── tools/
│   │   ├── jira_tool.py         ← JIRA: create/list/update/comment
│   │   └── email_tool.py        ← AWS SES: send/list emails
│   └── tasks/
│       └── run_agent.py         ← Robocorp task runner
└── k8s/
    └── deployment.yaml          ← Phase 3: AWS EKS
```

---

# ════════════════════════════════════════
# PHASE A — ONE-TIME SETUP (do this once)
# ════════════════════════════════════════

## A1 — Install Tools on Your Machine

```bash
# Verify Python
python --version        # need 3.11+

# Verify Docker
docker --version        # need 24+
docker compose version  # need v2+

# Install RCC (Robocorp CLI)

# Mac/Linux:
curl -o rcc https://downloads.robocorp.com/rcc/releases/latest/macos64/rcc
chmod +x rcc && sudo mv rcc /usr/local/bin/rcc

# Windows (PowerShell as Admin):
iwr -outf rcc.exe https://downloads.robocorp.com/rcc/releases/latest/windows64/rcc.exe
Move-Item .\rcc.exe C:\Windows\System32\rcc.exe

# Verify RCC
rcc --version
```

**VS Code Extensions to install** (Ctrl+Shift+X):
- Python (Microsoft)
- Docker (Microsoft)
- YAML (Red Hat)
- Robocorp Code (Robocorp)

---

## A2 — Verify Your Email in AWS SES (10 minutes)

This is the ONLY setup needed for email. No Azure, no App Registration.

```
Step 1: Go to AWS Console → search "SES" → Simple Email Service
Step 2: Left menu → Verified identities → Create identity
Step 3: Choose "Email address" → enter your sender email → Create identity
Step 4: Go to your inbox → click the verification link from AWS
Step 5: Repeat steps 2-4 for your RECIPIENT email (required in sandbox)
Step 6: Back in SES → Verified identities → both emails should show "Verified"
```

> NOTE: AWS SES starts in "Sandbox" mode — you can only send TO verified emails.
> For testing this is fine. For production, click "Request production access" in SES.

---

## A3 — Fill in Your .env File

Open `.env` and replace every placeholder:

```env
ANTHROPIC_API_KEY=sk-ant-xxxxx          ← from console.anthropic.com
JIRA_URL=https://yourco.atlassian.net   ← your JIRA URL
JIRA_EMAIL=you@company.com              ← your JIRA login email
JIRA_API_TOKEN=xxxxx                    ← from id.atlassian.com/api-tokens
JIRA_PROJECT_KEY=PROJ                   ← your project key (e.g. DEV, OPS)
AWS_ACCESS_KEY_ID=AKIA...               ← your AWS key
AWS_SECRET_ACCESS_KEY=xxxxx             ← your AWS secret
AWS_REGION=ap-south-1                   ← your SES region
SES_SENDER_EMAIL=you@company.com        ← verified in SES
SES_RECIPIENT_EMAIL=you@company.com     ← verified in SES (can be same)
```

---

# ════════════════════════════════════════
# PHASE B — VS CODE EXECUTION ORDER
# ════════════════════════════════════════

Open VS Code → File → Open Folder → select ai-project-aws/
Open Terminal in VS Code: Ctrl+` (backtick)

---

## B1 — Install Python Dependencies

```bash
cd ai-bot
pip install -r requirements.txt
```

Wait for install to complete (~2 minutes).

---

## B2 — Test JIRA Tool (standalone, no Docker)

```bash
# Still inside ai-bot/
python tools/jira_tool.py
```

**Expected output:**
```
==================================================
TESTING JIRA TOOL STANDALONE
==================================================

1. Creating ticket...
✅ JIRA ticket created!
   Key:      PROJ-42
   Summary:  Standalone test ticket from AI Bot
   Priority: Low
   URL:      https://yourco.atlassian.net/browse/PROJ-42

2. Fetching open tickets...
Open tickets in PROJ (1 found):
  PROJ-42: [Low] Standalone test ticket from AI Bot
```

**If this fails:**
- `401 Unauthorized` → wrong JIRA_EMAIL or JIRA_API_TOKEN in .env
- `404 Not Found` → wrong JIRA_URL or JIRA_PROJECT_KEY in .env

---

## B3 — Test AWS SES Email Tool (standalone, no Docker)

```bash
python tools/email_tool.py
```

**Expected output:**
```
==================================================
TESTING AWS SES EMAIL TOOL STANDALONE
==================================================

1. Listing verified SES identities...
Verified SES identities:
  ✅ you@company.com (Success)
  ✅ recipient@company.com (Success)

2. Sending test email...
✅ Email sent via AWS SES!
   From:       you@company.com
   To:         recipient@company.com
   Subject:    Test from AI Bot — AWS SES
   Message ID: 0102018abc...
```

**If this fails:**
- `MessageRejected` → email not verified in SES → go back to step A2
- `AuthFailure` → wrong AWS_ACCESS_KEY_ID or AWS_SECRET_ACCESS_KEY in .env
- `InvalidClientTokenId` → wrong AWS region in .env

**Check your inbox** — real email should arrive within 30 seconds.

---

## B4 — Test with Robocorp RCC (before Docker)

```bash
# Still inside ai-bot/
# First run creates conda environment (~3-4 minutes, one-time only)

rcc run --task "Test JIRA Only"
```

**Expected output:**
```
INFO  Creating environment...   ← first time only, takes 3 min
INFO  Running task: Test JIRA Only
==================================================
SMOKE TEST — JIRA
==================================================
✅ JIRA ticket created!
   Key: PROJ-43
✅ JIRA PASSED — credentials are correct
```

```bash
rcc run --task "Test Email Only"
```

**Expected output:**
```
✅ Email sent via AWS SES!
✅ AWS SES PASSED — email sent successfully
```

```bash
rcc run --task "Test Full Flow"
```

**Expected output:**
```
[1/2] Creating JIRA ticket...
✅ JIRA ticket created! Key: PROJ-44

[2/2] Sending confirmation email via AWS SES...
✅ Email sent via AWS SES!

JIRA:      PASSED ✅
AWS SES:   PASSED ✅

🎉 ALL SMOKE TESTS PASSED — ready for full agent run!
```

---

## B5 — Run Full AI Agent with RCC

```bash
rcc run --task "Run AI Agent"
```

**Expected output:**
```
AGENT TASK:
Create a JIRA ticket titled 'Automated Task from Robocorp AI Bot'...

> Entering new AgentExecutor chain...
> Invoking: create_jira_ticket with {'summary': 'Automated Task...', ...}
✅ JIRA ticket created! Key: PROJ-45 ...
> Invoking: send_ses_email with {'subject': 'AI Bot: New JIRA Ticket...', ...}
✅ Email sent via AWS SES! Message ID: 0102018...

AGENT RESULT:
I created JIRA ticket PROJ-45 and sent a confirmation email to recipient@company.com.
```

---

## B6 — Start Docker Compose (all 3 services)

```bash
# Go back to project root
cd ..   # now in ai-project-aws/

# Build Docker images (first time ~3-5 minutes)
docker-compose build

# Start all 3 services
docker-compose up
```

**Expected output:**
```
service-a  | INFO:  Uvicorn running on http://0.0.0.0:8000
service-b  | INFO:  Uvicorn running on http://0.0.0.0:8001
ai-bot     | INFO:  Uvicorn running on http://0.0.0.0:8002
ai-bot     | INFO:  ✅ LangChain agent initialised successfully
```

All 3 running = green.

---

## B7 — Run End-to-End Test

Open a **second terminal** in VS Code (+ button in terminal panel).
Keep docker-compose running in the first terminal.

```bash
# In second terminal, from ai-project-aws/
python test_e2e.py
```

**Expected output:**
```
STEP 1 — Health Checks
✅ PASS  Service A health
✅ PASS  Service B health
✅ PASS  AI Bot health + agent ready

STEP 2 — Service B Classification
✅ PASS  Service B: bug classification
✅ PASS  Service B: feature classification

STEP 3 — AI Bot Tools
✅ PASS  AI Bot: all tools registered

STEP 4 — AI Bot Direct Run (LIVE JIRA + AWS SES)
✅ PASS  AI Bot: agent run (JIRA + SES email)

STEP 5 — Full Chain: Service A → B → AI Bot
✅ PASS  Full chain via Service A /trigger

Result: 5/5 tests passed
🎉 ALL TESTS PASSED!
   Live JIRA tickets created ✅
   Live AWS SES emails sent  ✅
```

---

# ════════════════════════════════════════
# PHASE C — ROBOCORP CONTROL ROOM
# ════════════════════════════════════════

Do this AFTER Phase B all passes.

---

## C1 — Sign In to Control Room in VS Code

```
1. In VS Code → press Ctrl+Shift+P
2. Type: Robocorp: Sign In
3. It opens browser → sign in at cloud.robocorp.com
4. Back in VS Code → Robocorp panel appears in left sidebar
```

---

## C2 — Upload Robot to Control Room

**Option 1 — VS Code (easiest):**
```
1. VS Code left sidebar → Robocorp icon
2. Click "Upload Robot to Control Room"
3. Select your workspace (ai-bot-workspace)
4. Select the ai-bot/ folder
5. Upload complete
```

**Option 2 — Terminal:**
```bash
cd ai-bot/
rcc cloud workspace --workspace YOUR_WORKSPACE_ID
rcc cloud push --workspace YOUR_WORKSPACE_ID --robot robot.yaml
```

---

## C3 — Add Environment Variables in Control Room

```
1. cloud.robocorp.com → your workspace
2. Click your robot → "Configure" → "Environment variables"
3. Add each variable from your .env:
   ANTHROPIC_API_KEY   = sk-ant-xxxxx
   JIRA_URL            = https://yourco.atlassian.net
   JIRA_EMAIL          = you@company.com
   JIRA_API_TOKEN      = xxxxx
   JIRA_PROJECT_KEY    = PROJ
   AWS_ACCESS_KEY_ID   = AKIA...
   AWS_SECRET_ACCESS_KEY = xxxxx
   AWS_REGION          = ap-south-1
   SES_SENDER_EMAIL    = you@company.com
   SES_RECIPIENT_EMAIL = recipient@company.com
4. Save
```

---

## C4 — Run Robot from Control Room

```
1. cloud.robocorp.com → your workspace → your robot
2. Click "Run" button
3. Select task:
   - "Test JIRA Only"    ← run first
   - "Test Email Only"   ← run second
   - "Test Full Flow"    ← run third
   - "Run AI Agent"      ← final full run
4. Click Run
5. Watch live logs in Control Room
```

**To customise the agent task from Control Room:**
```
Robot → Configure → Environment variables
→ Add: AGENT_TASK = Create a JIRA ticket for [your task] and email the team
→ Run "Run AI Agent"
```

---

## C5 — Schedule Automatic Runs (optional)

```
Control Room → your robot → Schedule
→ Set frequency: hourly / daily / on trigger
→ Select task: "Run AI Agent"
→ Save
```

---

# TROUBLESHOOTING

| Error | Cause | Fix |
|-------|-------|-----|
| JIRA 401 | Wrong credentials | Check JIRA_EMAIL + JIRA_API_TOKEN in .env |
| JIRA 404 | Wrong project key | Check JIRA_PROJECT_KEY in .env |
| SES MessageRejected | Email not verified | Verify both emails in AWS Console → SES |
| SES AuthFailure | Wrong AWS keys | Check AWS_ACCESS_KEY_ID + SECRET in .env |
| SES not in region | Wrong region | Check AWS_REGION matches where SES is enabled |
| Agent not ready | Bad Anthropic key | Check ANTHROPIC_API_KEY in .env |
| Container exits | Any startup error | Run: docker-compose logs ai-bot |
| Module not found | Missing package | Run: docker-compose build --no-cache |
| rcc not found | RCC not in PATH | Reinstall RCC, check PATH variable |
| Port in use | Another service on port | Change port in docker-compose.yml |

---

# MANUAL API CALLS FOR TESTING

```bash
# Check all services are up
curl http://localhost:8000/status

# Trigger full flow via Service A
curl -X POST http://localhost:8000/trigger \
  -H "Content-Type: application/json" \
  -d '{"task": "Critical login bug in Pod1 — users cannot authenticate", "notify": true}'

# Run AI agent directly
curl -X POST http://localhost:8002/run \
  -H "Content-Type: application/json" \
  -d '{"task": "Create JIRA ticket for Pod2 memory leak and email the team"}'

# List available tools
curl http://localhost:8002/tools
```
