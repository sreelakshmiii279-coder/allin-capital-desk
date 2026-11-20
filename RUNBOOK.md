# Runbook: running the desk on a Monday (L8: "a product needs an owner, not just a builder")

**Owner:** Riya (day to day). **Escalation:** Kushal (admin password, kill decisions). **Builder:** for code changes only.
Live: https://allin-desk.vercel.app · Test: run locally with `DESK_ENV=test` (separate database).

## Every weekday (10 minutes)
1. Open **Review queue**. The intake card shows waiting / running / done / **needs attention**.
2. Handle every **needs attention** row. The reason is written there (empty application, oversize deck, failed twice).
3. Review new reads top-down: Take the call → HOLD → borderline → Pass. Record each in **Partner review** with a one-line reason when you override.
4. For each "Take the call": edit the drafted email and press **Send**. Founder replies: paste them into the booking card.
5. Glance at **Cost**: today's spend vs the limit.

## The queue drains itself
GitHub Actions calls `/api/worker/tick` every 5 minutes (≈5 applications per tick, about 60 an hour). It also sends follow-ups after 3 silent working days and applies the retention purge. If it is stuck: press **Process queue**, or check the "Drain the intake queue" workflow runs on GitHub.

## When something goes wrong
| You see | It means | Do |
|---|---|---|
| Red **Paused** banner | Today's model spend passed `DAILY_COST_LIMIT_INR` (an alert email was sent) | Nothing is lost: the queue waits. Either wait for midnight IST or raise the limit in Vercel env (Kushal decides). |
| A row says **Needs attention: Failed twice** | The model or a provider failed twice | Open the row's run trace (link on the read); re-queue by re-adding the application. |
| A booking says **escalated** | Calendar unreachable, email bounced, 2 counter-rounds with no time, or an unclear reply | Reply to the founder by hand; the reason is in the booking's history. |
| An alert email "**booking record not saved**" | The meeting exists but the record write failed | Record it by hand in the booking card. |
| A score looks wrong | | Correct the criterion with a one-line reason. It is stored and retrieved for similar companies. |
| A portfolio conflict was **missed** | Kill criterion K1 | Stop using recommendations; tell Kushal; check the portfolio list (`data/research/portfolio.json`). |
| Override rate > 30% over 4 weeks | Kill criterion | Pause the desk; Riya triages by hand; back to the builder. |

## Weekly
- Look at the **Feedback loop** tab: are the same corrections repeating? Then a rule should change.
- Kushal reads 3 random full runs (trace + read). The worst failures don't announce themselves (L8).

## Before any prompt or rule change
1. `python app.py` locally (test env) → `python evals/harness.py` → must be **SHIP** with 0 critical failures and 0 flips.
2. `python backtest.py` → agreement ≥ 10/12.
3. Then deploy: `npx vercel deploy --prod --scope mesa-ced3 --yes`.

## Founder data requests
Erasure: application page → *Data protection* → *Erase* (admin password). See `PRIVACY.md`.

## Incident log
| Date | What happened | What changed |
|---|---|---|
| 2026-11-19 | Evals found the booking agent could book without partner approval | Approval guard added (K7) |
| 2026-11-19 | Prompt trimming made two past investments look like "regulation bets" (backtest 9/12) | Gate definitions sharpened + gate memos always sent (11/12) |
