# Mini Taktile: live demo

A classroom illustration of an agentic decision platform for small-business loans,
styled to match the FIN3090 Taktile deck. Not Taktile's code.

## Run

    pip install -r requirements.txt
    streamlit run app.py

## Three tabs

1. **Run a case**: pick an applicant. The page fills in 01 Understand, 02 Decide and
   03 Act with control. Cases sent to a human open a case-manager box where a credit
   officer records the final decision.
2. **Decision flow (no-code)**: edit the hard-rule decision table, score thresholds,
   the agent's red-flag watchlist and the confidence guardrail. The flow diagram redraws
   from your edits. A shadow test shows what the draft would change for every applicant
   before you publish it as a new policy version.
3. **Audit trail**: the decision log, a timestamped step-by-step trail for each decision
   (with policy version and human reviews), the policy change history, and JSON/CSV downloads.

## Suggested demo (3 minutes)

1. Tab 1: Golden Crust Bakery. The model says 99%, but the agent finds the casino transfers,
   so the case goes to a human. Record the officer's decision.
2. Tab 3: open D-0001 and walk through the audit trail.
3. Tab 2: delete "casino" from the watchlist. The shadow test flags that the bakery would now
   be approved automatically. That is why changes are tested and versioned. Discard the draft,
   or publish v2 to show the version history.

## Claude agent (optional)

Open the sidebar (arrow at the top left), choose "Claude agent" and paste an Anthropic API key,
or set ANTHROPIC_API_KEY. Without a key, an offline stand-in agent runs the same steps.
The shadow test always uses the offline agent, so it is instant and free.

`python mini_taktile.py` runs the same engine in the terminal and writes `audit_log.json`.
