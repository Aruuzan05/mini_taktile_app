"""
app.py - Mini Taktile live demo, styled to match the FIN3090 Taktile deck.

    pip install -r requirements.txt
    streamlit run app.py

Three tabs, mirroring how a risk team uses a decision platform:
  1 Run a case        an application goes through Understand -> Decide -> Act with control;
                      unclear cases land in a review queue where a credit officer decides
  2 Decision flow     the no-code editor: a decision table of hard rules, score thresholds,
                      the agent's red-flag watchlist and guardrails; shadow-test a draft on
                      all applicants, then publish it as a new policy version
  3 Audit trail       every decision with its timestamped steps, the policy version it used,
                      human reviews and the history of policy changes

Without an API key the offline stand-in agent runs, so the demo never breaks.
The settings sidebar (agent choice, API key) starts collapsed.
"""

import base64
import copy
import html
import json
import os
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

import mini_taktile as mt

st.set_page_config(page_title="Mini Taktile · Live demo", page_icon="assets/star.png",
                   layout="wide", initial_sidebar_state="collapsed")

# ---------------------------------------------------------------- deck tokens
NAVY, CREAM = "#253278", "#F8EFE5"
SOFT = "#C9CEE6"                      # quiet text on navy
STATUS = {                            # colour never carries meaning alone: every badge also says it
    "APPROVE": ("#2E7D4F", "APPROVED"),
    "DECLINE": ("#B3261E", "DECLINED"),
    "HUMAN REVIEW": ("#B86E00", "SENT TO A HUMAN"),
}
STAR = base64.b64encode((Path(__file__).parent / "assets" / "star.png").read_bytes()).decode()

