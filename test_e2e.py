"""
End-to-End Test Script
======================
Run AFTER docker-compose up to verify everything works live.

Usage:
  python test_e2e.py

5 steps tested:
  1. Health checks on all 3 services
  2. Service B classification logic
  3. AI Bot tools registered correctly
  4. AI Bot direct run (live JIRA + AWS SES email)
  5. Full chain: Service A → B → AI Bot → JIRA + SES
"""

import requests
import sys

BASE_A   = "http://localhost:8000"
BASE_B   = "http://localhost:8001"
BASE_BOT = "http://localhost:8002"

results = []

def check(name, fn):
    try:
        fn()
        print(f"✅ PASS  {name}")
        results.append((name, True))
    except Exception as e:
        print(f"❌ FAIL  {name}")
        print(f"         Error: {e}")
        results.append((name, False))


# ── Step 1: Health Checks ─────────────────────────────────────
print("\n" + "="*60)
print("STEP 1 — Health Checks")
print("="*60)

def test_health_a():
    r = requests.get(f"{BASE_A}/health", timeout=5)
    assert r.status_code == 200 and r.json()["status"] == "ok"

def test_health_b():
    r = requests.get(f"{BASE_B}/health", timeout=5)
    assert r.status_code == 200 and r.json()["status"] == "ok"

def test_health_bot():
    r = requests.get(f"{BASE_BOT}/health", timeout=5)
    assert r.status_code == 200 and r.json()["status"] == "ok"
    assert r.json()["agent_ready"] is True, "Agent not ready — check ANTHROPIC_API_KEY"

check("Service A health", test_health_a)
check("Service B health", test_health_b)
check("AI Bot health + agent ready", test_health_bot)


# ── Step 2: Service B Classification ─────────────────────────
print("\n" + "="*60)
print("STEP 2 — Service B Classification")
print("="*60)

def test_b_bug():
    r = requests.post(f"{BASE_B}/process", json={"data": "Critical login bug on Pod1"}, timeout=10)
    assert r.status_code == 200
    d = r.json()
    assert d["enriched"]["category"] == "BUG_REPORT"
    assert d["enriched"]["priority"] == "Critical"
    print(f"         → Category: {d['enriched']['category']}, Priority: {d['enriched']['priority']}")

def test_b_feature():
    r = requests.post(f"{BASE_B}/process", json={"data": "Add new dashboard feature"}, timeout=10)
    assert r.status_code == 200
    assert r.json()["enriched"]["category"] == "FEATURE_REQUEST"
    print(f"         → Category: {r.json()['enriched']['category']}")

check("Service B: bug classification",     test_b_bug)
check("Service B: feature classification", test_b_feature)


# ── Step 3: AI Bot Tools ──────────────────────────────────────
print("\n" + "="*60)
print("STEP 3 — AI Bot Tools")
print("="*60)

def test_tools():
    r = requests.get(f"{BASE_BOT}/tools", timeout=5)
    assert r.status_code == 200
    tools = r.json()["tools"]
    for t in ["create_jira_ticket", "get_open_jira_tickets", "send_ses_email"]:
        assert t in tools, f"Missing: {t}"
    print(f"         → Tools: {', '.join(tools)}")

check("AI Bot: all tools registered", test_tools)


# ── Step 4: AI Bot Direct Run ─────────────────────────────────
print("\n" + "="*60)
print("STEP 4 — AI Bot Direct Run (LIVE JIRA + AWS SES)")
print("="*60)
print("  ⏳ Calls LLM + JIRA + AWS SES. Takes ~20 seconds...")

def test_bot_run():
    r = requests.post(f"{BASE_BOT}/run", json={
        "task": (
            "Create a JIRA ticket titled 'E2E Test from AI Bot' "
            "with description 'Created by automated e2e test.' priority Low. "
            "Then send an email with subject 'AI Bot E2E Test Passed' "
            "confirming the ticket was created."
        )
    }, timeout=120)
    assert r.status_code == 200, f"Status {r.status_code}: {r.text}"
    d = r.json()
    assert d["status"] == "success"
    print(f"\n         Result: {d['result'][:120]}...")

check("AI Bot: agent run (JIRA + SES email)", test_bot_run)


# ── Step 5: Full Chain via Service A ─────────────────────────
print("\n" + "="*60)
print("STEP 5 — Full Chain: Service A → B → AI Bot")
print("="*60)
print("  ⏳ Full chain. Takes ~30 seconds...")

def test_full_chain():
    r = requests.post(f"{BASE_A}/trigger", json={
        "task":   "Critical bug: users cannot log in to Pod2 application",
        "notify": True,
    }, timeout=120)
    assert r.status_code == 200, f"Status {r.status_code}: {r.text}"
    d = r.json()
    assert d["status"] == "success"
    print(f"\n         Service B: {d['service_b_output'][:80]}...")
    print(f"         AI Bot:    {d['ai_bot_result'][:80]}...")

check("Full chain via Service A /trigger", test_full_chain)


# ── Summary ───────────────────────────────────────────────────
print("\n" + "="*60)
print("TEST SUMMARY")
print("="*60)
passed = sum(1 for _, ok in results if ok)
total  = len(results)

for name, ok in results:
    print(f"  {'✅' if ok else '❌'}  {name}")

print(f"\nResult: {passed}/{total} tests passed")

if passed == total:
    print("\n🎉 ALL TESTS PASSED!")
    print("   Live JIRA tickets created ✅")
    print("   Live AWS SES emails sent  ✅")
    sys.exit(0)
else:
    print(f"\n⚠️  {total-passed} test(s) failed.")
    print("   Check logs: docker-compose logs -f")
    sys.exit(1)
