"""
app.py - Mini Taktile live demo, styled to match the FIN3090 Taktile deck.

    pip install -r requirements.txt
    streamlit run app.py

Pick an applicant (or build your own) and the page shows the deck's three
steps - 01 Understand, 02 Decide, 03 Act with control - filled in live.

Without an API key the offline stand-in agent runs, so the demo never breaks.
The settings sidebar (agent choice, API key) starts collapsed: open it with
the arrow at the top left.
"""

import base64
import html
import json
import os
from pathlib import Path

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
.title-row {{ display:flex; justify-content:space-between; align-items:center; margin: .4rem 0 1.0rem 0; }}
.big {{ color:{NAVY}; font-size: 4.6rem; font-weight: 800; line-height: 1; letter-spacing:-1px; margin:0; }}
.sub {{ color:{NAVY}; font-size: 1.9rem; font-weight: 700; margin: .35rem 0 0 0; }}
.lead {{ color:{NAVY}; font-size: 1.1rem; margin-top:.5rem; max-width: 900px; }}
[data-testid="stButtonGroup"] button {{ border: 2px solid {NAVY}; font-weight: 600; padding: .3rem 1rem; }}
[data-testid="stButtonGroup"] button[aria-checked="true"] {{ background:{NAVY} !important; }}
[data-testid="stButtonGroup"] button[aria-checked="true"] * {{ color:{CREAM} !important; }}

