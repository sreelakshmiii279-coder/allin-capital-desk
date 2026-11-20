# All In Capital: Case 04 checklist ("Ready to hand over?")

Sources: Case 04 brief (Build 5, due Fri 20 Nov 2026), L7 Evals, Advanced AI S2 and S3 (all in `data/class/`).
✅ done and verified · 🔑 built, but needs an account/key you create before it can be verified · ⚠ partly, with the limit stated

## A. What the case says the system now does
| | Item | Where | Status |
|---|---|---|---|
| ✅ | Researches each applicant and scores against the rubric, with a recommendation | `pipeline.py` | 20-application volume test |
| ✅ | **Riya** reviews the score and justification, then approves or rejects | Review queue; reviewer defaults to Riya | |
| ✅ | System **drafts a personalised email**; **Riya edits and sends it from the dashboard** | `booking.start` → draft; `send_draft`; booking card | Verified on a test twin: the draft cited the 38% repeat rate |
| ✅ | Reads the reply, **follows up if no response** (3 working days), handles a **counter-proposal**, escalates at the cap | `booking.on_reply`, `booking.tick` (worker) | Evals BK2–BK9 |
| ⚠ | Checks **Riya's calendar**, offers slots, books **in both calendars** | Slots are held in the desk's calendar for Riya; booking sends an .ics invite | No Google Calendar connection: the .ics goes to our inbox. Founder replies are pasted in (no inbound mail). |
| ✅ | Riya's corrections feed **both scoring and email drafting** | `feedback.py`; email lessons are retrieved in `draft_with_model` | Verified: Riya's edit became lesson #5, and the next brand draft opened with the number |

## B. The five questions
| # | Question | Task | Status |
|---|---|---|---|
| 1 | Does it work? | Evals (L7) | ✅ 111 cases, run twice. See `evals/reports/latest.md` |
| 2 | Is it safe? | **Task 1** prompt audit | ✅ `PROMPT_AUDIT.md`: founder IDs; relevant memos only (22.8k → 7.5k chars); findings, not pages; "data, not instructions" line |
| 3 | Real-world use? | **Task 2** volume test + queue | ✅ `evals/reports/volume.md`: 20 at once, none lost, two bad inputs → needs-attention with a reason, injection → Pass |
| 3 | | **Task 3** Portkey with automatic retries | 🔑 `llm.py` routes every call through Portkey when `PORTKEY_API_KEY` is set (retry config 3 attempts on 429/5xx). Verify with `python check_setup.py`. Portkey's docs don't say whether search citations come back through the gateway; the check tests it, and `PORTKEY_ROUTE_SEARCH=0` keeps research working if not. |
| 4 | Can you operate it? | **Task 4** Langfuse tracing + prompt version | ✅ Every step and model call is traced in Neon (`runs`, `model_calls`), opens at `#/run/<id>`, and records the prompt version. 🔑 Export to Langfuse via OTLP once keys are set (the legacy ingestion API was switched off on 16 Nov 2026). |
| 5 | Does the economics work? | **Task 5** cost per call, totals, cost page, daily limit + alert | ✅ Cost tab: by application, day, week, month, step. Pause + one alert email per day past `DAILY_COST_LIMIT_INR` (4,000). ⚠ Prices are assumed list prices: confirm them in Google AI Studio billing. |

## C. L7 evals
- [x] Kill criteria written first: `evals/KILL_CRITERIA.md` (K1–K14)
- [x] Every decision point with partitions, boundaries and interactions: `evals/cases.json` (111 rows, severity tagged)
- [x] Hard and soft assertions; the judge checks every rubric item
- [x] Harness over HTTP only; break-on-purpose (`--break`); canary must fail; every case runs twice
- [x] Adversarial rows: E4, C6, R7, CL8, S2, plus Promptly in the volume test
- [x] Blind 10% human audit sample written each run (`evals/audit/`). **You** fill in the verdicts, then run `--audit-compare`.
- [ ] 🔑 Judge from a **different model family**: set `ANTHROPIC_API_KEY` or `OPENAI_API_KEY`. Until then every report says "SAME FAMILY".

## D. Advanced AI S2: six checks
- [x] Hardcoded numbers each have a named source (config.py comments; thesis.py sources)
- [x] Units: score 0–100 vs criteria 0–5 checked (F1–F6); ₹ Cr / lakh / USD conversion tested (F9–F12); cost tokens → USD → INR tested ($1–$3)
- [x] Silent defaults: unknown counts as 1, not skipped (F20); a model 7/5 is clamped (F21); a broken calendar returns 'no_calendar_access', never "full"
- [x] Hidden state: per-thread clients; the queue claims with SKIP LOCKED; scoring sampled twice and merged
- [x] Invented functions and secrets: `.env` is git-ignored; `.env.example` has empty values
- [x] Works on more than one example: 10 real + 7 renamed twins + 3 hostile inputs (volume test); 12 memos (backtest)

