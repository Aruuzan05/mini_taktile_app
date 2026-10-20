"""
mini_taktile.py - a classroom illustration of an "agentic decision platform".

NOT Taktile's code. A simplified model of the same idea, in 5 layers:

  1. DATA       mock data sources (credit bureau, bank transactions, KYC, news)
  2. ML MODEL   logistic regression -> probability the loan is repaid
  3. AI AGENT   an LLM that calls the data tools, reads the messy text
                (bank notes, news) and recommends a decision with reasons
  4. RULES      hard limits the agent can never override
  5. HUMAN      unclear or conflicting cases go to a human review queue

Every step is written to an audit trail (audit_log.json).

Run:
    pip install numpy scikit-learn anthropic
    export ANTHROPIC_API_KEY=sk-ant-...      # optional
    python mini_taktile.py                   # all demo applicants
    python mini_taktile.py cafe              # one applicant

No API key? The script uses an offline stand-in agent that follows the
same steps with simple keyword checks, so the live demo never breaks.
"""

import json
import os
import sys
from datetime import datetime, timezone

import numpy as np
from sklearn.linear_model import LogisticRegression

MODEL_NAME = os.environ.get("MINI_TAKTILE_MODEL", "claude-sonnet-5-5")
FEATURES = ["credit_score", "monthly_revenue_k", "debt_to_income", "years_in_business"]

# --------------------------------------------------------------------------
# 1) DATA: mock applicants and mock data sources
#    Structured numbers go to the ML model; free text is what the agent reads.
# --------------------------------------------------------------------------
APPLICANTS = {
    "cafe": {
        "name": "Bean There Cafe", "amount_k": 50, "purpose": "Second espresso machine and seating",
        "bureau": {"credit_score": 680, "missed_payments_24m": 1, "open_loans": 2},
        "financials": {"monthly_revenue_k": 30, "debt_to_income": 0.35, "years_in_business": 2},
        "bank_notes": "Steady card income, busier on weekends. Revenue dipped 15% in February, "
                      "recovered by April. Rent paid on time every month.",
        "kyc": {"identity_verified": True, "sanctions_hit": False},
        "news": "Local blog named the cafe one of the top 10 new coffee spots in the city.",
    },
    "bakery": {
        "name": "Golden Crust Bakery", "amount_k": 80, "purpose": "Open a second shop",
        "bureau": {"credit_score": 760, "missed_payments_24m": 0, "open_loans": 1},
        "financials": {"monthly_revenue_k": 55, "debt_to_income": 0.15, "years_in_business": 8},
        "bank_notes": "Strong, stable income. In the last 60 days there were 14 large transfers "
                      "to an online casino, totalling $42k, from the business account.",
        "kyc": {"identity_verified": True, "sanctions_hit": False},
        "news": "No news found.",
    },
    "bookshop": {
        "name": "Chapter One Books", "amount_k": 40, "purpose": "Refit the shop and add a reading cafe",
        "bureau": {"credit_score": 745, "missed_payments_24m": 0, "open_loans": 1},
        "financials": {"monthly_revenue_k": 40, "debt_to_income": 0.18, "years_in_business": 9},
        "bank_notes": "Stable income with a seasonal peak in December. Account never went below zero.",
        "kyc": {"identity_verified": True, "sanctions_hit": False},
        "news": "Hosts a monthly author event covered by the local paper.",
    },
    "florist": {
        "name": "Petal & Stem Florist", "amount_k": 30, "purpose": "Delivery van",
        "bureau": {"credit_score": 610, "missed_payments_24m": 3, "open_loans": 3},
        "financials": {"monthly_revenue_k": 12, "debt_to_income": 0.62, "years_in_business": 1},
        "bank_notes": "Irregular income, several overdraft fees each month.",
        "kyc": {"identity_verified": True, "sanctions_hit": False},
        "news": "No news found.",
    },
    "bigbuild": {
        "name": "BuildFast Ltd", "amount_k": 400, "purpose": "Equipment",
        "bureau": {"credit_score": 790, "missed_payments_24m": 0, "open_loans": 1},
        "financials": {"monthly_revenue_k": 210, "debt_to_income": 0.20, "years_in_business": 12},
        "bank_notes": "Large, steady contract income.",
        "kyc": {"identity_verified": True, "sanctions_hit": False},
        "news": "Won a city infrastructure contract last year.",
    },
}

