# Mini Taktile

A classroom illustration of an agentic decision platform for loans. Not Taktile's code.

## Run

    pip install -r requirements.txt
    streamlit run app.py

Optional: set `ANTHROPIC_API_KEY` (or paste it in the sidebar) to use the real Claude agent.
Without a key, an offline stand-in agent follows the same steps.

## Tabs

- **Beat the AI**: show a card, count the room's votes, reveal the system's answer.
- **Try your own application**: sliders and text boxes; the decision updates live.
- **How it works**: the 5 layers mapped to Taktile's platform.

`python mini_taktile.py` runs the same engine in the terminal and writes `audit_log.json`.