CSS = f"""@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
html, body, [class*="css"], .stApp, .stMarkdown, p, li, label, input, textarea, button {{
  font-family: 'Inter', Arial, sans-serif !important; }}
.stApp {{ background: {CREAM}; color: {NAVY}; }}
header[data-testid="stHeader"] {{ background: transparent; }}
[data-testid="stToolbar"], footer, #MainMenu {{ visibility: hidden; }}
.block-container {{ padding: 1.4rem 3.2rem 2rem 3.2rem; max-width: 1500px; }}
h1, h2, h3, h4, p, li, label, span {{ color: {NAVY}; }}
.topbar {{ display:flex; justify-content:space-between; font-weight:700; font-size:.85rem; }}
.title-row {{ display:flex; justify-content:space-between; align-items:center; margin: .3rem 0 .6rem 0; }}
.big {{ color:{NAVY}; font-size: 3.6rem; font-weight: 800; line-height: 1; letter-spacing:-1px; margin:0; }}
.sub {{ color:{NAVY}; font-size: 1.6rem; font-weight: 700; margin: .3rem 0 0 0; }}
.lead {{ color:{NAVY}; font-size: 1.05rem; margin-top:.4rem; max-width: 980px; }}
[data-testid="stButtonGroup"] button {{ border: 2px solid {NAVY}; font-weight: 600; padding: .3rem 1rem; }}
[data-testid="stButtonGroup"] button[aria-checked="true"] {{ background:{NAVY} !important; }}
[data-testid="stButtonGroup"] button[aria-checked="true"] * {{ color:{CREAM} !important; }}
.stTabs [data-baseweb="tab-list"] {{ gap: 6px; border-bottom: 2px solid {NAVY}; }}
.stTabs [data-baseweb="tab"] {{ background: transparent; border: 2px solid {NAVY}; border-bottom: none;
  padding: 8px 18px; }}
.stTabs [data-baseweb="tab"] p {{ font-weight: 800; font-size: 1.05rem; }}
.stTabs [aria-selected="true"] {{ background: {NAVY}; }}
.stTabs [aria-selected="true"] p {{ color: {CREAM} !important; }}
.stTabs [data-baseweb="tab-highlight"] {{ display:none; }}
.outline {{ border: 2px solid {NAVY}; padding: 16px 20px; margin: 12px 0; }}
.box-title {{ font-weight: 800; font-size: 1.15rem; margin-bottom: 4px; }}
.facts {{ display:grid; grid-template-columns: repeat(4, 1fr); gap: 4px 24px; }}
.facts .k {{ font-size:.85rem; }} .facts .v {{ font-size:1.3rem; font-weight:800; }}
.notes {{ margin-top:12px; padding-top:10px; border-top:1px solid {NAVY}33; font-size:.95rem; }}
.flag, .col .flag {{ background:#FFC9A8; color:{NAVY} !important; padding:0 4px; font-weight:700; }}
.panel {{ background:{NAVY}; display:grid; grid-template-columns: 1fr 1fr 1fr; padding: 26px 8px; margin-top: 6px; }}
.col {{ padding: 4px 24px; border-left: 2px solid {CREAM}; }}
.col:first-child {{ border-left: none; }}
.col h3 {{ color:{CREAM} !important; font-size:1.45rem; font-weight:800; margin:0 0 12px 0; padding:0; }}
.col p, .col li, .col span, .col div {{ color:{CREAM}; }}
.col .q {{ color:{SOFT} !important; font-size:.9rem; }}
.col ul {{ padding-left: 1.1rem; margin: 6px 0; }} .col ul.checks {{ list-style:none; padding-left:0; }}
.col li {{ margin: 3px 0; font-size:.95rem; }}
.col .num {{ font-size: 3.1rem; font-weight: 800; line-height: 1; }}
.gauge {{ display:flex; height:14px; margin:8px 0 2px 0; position:relative; }}
.gauge div {{ height:100%; }}
.marker {{ position:absolute; top:-6px; width:4px; height:26px; background:{CREAM}; margin-left:-2px; }}
.ticks {{ position:relative; height:16px; font-size:.75rem; }}
.ticks span {{ position:absolute; color:{SOFT} !important; }}
.badge {{ display:inline-block; padding: 7px 13px; font-weight:800; font-size:1.25rem; color:white !important;
  margin: 2px 0 8px 0; }}
.pill {{ display:inline-block; padding: 2px 9px; font-weight:700; font-size:.8rem; color:white !important; }}
.takeaway {{ font-weight:800; font-size:1.15rem; margin: 18px 0 8px 0 !important; }}
.pageno {{ text-align:right; font-size:.9rem; margin-top: 8px; }}
.tl {{ border-left: 3px solid {NAVY}; margin-left: 8px; padding-left: 18px; }}
.tl-item {{ position: relative; padding: 6px 0 12px 0; }}
.tl-item:before {{ content:''; position:absolute; left:-27px; top:10px; width:13px; height:13px;
  background:{NAVY}; border-radius:50%; border: 2px solid {CREAM}; }}
.tl-time {{ font-size:.8rem; font-family: monospace !important; }}
.tl-layer {{ display:inline-block; background:{NAVY}; color:{CREAM} !important; font-size:.75rem; font-weight:700;
  padding: 1px 8px; margin: 0 8px; }}
.tl-what {{ font-weight:600; }}
[data-testid="stExpander"] {{ border: 2px solid {NAVY}; border-radius:0; background: transparent; }}
[data-testid="stBaseButton-primary"], button[kind="primary"] {{ background:{NAVY}; border-color:{NAVY}; }}
[data-testid="stBaseButton-primary"] *, button[kind="primary"] * {{ color:{CREAM} !important; font-weight:700; }}
"""
# one line, no blank lines: Markdown would otherwise end the <style> block early
st.markdown("<style>" + " ".join(CSS.split()) + "</style>", unsafe_allow_html=True)

CASES = [  # applicant id, pill label, key takeaway (the deck's "Takeaway:" voice)
    ("bookshop", "Chapter One Books", "Clear, low-risk cases are automated, so no human time is spent on them."),
    ("bakery", "Golden Crust Bakery", "The model only sees numbers and says 99%. The agent read the bank notes, "
                                      "found the casino transfers and sent the case to a human."),
    ("cafe", "Bean There Cafe", "Borderline cases are escalated to a person, not decided by a coin flip."),
    ("bigbuild", "BuildFast Ltd", "Hard rules come first. Even a perfect score cannot override the bank's limit."),
    ("florist", "Petal & Stem Florist", "Clear declines are automated too, with the reasons recorded."),
]
CUSTOM = "Build your own"
TOOLS = {"get_credit_report": "Credit bureau", "get_financials": "Financials",
         "get_bank_transaction_notes": "Bank statement notes", "check_kyc": "Identity and sanctions (KYC)",
         "search_news": "News search", "get_risk_model_score": "ML risk model"}
FIELD_LABEL = {k: v[0] for k, v in mt.FIELDS.items()}
LABEL_FIELD = {v: k for k, v in FIELD_LABEL.items()}

# ---------------------------------------------------------------- session state
ss = st.session_state
if "policy" not in ss:
    ss.policy = copy.deepcopy(mt.DEFAULT_POLICY)
    ss.version = 1
    ss.history = [{"Version": "v1", "Published": datetime.now().strftime("%H:%M:%S"), "By": "Risk team",
                   "Changes": "Initial policy"}]
    ss.log = []          # decision log: one entry per (application, policy version, agent)
    ss.log_index = {}    # run key -> position in ss.log
    ss.editor_gen = 0    # bumped to reset the no-code editors after publish/discard