# --------------------------------------------------------------------------
# 2) ML MODEL: trained on synthetic past loans (1 = repaid)
# --------------------------------------------------------------------------
rng = np.random.default_rng(0)
n = 2000
X = np.column_stack([rng.normal(680, 60, n), rng.gamma(2, 15, n),
                     rng.uniform(0.05, 0.8, n), rng.integers(0, 15, n)])
logit = 0.02 * (X[:, 0] - 680) + 0.03 * X[:, 1] - 4 * X[:, 2] + 0.15 * X[:, 3] + 0.5
y = (rng.random(n) < 1 / (1 + np.exp(-logit))).astype(int)
MU, SD = X.mean(0), X.std(0)
MODEL = LogisticRegression().fit((X - MU) / SD, y)


def ml_score(app):
    x = np.array([app["bureau"]["credit_score"], app["financials"]["monthly_revenue_k"],
                  app["financials"]["debt_to_income"], app["financials"]["years_in_business"]], float)
    z = (x - MU) / SD
    p = float(MODEL.predict_proba([z])[0, 1])
    contrib = MODEL.coef_[0] * z
    drivers = [f"{FEATURES[i]} {'helps' if contrib[i] > 0 else 'hurts'}"
               for i in np.argsort(-abs(contrib))[:2]]
    return {"p_repay": round(p, 2), "top_drivers": drivers}


# --------------------------------------------------------------------------
# Tools the agent may call (each one is logged to the audit trail)
# --------------------------------------------------------------------------
def tool_impl(name, app):
    if name == "get_credit_report":
        return app["bureau"]
    if name == "get_financials":
        return app["financials"]
    if name == "get_bank_transaction_notes":
        return {"notes": app["bank_notes"]}
    if name == "check_kyc":
        return app["kyc"]
    if name == "search_news":
        return {"results": app["news"]}
    if name == "get_risk_model_score":
        return ml_score(app)
    return {"error": f"unknown tool {name}"}


TOOLS = [
    {"name": "get_credit_report", "description": "Credit bureau report: score, missed payments, open loans.",
     "input_schema": {"type": "object", "properties": {}}},
    {"name": "get_financials", "description": "Monthly revenue, debt-to-income ratio and years in business.",
     "input_schema": {"type": "object", "properties": {}}},
    {"name": "get_bank_transaction_notes", "description": "Analyst notes summarising the last 6 months of bank transactions.",
     "input_schema": {"type": "object", "properties": {}}},
    {"name": "check_kyc", "description": "Identity verification and sanctions screening result.",
     "input_schema": {"type": "object", "properties": {}}},
    {"name": "search_news", "description": "Recent news and media mentions of the business.",
     "input_schema": {"type": "object", "properties": {}}},
    {"name": "get_risk_model_score", "description": "The bank's ML model: probability of repayment and its top drivers.",
     "input_schema": {"type": "object", "properties": {}}},
    {"name": "submit_recommendation", "description": "Submit your final recommendation. Call exactly once, at the end.",
     "input_schema": {"type": "object", "required": ["decision", "confidence", "reasons", "red_flags"],
                      "properties": {
                          "decision": {"type": "string", "enum": ["APPROVE", "DECLINE", "HUMAN REVIEW"]},
                          "confidence": {"type": "number", "description": "0 to 1"},
                          "reasons": {"type": "array", "items": {"type": "string"},
                                      "description": "2-4 short reasons, each citing the evidence used"},
                          "red_flags": {"type": "array", "items": {"type": "string"}}}}},
]

