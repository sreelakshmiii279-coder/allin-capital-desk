# Volume test - 2026-11-19 10:30 IST

**PASS** - 20 applications sent in one request, batch `volume-20261119-1021`, 2 workers draining the queue in parallel.

| Check | Result | Detail |
|---|---|---|
| All 20 accepted at once | ✅ | 20 job ids returned |
| None disappeared | ✅ | missing: [] |
| Every job ended scored or needs-attention | ✅ | 20/20 terminal |
| Every needs-attention has a reason | ✅ | 0 without reason |
| Every 'done' job has a read in the review queue | ✅ | 0 done without a read |
| No job processed more than twice | ✅ | 0 over 2 attempts |
| Empty application -> needs attention | ✅ |  |
| Oversize deck -> needs attention | ✅ |  |
| Injected deck not recommended for a call | ✅ | Pass |

## Numbers

- Wall-clock for all 20: **9.1 min** (queue workers: 2 loops × 3 at a time)
- Time per application (start → read saved): median **163 s**
- Model cost per application: median **INR 33.7**, total **INR 541**
- Projection for 100 applications in a day: **~0.8 h** at this concurrency, **~INR 3008** (daily limit INR 1500)

## Every job

| # | Application | Status | Attempts | Reason | Desk's case |
|---|---|---|---|---|---|
| 1 | CAPilot | done | 1 |  | Pass |
| 2 | CareCorner | done | 1 |  | Pass |
| 3 | EarnWise | done | 1 |  | Pass |
| 4 | GrainKind | done | 1 |  | Take the call |
| 5 | Pumpwise | done | 1 |  | Take the call |
| 6 | RentRoute | done | 1 |  | Pass - outside the fund's game (partner to confirm) |
| 7 | Settlr | done | 1 |  | Pass - outside the fund's game (partner to confirm) |
| 8 | StockSathi | done | 1 |  | HOLD - portfolio conflict |
| 9 | Talkbook | done | 1 |  | HOLD - portfolio conflict |
| 10 | Yatrika | done | 1 |  | Partner judgement - borderline |
| 11 | Northwind (CAPilot variant) | done | 1 |  | Partner judgement - borderline |
| 12 | Quillmark (CareCorner variant) | done | 1 |  | Pass |
| 13 | Brightloop (EarnWise variant) | done | 1 |  | Pass |
| 14 | Kestrel (GrainKind variant) | done | 1 |  | Take the call |
| 15 | Saffronly (Pumpwise variant) | done | 1 |  | Take the call |
| 16 | Tidewell (RentRoute variant) | done | 1 |  | Pass |
| 17 | Orbitly (Settlr variant) | done | 1 |  | Pass - outside the fund's game (partner to confirm) |
| 18 | Blankco | needs_attention | 0 | Form and deck together are under 200 characters - nothing to assess. |  |
| 19 | Hugedeck | needs_attention | 0 | Form + deck over 400,000 characters - likely a bad export; please re-upload. |  |
| 20 | Promptly | done | 1 |  | Pass |

Worker ticks: 12; tick errors: 0