# ---------------------------------------------------------------- sidebar (collapsed by default)
with st.sidebar:
    st.subheader("Demo settings")
    engine = st.radio("AI agent", ["Offline stand-in (no key)", "Claude agent (API key)"])
    api_key = None
    if engine.startswith("Claude"):
        api_key = st.text_input("Anthropic API key", type="password", value=os.environ.get("ANTHROPIC_API_KEY", ""))
        st.caption(f"Model: {mt.MODEL_NAME}")
        if not api_key:
            st.warning("No key: using the offline agent.")
    use_llm = bool(api_key)
    st.caption("A classroom illustration of an agentic decision platform. Not Taktile's code.")


# ---------------------------------------------------------------- helpers
def esc(s):
    return html.escape(str(s))


def num(v):
    v = float(v)
    return str(int(v)) if v.is_integer() else f"{v:g}"


def vname():
    return f"v{ss.version}"


def highlight(text, words):
    out = esc(text)
    for w in words:
        if not w:
            continue
        for v in {w, w.lower(), w.capitalize()}:
            out = out.replace(v, f"<span class='flag'>{v}</span>")
    return out


def run_and_log(app):
    """Run under the published policy; log each distinct run once so reviews attach to it."""
    key = json.dumps(app, sort_keys=True) + vname() + str(use_llm)
    if key not in ss.log_index:
        with st.spinner("The AI agent is checking the data sources…"):
            try:
                result, audit = mt.decide_app(app, use_llm, api_key, ss.policy, vname())
            except Exception as e:
                st.error(f"Claude agent failed ({type(e).__name__}); using the offline agent.")
                result, audit = mt.decide_app(app, False, None, ss.policy, vname())
        ss.log.append({"ID": f"D-{len(ss.log) + 1:04d}", "Time": datetime.now().strftime("%H:%M:%S"),
                       "Applicant": app["name"], "Decision": result["final"],
                       "Decided by": {"rules": "Hard rules", "agent": "AI agent",
                                      "sent to human": "Pending human review"}[result["by"]],
                       "Policy": vname(), "Model score": result.get("model_score"),
                       "Agent": "Claude" if use_llm else "Offline", "result": result, "audit": audit})
        ss.log_index[key] = len(ss.log) - 1
    return ss.log[ss.log_index[key]]


def gauge(p, pol):
    pct, lo, hi = round(p * 100), round(pol["decline_at"] * 100), round(pol["approve_at"] * 100)
    return (f"<div class='gauge'><div style='width:{lo}%;background:#B98A86'></div>"
            f"<div style='width:{hi - lo}%;background:#C9A35B'></div><div style='width:{100 - hi}%;background:#7FA88B'></div>"
            f"<div class='marker' style='left:{pct}%'></div></div>"
            f"<div class='ticks'><span style='left:0'>decline ≤{lo}%</span>"
            f"<span style='right:0'>approve ≥{hi}%</span></div>")


def application_box(app):
    b, f = app["bureau"], app["financials"]
    facts = [("Loan requested", f"${app['amount_k']}k"), ("Credit score", b["credit_score"]),
             ("Monthly revenue", f"${f['monthly_revenue_k']}k"), ("Debt-to-income", f"{f['debt_to_income']:.0%}"),
             ("Years trading", f["years_in_business"]), ("Missed payments, 2 yrs", b["missed_payments_24m"]),
             ("Identity verified", "Yes" if app["kyc"]["identity_verified"] else "No")]
    cells = "".join(f"<div><div class='k'>{k}</div><div class='v'>{esc(v)}</div></div>" for k, v in facts)
    cells += f"<div><div class='k'>Purpose</div><div style='font-weight:700'>{esc(app['purpose'])}</div></div>"
    st.markdown(f"<div class='outline'><div style='font-size:1.35rem;font-weight:800;margin-bottom:10px'>"
                f"Application: {esc(app['name'])}</div><div class='facts'>{cells}</div>"
                f"<div class='notes'><b>Bank statement notes:</b> {esc(app['bank_notes'])}<br>"
                f"<b>News:</b> {esc(app['news'])}</div></div>", unsafe_allow_html=True)


