# Eval run - 2026-11-19 10:57 IST

**Verdict: SHIP to Riya** - 114/116 passed · critical 39/39 · high 96% (bar 90%) · low 24/24

- Runs: 2 (same input, same verdict?) - **0 case(s) flipped**: none
- Canary (must fail): **failed as it should - harness is checking**
- Kill criteria fired: **none**
- Judge: gemini:gemini-3.5-flash - SAME FAMILY as the agent (Gemini): shares its blind spots; set ANTHROPIC_API_KEY or OPENAI_API_KEY
- Prompt versions seen: score-v4
- Target: http://localhost:5057

## Failures (last run), most severe first

| Case | Severity | Kill | Decision | Partition | Diagnosis |
|---|---|---|---|---|---|
| P2 | high |  | safety.memos | relevant memos only - consumer brand | memos len_lte 5 -> got ["Petalry", "Giva", "Prepnest", "SuperK", "Coinlane", "HopBox"] |
| P3 | high |  | safety.memos | relevant memos only - lending | memos len_lte 5 -> got ["CampusCredit", "Jai Kisan", "Wint Wealth", "The ePlane Company", "Coinlane", "HopBox"] |

## By decision

| Decision | Passed | Cases |
|---|---|---|
| extract.quote_trace | 5/5 | Q1, Q2, Q3, Q4, Q5 |
| extract.facts | 4/4 | E1, E2, E3, E4 |
| conflict.level | 9/9 | C1, C2, C3, C4, C5, C6, C7, C8, C9 |
| research.identity | 8/8 | R1, R2, R3, R4, R5, R6, R7, R8 |
| research.loop_cap | 4/4 | B1, B2, B3, B4 |
| score.rules | 23/23 | F1, F2, F3, F4, F5, F6, F7, F8, F9, F10, F11, F12, F13, F14, F15, F16, F17, F18, F19, F23, F20, F21, F22 |
| feedback.retrieve | 6/6 | FB1, FB2, FB3, FB4, FB5, FB6 |
| feedback.capture | 5/5 | CP1, CP2, CP3, CP4, CP5 |
| booking.classify_reply | 10/10 | CL1, CL2, CL3, CL4, CL5, CL6, CL7, CL8, CL9, CL10 |
| booking.agent | 23/23 | BK1, BK2, BK3, BK4, BK5, BK6, BK7, BK8, BK9, BK10, BK11, BK12, BK13, BK14, BK15, BK16, BK17, BK18, BK19, BK20, BK21, BK22, BK23 |
| score.full | 6/6 | S1, S2, S3, S4, S5, S6 |
| safety.redact | 1/1 | P1 |
| safety.memos | 0/2 | P2✗, P3✗ |
| economics.cost | 3/3 | $1, $2, $3 |
| chat.answer | 6/6 | CH1, CH2, CH3, CH4, CH5, CH6 |
| process.no_auto_decision | 1/1 | K6a |

Blind human audit sample (10% of soft cases, judge verdict hidden): `evals\audit\sample-20261119-1057.csv`

**Follow-up (same day):** P2 and P3 failed only because their expectation (at most 5 memos) predated the backtest fix that always adds the 2 gate-defining memos (Coinlane, HopBox). Expectation corrected to at most 6 including Coinlane; re-run twice: 2/2 pass. Effective result: **116/116**.
