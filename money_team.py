#!/usr/bin/env python3
"""
money-team — autonomous revenue-seeking agent team.

Goal: generate income from EVERY channel — own products, services,
daily research into problems people pay to solve, LinkedIn, IG, anything.

Pipeline (daily cycle):
    Research  -> find problems people pay to solve (REAL, calls OpenRouter)
    Build     -> turn top idea into a product/service/landing (gated: agent-stack)
    Market    -> post to LinkedIn + IG (gated: LinkedIn creds; IG via ig-growth-engine)
    Sell      -> publish to ANSY store / Stripe (gated: Stripe key)

v1 ships a fully-working Research agent + persistent memory. Build/Market/Sell
are wired with honest credential gates (no stubs pretending to work).

Zero third-party deps — stdlib only (urllib, json, datetime).
"""
import os
import json
import datetime
import urllib.request
import urllib.error

ROOT = os.path.dirname(os.path.abspath(__file__))
MEM = os.path.join(ROOT, "memory")
IDEAS = os.path.join(MEM, "ideas.jsonl")
STATE = os.path.join(MEM, "state.json")
MODEL = os.getenv("OPENROUTER_MODEL", "openai/gpt-4o-mini")


# ----------------------------------------------------------------------------
# Memory
# ----------------------------------------------------------------------------
def load_state():
    if os.path.exists(STATE):
        try:
            return json.load(open(STATE))
        except Exception:
            pass
    return {"cycles": 0, "last_run": None, "last_ideas": [], "last_error": None}


def save_state(s):
    os.makedirs(MEM, exist_ok=True)
    json.dump(s, open(STATE, "w"), indent=2)


def append_idea(idea):
    os.makedirs(MEM, exist_ok=True)
    with open(IDEAS, "a", encoding="utf-8") as f:
        f.write(json.dumps(idea, ensure_ascii=False) + "\n")


# ----------------------------------------------------------------------------
# Research agent  (REAL — calls OpenRouter)
# ----------------------------------------------------------------------------
def research():
    """Find 3 problems people currently pay money to solve, with evidence."""
    key = os.getenv("OPENROUTER_API_KEY")
    if not key:
        return None, "OPENROUTER_API_KEY not set (needed for Research agent)"

    system = (
        "You are a sharp business researcher. Output ONLY valid JSON: "
        '{"problems":[{"title":str,"pains":str,"evidence":str,"price_range":str,'
        '"channel":str,"effort":str}]} '
        "channel must be one of: product, service, affiliate, saas, content. "
        "Focus on problems people ALREADY pay to solve (not hypothetical)."
    )
    user = (
        "List 3 problems people pay money to solve RIGHT NOW (2026). "
        "For each: the pain, concrete evidence of willingness to pay "
        "(existing paid tools/communities), realistic price range, best channel "
        "to monetize, and build effort (low/med/high)."
    )

    body = json.dumps({
        "model": MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0.7,
    }).encode()

    req = urllib.request.Request(
        "https://openrouter.ai/api/v1/chat/completions",
        data=body,
        headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            data = json.loads(r.read().decode())
        content = data["choices"][0]["message"]["content"]
        parsed = json.loads(content)
        problems = parsed.get("problems", [])
        stamp = datetime.datetime.utcnow().isoformat()
        for p in problems:
            p["captured_at"] = stamp
            append_idea(p)
        return problems, None
    except urllib.error.URLError as e:
        return None, "OpenRouter request failed: " + str(e)
    except (KeyError, json.JSONDecodeError) as e:
        return None, "Bad response: " + str(e)


# ----------------------------------------------------------------------------
# Build / Market / Sell agents  (wired, gated)
# ----------------------------------------------------------------------------
def build(idea):
    # Needs an autonomous coding agent (agent-stack / Codex / Aether OS).
    if not os.getenv("BUILD_AGENT_ENABLED"):
        return "GATED: set BUILD_AGENT_ENABLED + wire agent-stack to implement '%s'" % idea.get("title")
    return "BUILD not yet connected to coding agent."


def market(idea):
    out = []
    # IG: ig-growth-engine already runs daily (cron 04:30 UTC) — hook here.
    out.append("IG: route to ~/ig-growth-engine (already scheduled)")
    if not os.getenv("LINKEDIN_ACCESS_TOKEN"):
        out.append("GATED: LINKEDIN_ACCESS_TOKEN needed for LinkedIn posting")
    else:
        out.append("LinkedIn: ready to post")
    return " | ".join(out)


def sell(idea):
    if not os.getenv("STRIPE_SECRET_KEY"):
        return "GATED: STRIPE_SECRET_KEY needed to publish '%s' to ANSY store" % idea.get("title")
    return "Stripe ready."


# ----------------------------------------------------------------------------
# Orchestrator
# ----------------------------------------------------------------------------
def run_cycle():
    s = load_state()
    s["cycles"] += 1
    s["last_run"] = datetime.datetime.utcnow().isoformat()

    problems, err = research()
    if err:
        s["last_error"] = err
        save_state(s)
        return s, err

    s["last_ideas"] = [p["title"] for p in problems]
    s["last_error"] = None
    save_state(s)

    # Downstream agents (gated) — run against the top idea.
    report = {"research": [p["title"] for p in problems]}
    if problems:
        top = problems[0]
        report["build"] = build(top)
        report["market"] = market(top)
        report["sell"] = sell(top)
    return s, report


if __name__ == "__main__":
    state, result = run_cycle()
    print(json.dumps({"state": state, "result": result}, ensure_ascii=False, indent=2))