def three_steps(result, audit, pol):
    blocked = result["by"] == "rules"
    calls = [a for a in audit if a["step"] == "agent_tool_call"]

    if blocked:
        understand = "<p class='q'>Skipped. A hard rule stopped the application before the agent ran.</p>"
    else:
        items = "".join(f"<li>✓ {TOOLS.get(a['tool'], a['tool'])}</li>" for a in calls)
        notes = next((a["result"]["notes"] for a in calls if a["tool"] == "get_bank_transaction_notes"), "")
        flag_html = ("<p style='margin-top:10px'><b>Risk signal found:</b><br>" + highlight(notes, pol["red_flags"])
                     + "</p>") if result.get("red_flags") else \
            "<p style='margin-top:10px'><b>No risk signals</b> in the bank notes or news.</p>"
        understand = f"<p class='q'>The AI agent checked {len(calls)} sources:</p><ul class='checks'>{items}</ul>{flag_html}"

    checks = result.get("rule_checks", [])
    rule_items = "".join(f"<li>{'✗' if c['hit'] else '✓'} {esc(c['rule'])}"
                         f"{' → ' + esc(c['then']) if c['hit'] else ''}</li>" for c in checks)
    decide = f"<p class='q'>Hard rules ({len(checks)} checked):</p><ul class='checks'>{rule_items}</ul>"
    if not blocked:
        p = result["model_score"]
        decide += (f"<p class='q' style='margin:12px 0 0 0'>ML model: chance of repayment</p>"
                   f"<div class='num'>{p:.0%}</div>{gauge(p, pol)}"
                   f"<p style='margin-top:12px'><b>Agent recommends: {esc(result['agent_decision'])}</b> "
                   f"<span class='q'>({result['agent_confidence']:.0%} confident)</span></p>")

    color, label = STATUS[result["final"]]
    who = {"rules": "Decided by the bank's hard rules.",
           "agent": "Decided automatically, within the guardrails.",
           "sent to human": "Routed to the review queue below."}[result["by"]]
    act = (f"<div class='badge' style='background:{color}'>{label}</div><p><b>{who}</b></p>"
           f"<p class='q' style='margin-bottom:2px'>Reasons logged:</p><ul>"
           + "".join(f"<li>{esc(r)}</li>" for r in result["why"])
           + f"</ul><p class='q'>Policy {esc(result.get('policy_version', ''))} · every step saved to the audit trail.</p>")

    st.markdown(f"<div class='panel'>"
                f"<div class='col'><h3>01&nbsp; Understand</h3>{understand}</div>"
                f"<div class='col'><h3>02&nbsp; Decide</h3>{decide}</div>"
                f"<div class='col'><h3>03&nbsp; Act with control</h3>{act}</div></div>", unsafe_allow_html=True)


def review_box(entry):
    """Case Manager: a credit officer resolves cases the system sent to a human."""
    review = next((a for a in entry["audit"] if a["step"] == "human_review"), None)
    st.markdown("<div class='outline'><div class='box-title'>Case manager: credit officer review</div>"
                "The system did not decide this case alone. A human makes the final call, and that "
                "decision is added to the audit trail.</div>", unsafe_allow_html=True)
    if review:
        color, label = STATUS[review["decision"]]
        st.markdown(f"<span class='pill' style='background:{color}'>{label}</span> by "
                    f"<b>{esc(review['reviewer'])}</b> at {review['t'][11:19]}: {esc(review['note'])}",
                    unsafe_allow_html=True)
        return
    a, b, c = st.columns([1.2, 2.5, 1])
    choice = a.radio("Officer decision", ["APPROVE", "DECLINE"], horizontal=True, key=f"rv_{entry['ID']}")
    note = b.text_input("Note for the file", "Checked bank statements with the applicant.", key=f"rn_{entry['ID']}")
    c.write("")
    if c.button("Record decision", type="primary", key=f"rb_{entry['ID']}", width="stretch"):
        mt._log(entry["audit"], "Human review", "human_review", decision=choice, reviewer="Credit officer (demo)",
                note=note)
        entry["Decision"], entry["Decided by"] = choice, "Credit officer"
        st.rerun()


