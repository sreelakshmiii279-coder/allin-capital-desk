# Trust contract: how far Kushal can trust the desk, and exactly where it breaks

*Case: "before any of this touches a real decision, Kushal knows — in writing, in numbers, agreed in advance — exactly how far he
can trust it and exactly where it breaks."* This page is that agreement. The numbers are in `config.py`, so the desk enforces them
itself instead of relying on someone remembering.

## 1. What the desk is allowed to do
| It does | It never does |
|---|---|
| Reads deck + form, extracts facts with quotes | Decide. Every application waits for a partner (M5: nobody auto-rejected or auto-advanced) |
| Checks every application against the full portfolio list (63 companies, sourced) | Hold an application *silently*: a HOLD always shows the merit read underneath |
| Searches the web for founders, claims, competition, regulation, max 8 searches | Scrape LinkedIn, or trust a search answer that has no source |
| Scores 6 criteria 0–5 with a source behind every claim | Give a bare number: every score has its criterion, reason, sources and unknowns |
| Recommends: Take the call / Partner judgement / Pass / HOLD | Recommend more calls than the Tue/Thu slots allow (6 a week) |
| After a partner's "Take the call": holds slots, drafts the email + invite, books on reply | Email a founder directly (this build sends to our own inbox), or book without a partner's yes |

## 2. Before go-live — the gate (agreed in advance)
| Test | Threshold | Result | Status |
|---|---|---|---|
| Backtest agreement with the fund's 12 real decisions | ≥ 10/12 | **10/12** | Pass, *at the line* |
| Every disagreement explained (criterion + hindsight) | 100% | 2/2 | Pass |
| Claims traceable to a source in this week's batch | ≥ 95% | 169/171 = 98.8% | Pass |
| Portfolio conflict the partners already know about (MeetRecord-type) is caught | caught | Talkbook → MeetRecord and StockSathi → SuperK flagged *direct*, HOLD | Pass |
| Same input gives the same gate | stable | conflict check runs twice and keeps the stricter level (one early run had StockSathi/SuperK flip) | Pass |
| Riya's triage stays on in parallel ("shadow mode") | 4 weeks minimum | starts now | — |

10/12 is the minimum, not comfort. One more miss and the desk would not go live.

## 3. Where it breaks — known, measured, named
| # | Failure mode | Evidence | What the partner should do |
|---|---|---|---|
| 1 | **Pre-revenue deeptech is under-scored.** Traction is capped when the "key number" is missing, so a founder-first bet like ePlane reads as borderline. | Backtest: ePlane, fund INVESTED, desk 54 "borderline"; hindsight says the desk was wrong (Series B, DGCA approval). | Treat deeptech "borderline" as "Aditya to look" (he does deeptech second calls himself, M3). One correction ("deeptech: a regulator milestone sequence counts as traction") will carry to the next drone/aircraft/robotics applicant. |
| 2 | **It cannot see founder behaviour on a call.** Defensiveness, candour under pressure, "what would make you quit?" — the things that decided Petalry, CampusCredit, Prepnest — only show up in a call. | Backtest used post-call memos, so live founder scores will be *less* certain than the 10/12 suggests. | The founder criterion on a live application is mostly unverified. Use the "questions for the call" list. |
| 3 | **Founder identity is rarely verifiable from the web.** Common names return namesakes; this batch's links are all placeholders. | 0 of 17 founders checked could be confirmed in this batch; the desk reports "not found" / "namesake only" rather than guessing. | Never read "founder 3/5" as "verified". Check the research table. |
| 4 | **Portfolio list is incomplete.** Public sources give 63 companies (41 confirmed); Fund I alone made 51 deals, and some logos may be the partners' pre-fund angel cheques. | `data/research/portfolio.json` | Replace the list with the fund's internal one. Until then a missed conflict is possible: kill rule 4 below applies. |
| 5 | **Category labels from founders are often wrong.** Talkbook and StockSathi ticked "consumer tech"; both are B2B. | Extraction relabels; both labels are shown. | Check the relabel when the sector drives a flag. |
| 6 | **Hindsight verdicts on fictional or private companies cannot be checked.** | Petalry: no public trace, verdict "not public". | Judge those disagreements on reasoning, not outcome. |
| 7 | **The thesis is a reconstruction.** The fund publishes no rubric, weights or exclusion list. | `DESIGN.md` §4 | Weights are in one file; change them deliberately, then re-run the backtest. |

## 4. Kill criteria — the desk stops itself
| Signal | Threshold | Window | Action |
|---|---|---|---|
| Partner overrides of the recommendation | > 30% | any 4 weeks | Pause recommendations; Riya triages; redesign |
| Claims without a traceable source | > 5% in a run | per run | That run's reads are flagged "withheld" until checked |
| Riya's review time per application | > 15 min average | 4 weeks | Kill: reviewing costs half of doing it by hand |
| **Any** portfolio conflict a partner finds that the desk missed | 1 | ever | Conflict module off; manual portfolio check until fixed |
| Desk-recommended calls → second meeting, vs Riya-only calls | lower | 2 quarters | Retire the recommendation layer; keep research + conflict check |
| Backtest re-run on the quarter's new decisions | < 83% agreement | quarterly | Back to the gate |

## 5. What it saves, if it holds
Baseline: 30 min per application, 19+ associate-days a quarter (~300 applications). Target: Riya reviews a read in ≤ 10 min, so
**~10 associate-days a quarter come back**, before counting the calendar back-and-forth that disappears on every "yes". The
time saving is only an output. The outcomes are: no missed conflicts, and calls that convert to second meetings at least as well as today.

*Signed off by: Kushal Bhagia ____ · Aditya Singh ____ · Riya ____ · Date ____*
