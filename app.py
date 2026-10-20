"""
app.py - Streamlit front end for mini_taktile.py

    pip install streamlit numpy scikit-learn anthropic altair pandas
    streamlit run app.py

Three tabs:
  Beat the AI      the classroom game: vote, then reveal what the system decides
  Try your own     sliders and text boxes; watch the decision change live
  How it works     the 5 layers, mapped to Taktile's real platform

Without an API key the offline stand-in agent runs, so the demo never breaks.
"""

import json
import os

import altair as alt
import pandas as pd
import streamlit as st

import mini_taktile as mt

st.set_page_config(page_title="Mini Taktile", page_icon="🏦", layout="wide")

# ---------------------------------------------------------------- look & feel
NAVY, CREAM, ORANGE = "#14182B", "#F6F4EE", "#FF6B35"
DECISION_STYLE = {
    "APPROVE": ("#2E7D4F", "✅", "Approved automatically"),
    "DECLINE": ("#B3261E", "⛔", "Declined"),
    "HUMAN REVIEW": ("#B86E00", "🧑‍💼", "Sent to a human"),
}
st.markdown(f"""
<style>
.block-container {{padding-top: 1.6rem;}}
.stage {{border-radius: 14px; padding: 14px 12px; min-height: 128px; border: 2px solid #E2DED3;
         background: #FFFDF8;}}
.stage h4 {{margin: 0 0 4px 0; font-size: 1.0rem;}}
.stage .num {{font-size: .8rem; letter-spacing: 2px; text-transform: uppercase; opacity: .7;}}
.stage .st {{font-size: .92rem; margin-top: 6px; line-height: 1.35;}}
.arrow {{text-align: center; font-size: 1.6rem; padding-top: 44px; color: #9AA0B4;}}
.badge {{border-radius: 16px; padding: 18px 22px; color: white; font-size: 1.6rem; font-weight: 700;}}
.badge small {{display: block; font-size: .95rem; font-weight: 400; opacity: .92; margin-top: 4px;}}
.card {{border-radius: 16px; padding: 20px 24px; background: #FFFDF8; border: 2px solid #E2DED3;}}
.card h3 {{margin-top: 0;}}
.fine {{font-size: .82rem; color: #5A6075; border-top: 1px dashed #D8D3C5; margin-top: 10px; padding-top: 8px;}}
.lesson {{border-left: 6px solid {ORANGE}; background: {NAVY}; color: {CREAM}; padding: 14px 18px;
          border-radius: 10px; font-size: 1.08rem;}}
.flag {{background: #FFE3D6; padding: 0 4px; border-radius: 4px; font-weight: 600;}}
</style>
""", unsafe_allow_html=True)

BY_TEXT = {
    "rules": "Decided by the bank's hard rules, before the AI even ran",
    "agent": "Decided automatically by the AI agent, within the guardrails",
    "sent to human": "The AI was not sure enough: a credit officer makes the final call",
}
GAME_CARDS = [
    ("bookshop", "Card 1", "Easy, clear cases are automated: no human time spent."),
    ("bakery", "Card 2", "The trap. Great numbers, but the agent read the bank notes and caught what the model can't see."),
    ("cafe", "Card 3", "Borderline cases go to a person, not a coin flip."),
    ("bigbuild", "Card 4", "Hard rules beat even a perfect score. The AI cannot override them."),
    ("florist", "Bonus", "Clear declines are automated too."),
]
TOOL_LABELS = {
    "get_credit_report": ("📄", "Credit bureau"), "get_financials": ("📊", "Financials"),
    "get_bank_transaction_notes": ("🏦", "Bank notes"), "check_kyc": ("🪪", "Identity / sanctions"),
    "search_news": ("📰", "News search"), "get_risk_model_score": ("🤖", "ML risk model"),
}