def custom_application():
    st.markdown("<div class='outline' style='margin-bottom:0'><b>Build your own application.</b> "
                "The ML model only sees the numbers. Only the AI agent reads the two text boxes, so try typing "
                "<i>casino</i>, <i>lawsuit</i> or <i>overdraft</i>, or ask for more than the product limit.</div>",
                unsafe_allow_html=True)
    base = mt.APPLICANTS["cafe"]
    a, b = st.columns(2)
    with a:
        name = st.text_input("Business name", base["name"])
        amount = st.slider("Loan requested ($k)", 5, 500, base["amount_k"], step=5)
        score = st.slider("Credit score", 500, 850, base["bureau"]["credit_score"])
        revenue = st.slider("Monthly revenue ($k)", 1, 250, base["financials"]["monthly_revenue_k"])
        dti = st.slider("Debt-to-income (%)", 0, 90, int(base["financials"]["debt_to_income"] * 100))
        years = st.slider("Years in business", 0, 20, base["financials"]["years_in_business"])
    with b:
        notes = st.text_area("Bank statement notes", base["bank_notes"], height=140)
        news = st.text_area("News", base["news"], height=90)
        missed = st.number_input("Missed payments (24 months)", 0, 10, base["bureau"]["missed_payments_24m"])
        kyc_ok = st.checkbox("Identity verified", value=True)
    return {"name": name, "amount_k": amount, "purpose": base["purpose"],
            "bureau": {**base["bureau"], "credit_score": score, "missed_payments_24m": int(missed)},
            "financials": {"monthly_revenue_k": revenue, "debt_to_income": dti / 100, "years_in_business": years},
            "bank_notes": notes, "kyc": {"identity_verified": kyc_ok, "sanctions_hit": False}, "news": news}


def custom_takeaway(result):
    if result["by"] == "rules":
        return "A hard rule decided before any AI ran."
    if result.get("red_flags") and result["final"] == "HUMAN REVIEW":
        return "The agent found a risk signal in the text, so a human makes the call."
    if result["final"] == "HUMAN REVIEW":
        return "Not clear enough to automate, so the case goes to a human."
    return f"A clear case: {STATUS[result['final']][1].lower()} automatically, with the reasons logged."


def flow_dot(pol):
    """Graphviz picture of the decision flow, generated from the policy itself."""
    def lab(s):
        return s.replace('"', "'")
    active = [r for r in pol["rules"] if r.get("active")]
    rule_lines = "\\l".join(lab(f"{r['name']}: {FIELD_LABEL[r['field']].split(' (')[0]} {r['op']} {num(r['value'])} → {r['then']}")
                             for r in active)
    words = ", ".join(pol["red_flags"][:6]) + ("…" if len(pol["red_flags"]) > 6 else "")
    lo, hi = round(pol["decline_at"] * 100), round(pol["approve_at"] * 100)
    review_rules = any(r["then"] == "HUMAN REVIEW" for r in active)
    return f"""digraph {{
rankdir=TB; bgcolor="transparent"; nodesep=0.5; ranksep=0.42;
node [shape=box, style="filled", fillcolor="{NAVY}", fontcolor="{CREAM}", color="{NAVY}", fontname="Inter", fontsize=13, margin="0.2,0.12"];
edge [color="{NAVY}", fontcolor="{NAVY}", fontname="Inter", fontsize=12, penwidth=1.5];
app [label="Application"];
rules [label="Hard rules (decision table)\\l{rule_lines or 'no active rules'}\\l"];
agent [label="AI agent\\l6 data tools\\lwatchlist: {lab(words)}\\l"];
score [shape=diamond, label="Model score", fillcolor="{CREAM}", fontcolor="{NAVY}"];
guard [label="Guardrails\\lconfidence < {pol['min_confidence']:.0%} → human\\lagent vs model conflict → human\\l"];
approve [label="APPROVE", fillcolor="#2E7D4F", color="#2E7D4F", fontcolor="white"];
human [label="HUMAN REVIEW\\n(case manager)", fillcolor="#B86E00", color="#B86E00", fontcolor="white"];
decline [label="DECLINE", fillcolor="#B3261E", color="#B3261E", fontcolor="white"];
app -> rules; rules -> agent [label="all pass"]; rules -> decline [label="DECLINE rule hit"];
{'rules -> human [label="review rule hit", style=dashed];' if review_rules else ''}
agent -> score; score -> decline [label="≤ {lo}%"]; score -> guard [label="> {lo}%"];
guard -> approve [label="≥ {hi}%, no red flag"]; guard -> human [label="red flag or {lo}–{hi}%"];
{{rank=same; approve; human; decline;}}
}}"""