## E. Advanced AI S3: four questions per tool card
- [x] All five booking tools: label, typed inputs with examples, named outputs, what happens on each failure, safe to call twice (`booking.TOOLS`)

## E2. L8 "From Prototype to Production" (posted 20 Nov): extra checks, now fixed in this build
| | Check (L8) | Status in the build |
|---|---|---|
| ✅ | Q1: borderline test set, kill criteria, Kushal's past-decisions test | 116 cases with boundaries; K1–K14; backtest **10/12** on score-v6 |
| ✅ | Q2 leak 1, *what you send out* | Founder IDs; **memo sections** (header + "why"), not whole memos (memo context 22.8k → 4.7k chars); extracted claims + redacted application text; web findings, not pages; everything outside tagged as data. ⚠ "Claims only" (v5) was tried and **failed the backtest (5/12)**: the claims lost founder behaviour, so the redacted application text stays. |
| ✅ | Q2 leak 2, *what's left lying around* | Retention purge 180 days after a decision (scheduled worker); traces carry **metadata only** (`LOG_CONTENT_TO_TRACES=0`); no prompt text stored in Neon |
| ✅ | Q2 leak 3, *who can do what* | Chat assistant uses a **SELECT-only DB login**; erasure needs a separate **admin password**; eval endpoints **404 on live** |
| ✅ | No keys in code | `.env` git-ignored; `.env.example` has names only |
| ✅ | **Test and live separate** | `allin_desk_test` (local + evals) vs `allin_desk` (Vercel). The harness and volume test refuse a non-test server. Test data removed from live. Masthead badge shows Test / Live. |
| ✅ | The law (DPDP / GDPR) | `PRIVACY.md`: founder notice text, data map, retention, erasure route, breach steps, processors. Counsel to confirm. |
| ✅ | Q3: 20 at once, nothing lost | Volume test 20/20 (19 Nov) |
| ✅ | Q3: retries 1 s → 2 s → 4 s + jitter, 4 tries | `llm.backoff`; booking email/calendar too (BK10–BK14) |
| ✅ | Q3: scheduled job drains the queue; limits on bursts | GitHub Actions every 5 min → `/api/worker/tick` (5 per tick); intake ≤100 per request and ≤50 per minute, extras told to retry |
| ✅ | Q3: cache identical application + prompt version | Read reused (no model calls) when text, prompt versions and corrections are unchanged; 7-day freshness |
| ⚠ | Q3: Portkey (retries, fallbacks, **budget cap**) | Code wired (`llm.py`, switches on with `PORTKEY_API_KEY`). **Portkey closed self-serve sign-up** (20 Nov 2026: sign-up now redirects to a Palo Alto Networks sales form), so no account could be created. What Portkey would add is covered in the desk itself: retries 1/2/4 s + jitter (4 tries), daily spend cap with pause + alert, per-call cost meter, cache. Missing: provider fallback to a second model vendor. |
| ✅ | Q4: Langfuse | **Connected** (free Hobby plan, EU). Local and live send OTLP traces: every run, step and model call with model, prompt version, tokens and cost; content not logged. "AI features" (sending data to AWS Bedrock) switched off. |
| ✅ | Q4: someone else can run it on Monday | `RUNBOOK.md`: owner, daily routine, what each alert means, kill actions, incident log |
| ✅ | Q5: cost per run/day/month vs Riya's baseline; limit that stops the spend | Cost tab; pause + alert at INR 2,500/day. Prices now from Google's pricing page (search was over-counted 2.5×; 3.5 Flash priced conservatively at 3.8 Flash rates) |
| ✅ | Q5: cheaper model per step | Lite model for reply classification, email draft, edit judge; main model for judgement steps |
| ✅ | Q5: pricing model and the written **ship call** | `reports/trust_contract.md`: conditional yes, per-question evidence, **~INR 10/application at published prices (~2% of hand screening)**, per-application pricing, kill switches |

## F. Found by the evals and fixed
- Booking: no automatic reply-window timeout; no calendar retry; crashed on a permanent booking error and on a CRM failure; didn't escalate when email retries ran out; **booked without partner approval** (K7). All fixed.
- Feedback: two conflicting corrections were both applied (K14); a drone lesson leaked into a food brand; a no-op "correction" was stored. All fixed.
- Scoring: a summary blended 1.9 L and 2.1 L into "~2 L" (S5 flip) → numbers are now quoted exactly. Renamed twins landed up to 16 points apart → two scoring samples are averaged, and gates need both samples to agree.
- Cost: 100 applications ≈ INR 3,400 at assumed prices, 85% of it web search → the daily limit was raised from 1,500 to 4,000 so announcement day doesn't pause halfway. Cutting `MAX_SEARCHES_PER_APP` from 8 to 5 would save about INR 10 per application.
