# Mini Taktile: live demo

A classroom illustration of an agentic decision platform for small-business loans,
styled to match the FIN3090 Taktile deck. Not Taktile's code.

## Run

    pip install -r requirements.txt
    streamlit run app.py

The page follows the deck's three steps: 01 Understand, 02 Decide, 03 Act with control.
Pick an applicant with the pills at the top, or choose "Build your own" to move sliders
and edit the bank notes live.

## Suggested order in class

1. Chapter One Books: approved automatically.
2. Golden Crust Bakery: the model says 99%, but the agent finds casino transfers, so it goes to a human.
3. BuildFast Ltd: the $250k hard rule declines it before any AI runs.
4. Build your own: type "casino" into the bank notes and watch the decision change.

## Claude agent (optional)

Open the sidebar (arrow at the top left), choose "Claude agent" and paste an Anthropic API key,
or set ANTHROPIC_API_KEY before launching. Without a key, an offline stand-in agent runs the same steps.

`python mini_taktile.py` runs the same engine in the terminal and writes `audit_log.json`.