SYSTEM_PROMPT = (
    "You are a credit analyst agent at a bank, reviewing a small-business loan application. "
    "Use the tools to gather evidence: always check the credit report, financials, bank transaction notes, "
    "KYC, news and the risk model score. Read the free-text notes carefully: they can reveal risks that the "
    "numeric model cannot see. Then call submit_recommendation once. Recommend HUMAN REVIEW when evidence "
    "conflicts or you are not confident. Every reason must cite the evidence it rests on. "
    "You only recommend; the bank's rules and a human make the final call."
)


# --------------------------------------------------------------------------
# 3) AI AGENT: real LLM agent (tool-use loop), or the offline stand-in
# --------------------------------------------------------------------------
def run_llm_agent(app, audit, api_key=None, policy=None):
    policy = policy or DEFAULT_POLICY
    system = SYSTEM_PROMPT + " Treat these as red flags if they appear in the text: " + ", ".join(policy["red_flags"]) + "."
    import anthropic
    client = anthropic.Anthropic(api_key=api_key) if api_key else anthropic.Anthropic()
    messages = [{"role": "user", "content":
                 f"Application: {app['name']} asks for ${app['amount_k']}k. Purpose: {app['purpose']}."}]
    for _ in range(12):  # step limit: the agent cannot loop forever
        resp = client.messages.create(model=MODEL_NAME, max_tokens=1024, system=system,
                                      tools=TOOLS, messages=messages)
        messages.append({"role": "assistant", "content": resp.content})
        results = []
        for block in resp.content:
            if block.type != "tool_use":
                continue
            if block.name == "submit_recommendation":
                _log(audit, "AI agent", "agent_recommendation", **block.input)
                return block.input
            out = tool_impl(block.name, app)
            _log(audit, "AI agent", "agent_tool_call", tool=block.name, result=out)
            results.append({"type": "tool_result", "tool_use_id": block.id, "content": json.dumps(out)})
        if not results:
            break
        messages.append({"role": "user", "content": results})
    return {"decision": "HUMAN REVIEW", "confidence": 0.0,
            "reasons": ["Agent did not finish within its step limit"], "red_flags": []}


RED_FLAG_WORDS = ["casino", "gambling", "overdraft", "lawsuit", "fraud", "bankrupt", "cash deposits"]

# --------------------------------------------------------------------------
# POLICY: everything a risk team can change without code (the "no-code" layer).
# The Streamlit app edits a copy of this; the CLI uses it as is.
# --------------------------------------------------------------------------
FIELDS = {  # field name -> (label, how to read it from an application)
    "amount_k": ("Loan amount ($k)", lambda a: a["amount_k"]),
    "credit_score": ("Credit score", lambda a: a["bureau"]["credit_score"]),
    "missed_payments_24m": ("Missed payments (24m)", lambda a: a["bureau"]["missed_payments_24m"]),
    "monthly_revenue_k": ("Monthly revenue ($k)", lambda a: a["financials"]["monthly_revenue_k"]),
    "debt_to_income_pct": ("Debt-to-income (%)", lambda a: round(a["financials"]["debt_to_income"] * 100)),
    "years_in_business": ("Years in business", lambda a: a["financials"]["years_in_business"]),
    "identity_verified": ("Identity verified (1 = yes)", lambda a: int(a["kyc"]["identity_verified"])),
    "sanctions_hit": ("Sanctions hit (1 = yes)", lambda a: int(a["kyc"]["sanctions_hit"])),
}
OPS = {">": lambda x, v: x > v, ">=": lambda x, v: x >= v, "<": lambda x, v: x < v,
       "<=": lambda x, v: x <= v, "=": lambda x, v: x == v}