def policy_diff(old, new):
    out = []
    for k, lbl in [("approve_at", "Approve threshold"), ("decline_at", "Decline threshold"),
                   ("min_confidence", "Minimum agent confidence")]:
        if round(old[k], 2) != round(new[k], 2):
            out.append(f"{lbl} {old[k]:.0%} → {new[k]:.0%}")
    added = [w for w in new["red_flags"] if w not in old["red_flags"]]
    removed = [w for w in old["red_flags"] if w not in new["red_flags"]]
    if added:
        out.append("Watchlist + " + ", ".join(added))
    if removed:
        out.append("Watchlist − " + ", ".join(removed))
    old_r = {r["name"]: r for r in old["rules"]}
    new_r = {r["name"]: r for r in new["rules"]}
    for n in new_r:
        if n not in old_r:
            out.append(f"Rule added: {n}")
        elif new_r[n] != old_r[n]:
            o, w = old_r[n], new_r[n]
            if o.get("active") != w.get("active"):
                out.append(f"Rule {'switched on' if w.get('active') else 'switched off'}: {n}")
            if (o["field"], o["op"], o["value"], o["then"]) != (w["field"], w["op"], w["value"], w["then"]):
                out.append(f"Rule changed: {n} ({w['field']} {w['op']} {num(w['value'])} → {w['then']})")
    for n in old_r:
        if n not in new_r:
            out.append(f"Rule removed: {n}")
    return out


def describe(a):
    """Plain-language line for one audit step."""
    s = a["step"]
    if s == "received":
        return f"Application received: {a['applicant']}, ${a['amount_k']}k, under policy {a.get('policy_version', '')}"
    if s == "rules_evaluated":
        hits = [c for c in a["checks"] if c["hit"]]
        txt = f"{len(a['checks'])} hard rules checked"
        return txt + (": " + "; ".join(f"{c['rule']} hit ({c['condition']}, actual {c['actual']}) → {c['then']}"
                                       for c in hits) if hits else ", all passed")
    if s == "agent_tool_call":
        return f"Agent called {TOOLS.get(a['tool'], a['tool'])}"
    if s == "agent_recommendation":
        flags = f"; red flags: {', '.join(a.get('red_flags', []))}" if a.get("red_flags") else ""
        return f"Agent recommends {a['decision']} ({a.get('confidence', 0):.0%} confident){flags}"
    if s == "guardrails_triggered":
        return "Guardrails triggered: " + "; ".join(a["triggered"])
    if s == "guardrails_passed":
        return "Guardrails passed"
    if s == "final":
        return f"System decision: {a['decision']} (by {a['decided_by']})"
    if s == "human_review":
        return f"{a['reviewer']} decided {a['decision']}: “{a['note']}”"
    return s


# ---------------------------------------------------------------- page header
st.markdown("<div class='topbar'><span>FIN3090 AI Application in Finance</span><span>20 OCT 2026</span></div>",
            unsafe_allow_html=True)
st.markdown(f"<div class='title-row'><div><div class='big'>LIVE DEMO:</div>"
            f"<div class='sub'>Mini Taktile: Run a Case, Change the Rules, Check the Audit Trail</div>"
            f"<div class='lead'>Risk teams build the decision flow without code, AI agents do the checking, "
            f"and every decision is recorded. Published policy: <b>{vname()}</b>.</div></div>"
            f"<img src='data:image/png;base64,{STAR}' style='width:120px'></div>", unsafe_allow_html=True)

tab_run, tab_flow, tab_audit = st.tabs(["01 Run a case", "02 Decision flow (no-code)", "03 Audit trail"])

# ================================================================ TAB 1: run a case
with tab_run:
    labels = [c[1] for c in CASES] + [CUSTOM]
    if ss.get("case") is None:  # clicking the selected pill again would clear it
        ss["case"] = ss.get("last_case", labels[1])
    pick = st.segmented_control("Applicant", labels, key="case", label_visibility="collapsed")
    ss["last_case"] = pick

    if pick == CUSTOM:
        app, takeaway = custom_application(), None
    else:
        app_id, _, takeaway = CASES[labels.index(pick)]
        app = mt.APPLICANTS[app_id]
        application_box(app)

    entry = run_and_log(app)
    three_steps(entry["result"], entry["audit"], ss.policy)
    if entry["result"]["final"] == "HUMAN REVIEW":
        review_box(entry)
    st.markdown(f"<p class='takeaway'>Takeaway: {esc(takeaway or custom_takeaway(entry['result']))}</p>",
                unsafe_allow_html=True)
    st.caption(f"Decision {entry['ID']} · see tab 03 for its full audit trail.")