# ---------------------------------------------------------------- sidebar
with st.sidebar:
    st.header("⚙️ Settings")
    engine = st.radio("Which AI agent?", ["Offline stand-in (no key needed)", "Claude agent (needs API key)"],
                      help="The offline agent follows the same steps with keyword checks. "
                           "The Claude agent really reads the text and reasons about it.")
    api_key = None
    if engine.startswith("Claude"):
        api_key = st.text_input("Anthropic API key", type="password",
                                value=os.environ.get("ANTHROPIC_API_KEY", ""))
        st.caption(f"Model: `{mt.MODEL_NAME}`. Each run costs a few API calls.")
        if not api_key:
            st.warning("No key yet: falling back to the offline agent.")
    use_llm = bool(api_key)
    st.divider()
    show_notes = st.toggle("Show presenter notes", value=False)
    st.caption("A classroom illustration of an agentic decision platform. Not Taktile's code.")


# ---------------------------------------------------------------- helpers
def run_case(app: dict):
    """Cache results per application so Streamlit reruns don't repeat API calls."""
    key = json.dumps(app, sort_keys=True) + str(use_llm)
    cache = st.session_state.setdefault("cache", {})
    if key not in cache:
        with st.spinner("The agent is checking the data sources…" if use_llm else "Running…"):
            try:
                cache[key] = mt.decide_app(app, use_llm, api_key)
            except Exception as e:  # bad key, no network, etc.
                st.error(f"Claude agent failed ({type(e).__name__}); using the offline agent instead.")
                cache[key] = mt.decide_app(app, False)
    return cache[key]


def stage_html(num, title, status, color):
    return (f"<div class='stage' style='border-color:{color}'>"
            f"<div class='num'>Step {num}</div><h4>{title}</h4>"
            f"<div class='st' style='color:{color}'>{status}</div></div>")


def pipeline(result, audit):
    """Five boxes: what happened at each layer, coloured by outcome."""
    grey, ok, warn, bad = "#9AA0B4", "#2E7D4F", "#B86E00", "#B3261E"
    blocked = result["by"] == "rules"
    calls = [a for a in audit if a["step"] == "agent_tool_call"]
    final_c = DECISION_STYLE[result["final"]][0]
    stages = [
        ("📥 Application", "Received", ok),
        ("📏 Hard rules", "❌ " + result["why"][0] if blocked else "Passed: amount, ID, sanctions", bad if blocked else ok),
        ("🤖 AI agent", "Skipped: rules already decided" if blocked else
         f"Checked {len(calls)} sources → recommends <b>{result['agent_decision']}</b> "
         f"({result['agent_confidence']:.0%} sure)", grey if blocked else (warn if result.get('red_flags') else ok)),
        ("🛡️ Guardrails", "Skipped" if blocked else
         ("Triggered: " + "; ".join(g.replace("Guardrail: ", "") for g in result["guardrails"]))
         if result.get("guardrails") else "No conflict found", grey if blocked else (warn if result.get("guardrails") else ok)),
        ("🏁 Decision", f"<b>{result['final']}</b>", final_c),
    ]
    cols = st.columns([5, 1, 5, 1, 5, 1, 5, 1, 5])
    for i, (title, status, color) in enumerate(stages):
        cols[i * 2].markdown(stage_html(i + 1, title, status, color), unsafe_allow_html=True)
        if i < 4:
            cols[i * 2 + 1].markdown("<div class='arrow'>➜</div>", unsafe_allow_html=True)