DEFAULT_POLICY = {
    "rules": [  # evaluated top to bottom; DECLINE stops the flow, HUMAN REVIEW flags the case
        {"active": True, "name": "Product limit", "field": "amount_k", "op": ">", "value": 250, "then": "DECLINE"},
        {"active": True, "name": "Identity check", "field": "identity_verified", "op": "=", "value": 0, "then": "DECLINE"},
        {"active": True, "name": "Sanctions screening", "field": "sanctions_hit", "op": "=", "value": 1, "then": "DECLINE"},
        {"active": False, "name": "Repeated missed payments", "field": "missed_payments_24m", "op": ">=", "value": 3,
         "then": "HUMAN REVIEW"},
    ],
    "approve_at": 0.75,         # model score at or above -> agent may approve
    "decline_at": 0.40,         # model score at or below -> agent declines
    "min_confidence": 0.60,     # guardrail: below this the case goes to a human
    "red_flags": list(RED_FLAG_WORDS),
}


def _log(audit, layer, step, **kw):
    audit.append({"t": datetime.now().astimezone().isoformat(timespec="milliseconds"), "layer": layer,
                  "step": step, **kw})


def evaluate_rules(app, policy):
    """Return (blocking_rule or None, list of HUMAN REVIEW rules hit, list of all checks)."""
    checks, review_hits = [], []
    for r in policy["rules"]:
        if not r.get("active", True) or r.get("field") not in FIELDS or r.get("op") not in OPS:
            continue
        x = FIELDS[r["field"]][1](app)
        hit = OPS[r["op"]](x, float(r["value"]))
        checks.append({"rule": r["name"], "condition": f"{r['field']} {r['op']} {float(r['value']):g}", "actual": x,
                       "hit": bool(hit), "then": r["then"] if hit else "pass"})
        if hit and r["then"] == "DECLINE":
            return r, review_hits, checks
        if hit and r["then"] == "HUMAN REVIEW":
            review_hits.append(r)
    return None, review_hits, checks


def run_offline_agent(app, audit, policy=DEFAULT_POLICY):
    """Same steps as the LLM agent, with keyword checks instead of a language model."""
    ev = {}
    for name in ["get_credit_report", "get_financials", "get_bank_transaction_notes",
                 "check_kyc", "search_news", "get_risk_model_score"]:
        ev[name] = tool_impl(name, app)
        _log(audit, "AI agent", "agent_tool_call", tool=name, result=ev[name])
    text = (ev["get_bank_transaction_notes"]["notes"] + " " + ev["search_news"]["results"]).lower()
    flags = [f"Text mentions '{w}'" for w in policy["red_flags"] if w and w.lower() in text]
    p = ev["get_risk_model_score"]["p_repay"]
    reasons = [f"Risk model: {p:.0%} chance of repayment ({', '.join(ev['get_risk_model_score']['top_drivers'])})"]
    if p <= policy["decline_at"]:
        decision, conf = "DECLINE", 1 - p
        reasons.append("Low score" + (", and the notes confirm the risk" if flags else "; notes do not change the picture"))
    elif flags:
        decision, conf = "HUMAN REVIEW", 0.5
        reasons.append("Bank notes or news contain a red flag the model cannot see")
    elif p >= policy["approve_at"]:
        decision, conf = "APPROVE", p
        reasons.append("Strong score and no red flags in notes or news")
    else:
        decision, conf = "HUMAN REVIEW", 0.5
        reasons.append("Middle score: not confident enough to decide alone")
    rec = {"decision": decision, "confidence": round(conf, 2), "reasons": reasons, "red_flags": flags}
    _log(audit, "AI agent", "agent_recommendation", **rec)
    return rec


# --------------------------------------------------------------------------
# ORCHESTRATOR: rules first, then agent, then guardrails -> human queue
# --------------------------------------------------------------------------
def decide(app_id, use_llm, api_key=None, policy=None):
    return decide_app(APPLICANTS[app_id], use_llm, api_key, policy)


