# All In Capital · Inbound Triage Desk

MESA PGP C4 · Term 2 · Case 03 (All In Capital) · AI with Mihirr Sose.

A desk that takes a week of inbound applications, deck + form, and for each one:
- checks it against the **full** portfolio list (the MeetRecord near-miss),
- **goes looking on the web** for what the founder didn't put in the deck, and says what it couldn't find,
- scores it **criterion by criterion** against the fund's reconstructed thesis, with a **source behind every claim**,
- makes the case: Take the call / Partner judgement / Pass / HOLD, inside the Tue/Thu call capacity,
- learns from every partner correction on similar companies (**feedback loop**),
- and once a partner says "take the call", **books it** (slots held, invite + .ics drafted).

It never decides. Kushal sees every outcome.

**Read in this order:** [`DESIGN.md`](DESIGN.md), the course method step by step: 9 checks → 5 pre-build decisions → components map →
thesis → evidence map → scoring → feedback loop → booking agent. Then [`reports/backtest.md`](reports/backtest.md) (10/12 vs the fund's real
decisions), [`reports/trust_contract.md`](reports/trust_contract.md) (where it breaks, kill criteria) and
[`reports/batch_report.md`](reports/batch_report.md) (this week's 10).

| File | Step |
|---|---|
| `intake.py` | 1. load the week's pile |
| `extract.py` | 2. structured facts, every one with a verified quote; deck-vs-form contradictions |
| `conflicts.py` | gate A: portfolio check (63 sourced companies) |
| `research.py` | 3. evidence-map research loop (capped, cited, namesake guard) |
| `thesis.py` | the written and revealed theses, criteria, anchors, anti-thesis |
| `score.py` | 4. per-criterion scores, evidence tracing, gates, recommendation |
| `feedback.py` | Act → Signal → Capture → Store → Retrieve → Apply |
| `booking.py` | S6 agent: tools, state object, edges, retry table |
| `pipeline.py` / `run.py` | batch run + capability ceiling |
| `backtest.py` / `report.py` | backtest and written reports |
| `app.py` + `web/` | partner review queue |

```
python run.py --seed      # load the partner-notes corrections once
python run.py             # run data/applications/ into the review queue
python backtest.py        # 12 memos, leave-one-out
python report.py          # reports/*.md
python app.py             # http://localhost:5057
```
Needs `.env`: `GEMINI_API_KEY`, `GEMINI_MODEL`, `DATABASE_URL` (Neon), `RESEND_API_KEY`, `TO_ADDRESS`, `EDIT_PASSWORD`.