def score_gauge(p):
    """HTML gauge: three decision zones on a 0-100% bar, with a marker at the model's score."""
    pct = round(p * 100)
    align = "translateX(-100%)" if pct > 85 else ("translateX(0)" if pct < 15 else "translateX(-50%)")
    return f"""
<div style='margin:6px 0 4px 0'>
  <div style='position:relative;height:34px'>
    <div style='position:absolute;left:{pct}%;transform:{align};bottom:12px;font-weight:700;color:{NAVY};
                white-space:nowrap'>ML model: {pct}%</div>
    <div style='position:absolute;left:{pct}%;transform:translateX(-50%);bottom:0;width:0;height:0;
                border-left:9px solid transparent;border-right:9px solid transparent;border-top:12px solid {NAVY}'></div>
  </div>
  <div style='position:relative;display:flex;height:40px;border-radius:8px;overflow:hidden;font-size:.86rem;color:#3A3F52'>
    <div style='width:40%;background:#F3C9C5;display:flex;align-items:center;justify-content:center'>Decline zone</div>
    <div style='width:35%;background:#F6DFB5;display:flex;align-items:center;justify-content:center'>Human review zone</div>
    <div style='width:25%;background:#C6E3CF;display:flex;align-items:center;justify-content:center'>Approve zone</div>
    <div style='position:absolute;left:{pct}%;top:0;bottom:0;width:4px;margin-left:-2px;background:{NAVY}'></div>
  </div>
  <div style='position:relative;height:18px;font-size:.78rem;color:#6A7085;margin-top:3px'>
    <span style='position:absolute;left:0'>0%</span>
    <span style='position:absolute;left:40%;transform:translateX(-50%)'>40%</span>
    <span style='position:absolute;left:75%;transform:translateX(-50%)'>75%</span>
    <span style='position:absolute;right:0'>100%</span>
  </div>
  <div style='font-size:.8rem;color:#6A7085;text-align:center'>Chance the loan is repaid, from the numbers only</div>
</div>"""


def highlight(text):
    for w in mt.RED_FLAG_WORDS:
        for variant in {w, w.capitalize()}:
            text = text.replace(variant, f"<span class='flag'>{variant}</span>")
    return text


def agent_trace(audit):
    calls = [a for a in audit if a["step"] == "agent_tool_call"]
    if not calls:
        st.info("The agent never ran: a hard rule decided first.")
        return
    for a in calls:
        icon, label = TOOL_LABELS.get(a["tool"], ("🔧", a["tool"]))
        r = a["result"]
        if "notes" in r:
            body = highlight(r["notes"])
        elif "results" in r:
            body = highlight(r["results"])
        else:
            body = " · ".join(f"{k.replace('_', ' ')}: <b>{v}</b>" for k, v in r.items())
        st.markdown(f"{icon} **{label}** &nbsp; <code>{a['tool']}()</code><br>"
                    f"<span style='color:#4A5068'>{body}</span>", unsafe_allow_html=True)


def show_result(result, audit, lesson=None, key="main"):
    color, icon, sub = DECISION_STYLE[result["final"]]
    st.markdown(f"<div class='badge' style='background:{color}'>{icon} {result['final']}"
                f"<small>{BY_TEXT[result['by']]}</small></div>", unsafe_allow_html=True)
    st.write("")
    pipeline(result, audit)
    st.write("")
    left, right = st.columns([3, 2])
    with left:
        if "model_score" in result:
            st.markdown(score_gauge(result["model_score"]), unsafe_allow_html=True)
        st.markdown("**Why**")
        for r in result["why"]:
            st.markdown(f"- {r}")
        for f in result.get("red_flags", []):
            st.markdown(f"- 🚩 **Red flag:** {f}")
    with right:
        with st.container(border=True):
            st.markdown("**🔎 What the agent looked at**")
            agent_trace(audit)
    if lesson:
        st.markdown(f"<div class='lesson'>💡 {lesson}</div>", unsafe_allow_html=True)
    with st.expander("📜 Audit trail (what a regulator would see)"):
        st.json(audit)
        st.download_button("Download audit_log.json", json.dumps(audit, indent=2),
                           file_name="audit_log.json", mime="application/json", key=f"dl_{key}")