# ================================================================ TAB 2: no-code decision flow
with tab_flow:
    g = ss.editor_gen
    st.markdown("<div class='lead' style='margin:6px 0 4px 0'>This is how a risk team works in a decision platform: "
                "change the rules in tables and sliders, <b>test the draft on past applications</b>, then "
                "<b>publish</b> it as a new version. No engineer and no code needed.</div>", unsafe_allow_html=True)

    left, right = st.columns([0.9, 1.25])
    with right:
        st.markdown("<div class='box-title' style='margin-top:10px'>Step 1 · Hard rules (decision table)</div>",
                    unsafe_allow_html=True)
        st.caption("Checked top to bottom before any AI runs. DECLINE stops the flow; HUMAN REVIEW flags the case. "
                   "Add a row at the bottom to create a rule.")
        rules_df = pd.DataFrame([{"On": r["active"], "Rule": r["name"], "If field": FIELD_LABEL[r["field"]],
                                  "Is": r["op"], "Value": float(r["value"]), "Then": r["then"]}
                                 for r in ss.policy["rules"]])
        edited = st.data_editor(
            rules_df, key=f"rules_{g}", num_rows="dynamic", hide_index=True, width="stretch",
            column_config={
                "On": st.column_config.CheckboxColumn(width="small", default=True),
                "Rule": st.column_config.TextColumn(required=True, width="medium"),
                "If field": st.column_config.SelectboxColumn(options=list(LABEL_FIELD), required=True, width="medium"),
                "Is": st.column_config.SelectboxColumn(options=list(mt.OPS), width="small", required=True),
                "Value": st.column_config.NumberColumn(width="small", required=True),
                "Then": st.column_config.SelectboxColumn(options=["DECLINE", "HUMAN REVIEW"], required=True, width="medium"),
            })
        st.markdown("<div class='box-title' style='margin-top:6px'>Step 2 · Model score thresholds</div>",
                    unsafe_allow_html=True)
        lo, hi = st.slider("Decline at or below / approve at or above (%)", 0, 100,
                           (round(ss.policy["decline_at"] * 100), round(ss.policy["approve_at"] * 100)),
                           key=f"thr_{g}")
        st.markdown("<div class='box-title' style='margin-top:6px'>Step 3 · AI agent watchlist</div>",
                    unsafe_allow_html=True)
        words = st.text_input("Words the agent treats as red flags in bank notes and news (comma-separated)",
                              ", ".join(ss.policy["red_flags"]), key=f"words_{g}")
        st.markdown("<div class='box-title' style='margin-top:6px'>Step 4 · Guardrail</div>", unsafe_allow_html=True)
        conf = st.slider("Send to a human if the agent's confidence is below (%)", 0, 100,
                         round(ss.policy["min_confidence"] * 100), key=f"conf_{g}")

    draft = {"rules": [], "approve_at": hi / 100, "decline_at": lo / 100, "min_confidence": conf / 100,
             "red_flags": [w.strip().lower() for w in words.split(",") if w.strip()]}
    for _, row in edited.iterrows():
        if isinstance(row.get("Rule"), str) and row.get("If field") in LABEL_FIELD and row.get("Is") in mt.OPS \
                and pd.notna(row.get("Value")) and row.get("Then") in ("DECLINE", "HUMAN REVIEW"):
            draft["rules"].append({"active": bool(row["On"]) if pd.notna(row["On"]) else True, "name": row["Rule"],
                                   "field": LABEL_FIELD[row["If field"]], "op": row["Is"],
                                   "value": float(row["Value"]), "then": row["Then"]})
    for r in ss.policy["rules"]:  # keep integer display for unchanged values
        r["value"] = float(r["value"])
    changes = policy_diff(ss.policy, draft)

    with left:
        st.markdown(f"<div class='box-title' style='margin-top:10px'>Decision flow · "
                    f"{'draft (unpublished changes)' if changes else 'published ' + vname()}</div>",
                    unsafe_allow_html=True)
        st.graphviz_chart(flow_dot(draft), width="stretch")
        st.caption("The picture is generated from the rules on the right, so it updates as you edit.")

    st.markdown("<div class='box-title' style='margin-top:14px'>Test before you publish: shadow test on all "
                "applicants</div>", unsafe_allow_html=True)
    st.caption("Runs every applicant through the published policy and the draft side by side (offline agent), "
               "so you see what a change would do before it goes live.")
    rows = []
    for app_id, label, _ in CASES:
        a_pub, _ = mt.decide_app(mt.APPLICANTS[app_id], False, policy=ss.policy, version=vname())
        a_new, _ = mt.decide_app(mt.APPLICANTS[app_id], False, policy=draft, version="draft")
        rows.append({"Applicant": label, f"Published {vname()}": a_pub["final"], "Draft": a_new["final"],
                     "Changed?": "CHANGED" if a_pub["final"] != a_new["final"] else "same"})
    shadow = pd.DataFrame(rows)
    st.dataframe(shadow.style.apply(lambda r: ["background-color:#F6D7C8; font-weight:700"] * len(r)
                                    if r["Changed?"] == "CHANGED" else [""] * len(r), axis=1),
                 hide_index=True, width="stretch")

    if changes:
        st.markdown("<div class='outline'><div class='box-title'>Unpublished changes</div>" +
                    "".join(f"• {esc(c)}<br>" for c in changes) + "</div>", unsafe_allow_html=True)
    b1, b2, _ = st.columns([1.3, 1, 3])
    if b1.button(f"Publish as v{ss.version + 1}", type="primary", disabled=not changes, width="stretch"):
        ss.policy = draft
        ss.version += 1
        ss.history.append({"Version": vname(), "Published": datetime.now().strftime("%H:%M:%S"),
                           "By": "Risk team (demo)", "Changes": "; ".join(changes)})
        ss.editor_gen += 1
        st.rerun()
    if b2.button("Discard draft", disabled=not changes, width="stretch"):
        ss.editor_gen += 1
        st.rerun()