def decide_app(app, use_llm, api_key=None, policy=None, version="v1"):
    """Run one application through rules, agent and guardrails under a given policy."""
    policy = policy or DEFAULT_POLICY
    audit = []
    _log(audit, "Intake", "received", applicant=app["name"], amount_k=app["amount_k"], policy_version=version)

    block, review_hits, checks = evaluate_rules(app, policy)
    _log(audit, "Rules", "rules_evaluated", checks=checks)
    if block:
        why = [f"Rule \u201c{block['name']}\u201d: {block['field']} {block['op']} {float(block['value']):g}"]
        _log(audit, "Decision", "final", decision="DECLINE", decided_by="hard rules", reasons=why)
        return {"final": "DECLINE", "by": "rules", "why": why, "rule_checks": checks,
                "policy_version": version}, audit

    if use_llm:
        agent = run_llm_agent(app, audit, api_key, policy)
    else:
        agent = run_offline_agent(app, audit, policy)

    score = ml_score(app)["p_repay"]
    final, why = agent["decision"], list(agent["reasons"])
    n_before = len(why)
    if agent["decision"] == "APPROVE" and score < 0.5:
        final, why = "HUMAN REVIEW", why + [f"Guardrail: agent approves but model score is only {score:.0%}"]
    if agent["decision"] == "DECLINE" and score > 0.8:
        final, why = "HUMAN REVIEW", why + [f"Guardrail: agent declines but model score is {score:.0%}"]
    if agent.get("confidence", 0) < policy["min_confidence"] and final != "HUMAN REVIEW":
        final, why = "HUMAN REVIEW", why + [f"Guardrail: agent confidence below {policy['min_confidence']:.0%}"]
    for r in review_hits:
        if final != "HUMAN REVIEW" or not any(r["name"] in w for w in why):
            final = "HUMAN REVIEW"
            why = why + [f"Rule \u201c{r['name']}\u201d sends the case to a human"]
    guard = why[n_before:]
    if guard:
        _log(audit, "Guardrails", "guardrails_triggered", triggered=guard)
    else:
        _log(audit, "Guardrails", "guardrails_passed")

    by = "agent" if final != "HUMAN REVIEW" else "sent to human"
    _log(audit, "Decision", "final", decision=final,
         decided_by="human review queue" if final == "HUMAN REVIEW" else "agent + guardrails", reasons=why)
    return {"final": final, "by": by, "why": why, "red_flags": agent.get("red_flags", []), "model_score": score,
            "agent_decision": agent["decision"], "agent_confidence": agent.get("confidence", 0),
            "guardrails": guard, "rule_checks": checks, "policy_version": version}, audit


def main():
    use_llm = bool(os.environ.get("ANTHROPIC_API_KEY"))
    print(f"Agent: {'LLM (' + MODEL_NAME + ')' if use_llm else 'offline stand-in (no ANTHROPIC_API_KEY set)'}\n")
    ids = sys.argv[1:] or list(APPLICANTS)
    log = {}
    for app_id in ids:
        result, audit = decide(app_id, use_llm)
        log[app_id] = audit
        app = APPLICANTS[app_id]
        print(f"=== {app['name']} (${app['amount_k']}k, {app['purpose']}) ===")
        print(f"  FINAL: {result['final']}   [{result['by']}]")
        if "model_score" in result:
            print(f"  ML model p(repay): {result['model_score']:.0%}")
        for r in result["why"]:
            print(f"  - {r}")
        for f in result.get("red_flags", []):
            print(f"  ! red flag: {f}")
        tools_used = [a["tool"] for a in audit if a["step"] == "agent_tool_call"]
        if tools_used:
            print(f"  Agent checked: {', '.join(tools_used)}")
        print()
    with open("audit_log.json", "w") as fh:
        json.dump(log, fh, indent=2)
    print("Full audit trail written to audit_log.json")


if __name__ == "__main__":
    main()