def application_card(app):
    b, f = app["bureau"], app["financials"]
    st.markdown(f"""
<div class='card'>
<h3>{app['name']}</h3>
<p><b>Asks for:</b> ${app['amount_k']}k &nbsp;·&nbsp; <b>Purpose:</b> {app['purpose']}</p>
<table style='width:100%; font-size:1.02rem'>
<tr><td>💳 Credit score</td><td><b>{b['credit_score']}</b></td>
    <td>📅 Years trading</td><td><b>{f['years_in_business']}</b></td></tr>
<tr><td>💰 Monthly revenue</td><td><b>${f['monthly_revenue_k']}k</b></td>
    <td>⚖️ Debt-to-income</td><td><b>{f['debt_to_income']:.0%}</b></td></tr>
<tr><td>⏰ Missed payments (2 yrs)</td><td><b>{b['missed_payments_24m']}</b></td>
    <td>🪪 Identity checked</td><td><b>{'Yes' if app['kyc']['identity_verified'] else 'No'}</b></td></tr>
</table>
<div class='fine'><b>Bank statement notes:</b> {app['bank_notes']}<br><b>News:</b> {app['news']}</div>
</div>""", unsafe_allow_html=True)


# ---------------------------------------------------------------- page
st.markdown(f"<h1 style='margin-bottom:0'>🏦 Mini Taktile</h1>"
            f"<p style='font-size:1.15rem;color:#4A5068;margin-top:4px'>How an AI agent, hard rules and a human "
            f"decide on a small-business loan. Agent: <b>{'Claude' if use_llm else 'offline stand-in'}</b></p>",
            unsafe_allow_html=True)

tab_game, tab_try, tab_how = st.tabs(["🎮 Beat the AI", "🧪 Try your own application", "🧩 How it works"])

# ---------------- Tab 1: the game
with tab_game:
    labels = [f"{c[1]}: {mt.APPLICANTS[c[0]]['name']}" for c in GAME_CARDS]
    pick = st.radio("Choose a card", labels, horizontal=True, label_visibility="collapsed")
    app_id, card_name, lesson = GAME_CARDS[labels.index(pick)]
    app = mt.APPLICANTS[app_id]

    c1, c2 = st.columns([3, 2])
    with c1:
        application_card(app)
    with c2:
        st.markdown("#### 🗳️ What would you decide?")
        st.caption("Count the room's votes (or a Mentimeter result), then reveal.")
        v = st.session_state.setdefault("votes", {}).setdefault(app_id, {"APPROVE": 0, "DECLINE": 0, "HUMAN REVIEW": 0})
        for opt, lbl in [("APPROVE", "✅ Approve"), ("DECLINE", "⛔ Decline"), ("HUMAN REVIEW", "🧑‍💼 Send to a human")]:
            v[opt] = st.number_input(lbl, min_value=0, step=1, value=v[opt], key=f"v_{app_id}_{opt}")
        revealed = st.session_state.setdefault("revealed", set())
        b1, b2 = st.columns(2)
        if b1.button("🎬 Reveal answer", type="primary", width="stretch", key=f"rev_{app_id}"):
            revealed.add(app_id)
        if b2.button("↺ Hide again", width="stretch", key=f"hide_{app_id}"):
            revealed.discard(app_id)

    if show_notes:
        st.info(f"Presenter note: {lesson}")

    if app_id in revealed:
        result, audit = run_case(app)
        st.divider()
        total = sum(v.values())
        if total:
            share = v[result["final"]] / total
            st.markdown(f"#### The room vs the system: **{share:.0%}** of you matched")
            votes_df = pd.DataFrame([{"Choice": k, "Votes": n, "System": "System's answer" if k == result["final"] else "Other"}
                                     for k, n in v.items()])
            st.altair_chart(alt.Chart(votes_df).mark_bar(cornerRadiusEnd=6).encode(
                y=alt.Y("Choice:N", sort=["APPROVE", "HUMAN REVIEW", "DECLINE"], title=None),
                x=alt.X("Votes:Q"),
                color=alt.Color("System:N", scale=alt.Scale(domain=["System's answer", "Other"],
                                                             range=[ORANGE, "#C9CCD8"]), title=None),
                tooltip=["Choice", "Votes"]).properties(height=130), width="stretch")
        show_result(result, audit, lesson, key="game")