# ================================================================ TAB 3: audit trail
with tab_audit:
    st.markdown("<div class='lead' style='margin:6px 0 8px 0'>Every decision is stored with each step, its time, "
                "the policy version it used and any human review. This is what an auditor or regulator asks "
                "for: <b>who decided what, when, and why</b>.</div>", unsafe_allow_html=True)
    if not ss.log:
        st.info("No decisions yet. Run a case in tab 01.")
    else:
        log_df = pd.DataFrame([{k: e[k] for k in ["ID", "Time", "Applicant", "Decision", "Decided by", "Policy",
                                                  "Agent"]} | {"Model score": f"{e['Model score']:.0%}"
                                                               if e["Model score"] is not None else "n/a"}
                               for e in reversed(ss.log)])
        st.markdown("<div class='box-title'>Decision log</div>", unsafe_allow_html=True)
        st.dataframe(log_df, hide_index=True, width="stretch")

        options = [f"{e['ID']} · {e['Applicant']} · {e['Policy']}" for e in reversed(ss.log)]
        sel = st.selectbox("Open a decision", options)
        e = ss.log[int(sel.split(" ")[0][2:]) - 1]
        c1, c2 = st.columns([1.6, 1])
        with c1:
            st.markdown(f"<div class='box-title' style='margin-top:6px'>Audit trail for {e['ID']}</div>",
                        unsafe_allow_html=True)
            items = "".join(f"<div class='tl-item'><span class='tl-time'>{a['t'][11:23]}</span>"
                            f"<span class='tl-layer'>{esc(a['layer'])}</span>"
                            f"<span class='tl-what'>{esc(describe(a))}</span></div>" for a in e["audit"])
            st.markdown(f"<div class='tl'>{items}</div>", unsafe_allow_html=True)
        with c2:
            color, label = STATUS[e["Decision"]]
            st.markdown(f"<div class='outline'><div class='box-title'>Summary</div>"
                        f"<span class='pill' style='background:{color}'>{label}</span><br><br>"
                        f"<b>Applicant:</b> {esc(e['Applicant'])}<br><b>Decided by:</b> {esc(e['Decided by'])}<br>"
                        f"<b>Policy version:</b> {e['Policy']}<br><b>Agent:</b> {e['Agent']}<br>"
                        f"<b>Steps recorded:</b> {len(e['audit'])}</div>", unsafe_allow_html=True)
            st.download_button(f"Download {e['ID']} audit (JSON)", json.dumps(e["audit"], indent=2),
                               file_name=f"{e['ID']}_audit.json", mime="application/json", width="stretch")
            st.download_button("Download decision log (CSV)", log_df.to_csv(index=False),
                               file_name="decision_log.csv", mime="text/csv", width="stretch")
        with st.expander("Raw audit record (JSON)"):
            st.json(e["audit"])

    st.markdown("<div class='box-title' style='margin-top:16px'>Policy change history</div>", unsafe_allow_html=True)
    st.dataframe(pd.DataFrame(list(reversed(ss.history))), hide_index=True, width="stretch")

st.markdown(f"<p class='q' style='font-size:.8rem;margin-top:14px'>Agent: "
            f"{'Claude (' + mt.MODEL_NAME + ')' if use_llm else 'offline stand-in'} · synthetic data · "
            f"a classroom illustration, not Taktile's code.</p><div class='pageno'>17</div>", unsafe_allow_html=True)