.outline {{ border: 2px solid {NAVY}; padding: 18px 22px; margin: 14px 0; }}
.facts {{ display:grid; grid-template-columns: repeat(4, 1fr); gap: 4px 24px; }}
.facts .k {{ font-size:.85rem; }} .facts .v {{ font-size:1.35rem; font-weight:800; }}
.notes {{ margin-top:12px; padding-top:10px; border-top:1px solid {NAVY}33; font-size:.95rem; }}
.flag, .col .flag {{ background:#FFC9A8; color:{NAVY} !important; padding:0 4px; font-weight:700; }}

.panel {{ background:{NAVY}; display:grid; grid-template-columns: 1fr 1fr 1fr; padding: 28px 8px; margin-top: 6px; }}
.col {{ padding: 4px 26px; border-left: 2px solid {CREAM}; }}
.col:first-child {{ border-left: none; }}
.col h3 {{ color:{CREAM} !important; font-size:1.55rem; font-weight:800; margin:0 0 14px 0; padding:0; }}
.col p, .col li, .col span, .col div {{ color:{CREAM}; }}
.col .q {{ color:{SOFT} !important; font-size:.92rem; }}
.col ul {{ padding-left: 1.1rem; margin: 6px 0; }} .col ul.checks {{ list-style:none; padding-left:0; }} .col li {{ margin: 3px 0; font-size:.98rem; }}
.col .num {{ font-size: 3.4rem; font-weight: 800; line-height: 1; }}
.gauge {{ display:flex; height:14px; margin:8px 0 2px 0; position:relative; }}
.gauge div {{ height:100%; }}
.marker {{ position:absolute; top:-6px; width:4px; height:26px; background:{CREAM}; margin-left:-2px; }}
.ticks {{ position:relative; height:16px; font-size:.75rem; }}
.ticks span {{ position:absolute; color:{SOFT} !important; }}
.badge {{ display:inline-block; padding: 8px 14px; font-weight:800; font-size:1.35rem; color:white !important;
  margin: 2px 0 10px 0; }}
.takeaway {{ font-weight:800; font-size:1.2rem; margin: 22px 0 10px 0 !important; }}
.pageno {{ text-align:right; font-size:.9rem; margin-top: 8px; }}
[data-testid="stExpander"] {{ border: 2px solid {NAVY}; border-radius:0; background: transparent; }}
.stSlider [data-baseweb="slider"] div[role="slider"] {{ background:{NAVY}; }}
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


def highlight(text):
    out = esc(text)
    for w in mt.RED_FLAG_WORDS:
        for v in {w, w.capitalize()}:
            out = out.replace(v, f"<span class='flag'>{v}</span>")
    return out


def run_case(app):
    key = json.dumps(app, sort_keys=True) + str(use_llm)
    cache = st.session_state.setdefault("cache", {})
    if key not in cache:
        with st.spinner("The AI agent is checking the data sources…"):
            try:
                cache[key] = mt.decide_app(app, use_llm, api_key)
            except Exception as e:
                st.error(f"Claude agent failed ({type(e).__name__}); using the offline agent.")
                cache[key] = mt.decide_app(app, False)
    return cache[key]


def gauge(p):
    pct = round(p * 100)
    return (f"<div class='gauge'><div style='width:40%;background:#B98A86'></div>"
            f"<div style='width:35%;background:#C9A35B'></div><div style='width:25%;background:#7FA88B'></div>"
            f"<div class='marker' style='left:{pct}%'></div></div>"
            f"<div class='ticks'><span style='left:0'>decline</span>"
            f"<span style='left:40%;transform:translateX(-50%)'>review</span>"
            f"<span style='right:0'>approve</span></div>")


def application_box(app):
    b, f = app["bureau"], app["financials"]
    facts = [("Loan requested", f"${app['amount_k']}k"), ("Credit score", b["credit_score"]),
             ("Monthly revenue", f"${f['monthly_revenue_k']}k"), ("Debt-to-income", f"{f['debt_to_income']:.0%}"),
             ("Years trading", f["years_in_business"]), ("Missed payments, 2 yrs", b["missed_payments_24m"]),
             ("Identity verified", "Yes" if app["kyc"]["identity_verified"] else "No"), ("Purpose", app["purpose"])]
    cells = "".join(f"<div><div class='k'>{k}</div><div class='v'>{esc(v)}</div></div>" for k, v in facts[:7])
    cells += f"<div><div class='k'>Purpose</div><div style='font-weight:700'>{esc(app['purpose'])}</div></div>"
    st.markdown(f"<div class='outline'><div style='font-size:1.45rem;font-weight:800;margin-bottom:10px'>"
                f"Application: {esc(app['name'])}</div><div class='facts'>{cells}</div>"
                f"<div class='notes'><b>Bank statement notes:</b> {esc(app['bank_notes'])}<br>"
                f"<b>News:</b> {esc(app['news'])}</div></div>", unsafe_allow_html=True)


def three_steps(app, result, audit):
    blocked = result["by"] == "rules"
    calls = [a for a in audit if a["step"] == "agent_tool_call"]

    # 01 Understand
    if blocked:
        understand = ("<p class='q'>Skipped. A hard rule stopped the application before the agent ran, "
                      "so no data was pulled.</p>")
    else:
        items = "".join(f"<li>✓ {TOOLS.get(a['tool'], a['tool'])}</li>" for a in calls)
        flags = result.get("red_flags") or []
        notes = next((a["result"]["notes"] for a in calls if a["tool"] == "get_bank_transaction_notes"), "")
        flag_html = ("<p style='margin-top:10px'><b>Risk signal found:</b><br>" + highlight(notes) + "</p>") if flags \
            else "<p style='margin-top:10px'><b>No risk signals</b> in the bank notes or news.</p>"
        understand = f"<p class='q'>The AI agent checked {len(calls)} sources:</p><ul class='checks'>{items}</ul>{flag_html}"

    # 02 Decide
    rules_line = (f"<p><b>Hard rules: BLOCKED</b><br>{esc(result['why'][0])}</p>" if blocked
                  else "<p><b>Hard rules: passed</b><br><span class='q'>Amount limit, identity, sanctions</span></p>")
    if blocked:
        decide = rules_line + "<p class='q'>The ML model and the agent were not needed.</p>"
    else:
        p = result["model_score"]
        decide = (rules_line +
                  f"<p class='q' style='margin:12px 0 0 0'>ML model: chance of repayment</p>"
                  f"<div class='num'>{p:.0%}</div>{gauge(p)}"
                  f"<p style='margin-top:12px'><b>Agent recommends: {esc(result['agent_decision'])}</b> "
                  f"<span class='q'>({result['agent_confidence']:.0%} confident)</span></p>")

    # 03 Act with control
    color, label = STATUS[result["final"]]
    who = {"rules": "Decided by the bank's hard rules.",
           "agent": "Decided automatically, within the guardrails.",
           "sent to human": "A credit officer makes the final call."}[result["by"]]
    reasons = [r for r in result["why"] if not r.startswith("Guardrail")]
    guard = result.get("guardrails") or []
    act = (f"<div class='badge' style='background:{color}'>{label}</div><p><b>{who}</b></p>"
           f"<p class='q' style='margin-bottom:2px'>Reasons logged:</p><ul>"
           + "".join(f"<li>{esc(r)}</li>" for r in reasons)
           + "".join(f"<li>{esc(g)}</li>" for g in guard)
           + "</ul><p class='q'>Every step is saved to the audit trail.</p>")

    st.markdown(f"<div class='panel'>"
                f"<div class='col'><h3>01&nbsp; Understand</h3>{understand}</div>"
                f"<div class='col'><h3>02&nbsp; Decide</h3>{decide}</div>"
                f"<div class='col'><h3>03&nbsp; Act with control</h3>{act}</div></div>", unsafe_allow_html=True)


def custom_application():
    st.markdown("<div class='outline' style='margin-bottom:0'><b>Build your own application.</b> "
                "The ML model only sees the numbers. Only the AI agent reads the two text boxes, so try typing "
                "<i>casino</i>, <i>lawsuit</i> or <i>overdraft</i>, or ask for more than $250k.</div>",
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
        kyc_ok = st.checkbox("Identity verified", value=True)
    return {"name": name, "amount_k": amount, "purpose": base["purpose"],
            "bureau": {**base["bureau"], "credit_score": score},
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


# ---------------------------------------------------------------- page
st.markdown("<div class='topbar'><span>FIN3090 AI Application in Finance</span><span>20 OCT 2026</span></div>",
            unsafe_allow_html=True)
st.markdown(f"<div class='title-row'><div><div class='big'>LIVE DEMO:</div>"
            f"<div class='sub'>Mini Taktile: One Loan, Three Steps</div>"
            f"<div class='lead'>A small-business loan goes through the same three steps as Taktile's platform. "
            f"Pick an applicant to see what the AI agent finds, what it decides, and when a human takes over.</div></div>"
            f"<img src='data:image/png;base64,{STAR}' style='width:150px'></div>", unsafe_allow_html=True)

labels = [c[1] for c in CASES] + [CUSTOM]
# Clicking the selected pill again would clear it; restore the last choice so one case is always on screen.
if st.session_state.get("case") is None:
    st.session_state["case"] = st.session_state.get("last_case", labels[1])
pick = st.segmented_control("Applicant", labels, key="case", label_visibility="collapsed")
st.session_state["last_case"] = pick

if pick == CUSTOM:
    app = custom_application()
    takeaway = None
else:
    app_id, _, takeaway = CASES[labels.index(pick)]
    app = mt.APPLICANTS[app_id]
    application_box(app)

result, audit = run_case(app)
three_steps(app, result, audit)
st.markdown(f"<p class='takeaway'>Takeaway: {esc(takeaway or custom_takeaway(result))}</p>", unsafe_allow_html=True)

with st.expander("Audit trail: what a regulator would see"):
    st.json(audit)
    st.download_button("Download audit_log.json", json.dumps(audit, indent=2), file_name="audit_log.json",
                       mime="application/json")

st.markdown(f"<p class='q' style='font-size:.8rem;margin-top:10px'>Agent: "
            f"{'Claude (' + mt.MODEL_NAME + ')' if use_llm else 'offline stand-in'} · synthetic data · "
            f"a classroom illustration, not Taktile's code.</p><div class='pageno'>18</div>", unsafe_allow_html=True)