# ---------------- Tab 2: build your own
with tab_try:
    st.markdown("Move the sliders and edit the text. Try typing *casino*, *lawsuit* or *overdraft* into the bank notes, "
                "or raise the amount above $250k.")
    start = st.selectbox("Start from", list(mt.APPLICANTS), format_func=lambda k: mt.APPLICANTS[k]["name"], index=2)
    base = mt.APPLICANTS[start]
    a, b = st.columns(2)
    with a:
        name = st.text_input("Business name", base["name"])
        amount = st.slider("Loan amount ($k)", 5, 500, base["amount_k"], step=5)
        score = st.slider("Credit score", 500, 850, base["bureau"]["credit_score"])
        revenue = st.slider("Monthly revenue ($k)", 1, 250, base["financials"]["monthly_revenue_k"])
        dti = st.slider("Debt-to-income (%)", 0, 90, int(base["financials"]["debt_to_income"] * 100))
        years = st.slider("Years in business", 0, 20, base["financials"]["years_in_business"])
        kyc_ok = st.checkbox("Identity verified", value=True)
    with b:
        notes = st.text_area("Bank statement notes (the agent reads this)", base["bank_notes"], height=150)
        news = st.text_area("News about the business", base["news"], height=110)
        st.caption("The ML model only sees the sliders. Only the agent reads these two boxes.")

    custom = {"name": name, "amount_k": amount, "purpose": base["purpose"],
              "bureau": {**base["bureau"], "credit_score": score},
              "financials": {"monthly_revenue_k": revenue, "debt_to_income": dti / 100, "years_in_business": years},
              "bank_notes": notes, "kyc": {"identity_verified": kyc_ok, "sanctions_hit": False}, "news": news}
    st.divider()
    if use_llm:
        go = st.button("🤖 Ask the Claude agent", type="primary")
        if go:
            st.session_state["custom_go"] = json.dumps(custom, sort_keys=True)
        if st.session_state.get("custom_go") == json.dumps(custom, sort_keys=True):
            show_result(*run_case(custom), key="custom")
        else:
            st.caption("Change anything, then press the button. (Offline mode updates live.)")
    else:
        show_result(*run_case(custom), key="custom")

# ---------------- Tab 3: how it works
with tab_how:
    st.markdown("### Five layers, one decision")
    st.markdown("Each layer in this demo matches a part of Taktile's **Agentic Decision Platform**.")
    st.table(pd.DataFrame([
        ["1. Data", "Mock credit bureau, financials, bank notes, KYC and news", "Data Marketplace and Context Layer (Experian, Plaid, LexisNexis…)"],
        ["2. Hard rules", "Max $250k, identity verified, no sanctions hit", "Rules and decision tables in the Decision Engine"],
        ["3. AI agent", "Claude calls 6 tools, reads the text, recommends with reasons", "AI Agent Manager, built on frontier models"],
        ["4. Guardrails", "Low confidence or agent vs model conflict → human", "Human-in-the-loop controls"],
        ["5. Human + audit", "Review queue and audit_log.json", "Case Manager and audit trail for regulators"],
    ], columns=["Layer", "In this demo", "In Taktile's real platform"]))
    st.markdown("### Why the agent matters")
    st.markdown("The ML model gives **Golden Crust Bakery a 99% chance of repaying**, because it only sees numbers. "
                "The agent reads the bank notes, finds $42k sent to an online casino, and stops the automatic approval. "
                "That is the gap between a credit score and an agent that reads documents.")
    st.markdown("### Honest limits of this demo")
    st.markdown("- The data is synthetic and the model is a simple logistic regression.\n"
                "- The offline agent only matches keywords, so it would wrongly flag \"no overdrafts\". "
                "A language model understands the sentence, which is why Taktile uses one.\n"
                "- Real platforms test rules on past cases, monitor drift and check fairness before going live.")
