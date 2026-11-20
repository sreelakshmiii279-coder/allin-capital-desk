# All In Capital: Case 04 checklist ("Ready to hand over?")

Sources: Case 04 brief (Build 5, due Fri 20 Nov 2026), L7 Evals, **L8 "From Prototype to Production"**, Advanced AI S2 and S3, and the AI class notes S1–S6 (all in `data/class/`).
✅ done and verified · ⚠ done with a stated limit · ⏳ left to do · 👤 only a person (you / the fund) can do it

Live: https://allin-desk.vercel.app · Code: https://github.com/sreelakshmiii279-coder/allin-capital-desk · Status as of 20 Nov 2026.

---

## What's left
| | Item | Who | Why it isn't done |
|---|---|---|---|
| 👤 | **Judge from a different model family** for the soft eval checks (L7) | You: add an `ANTHROPIC_API_KEY` or `OPENAI_API_KEY` to `.env` | Needs a paid key in your name. Until then every eval report states "SAME FAMILY". |
| 👤 | **Grade the blind 10% audit sample** (L7), then `python evals/harness.py --audit-compare evals/audit/sample-….csv` | You | It is a human check by design: your verdicts, without seeing the judge's |
| 👤 | **Counsel signs off `PRIVACY.md`** and its notice goes on the fund's public form (L8, the law) | The fund | Legal sign-off and the public form belong to the fund |
| 👤 | **Replace the public portfolio list** (63 companies found online) with the fund's internal list | The fund | Only the fund has it. Until then a missed conflict is possible (kill switch K1). |
| 👤 | **Sign the ship call** (`reports/trust_contract.md`) | Kushal, Aditya, Riya | "Agreed in advance" means the people who own the decision |
| ⚠ | **Real calendars and inbound email** | Optional build | Slots are held in the desk's own calendar for Riya, and bookings send an .ics invite to our inbox. No Google Calendar sync; founder replies are pasted in. |
| ⚠ | **Fallback to a second model vendor** if Google is down | Optional build | The gateway retries Google; it does not switch to another vendor. Retries, the queue and "needs attention" mean nothing is lost while Google is down. |
| ⏳ | **Re-run the 20-application volume test** on the final build | Me, ~10 min, ~INR 200 | The last volume run (19 Nov) predates the scheduled worker, intake limits and the Cloudflare gateway. Those were tested piecewise; the burst test should be repeated end to end. |

Everything else below is done.

---

## A. What the case says the system does
| | Item | Where / evidence |
|---|---|---|
| ✅ | Researches each applicant and scores against the rubric, with a recommendation | `pipeline.py`; batch of 10 + volume test |
| ✅ | **Riya** reviews the score and justification, then approves or rejects | Review queue; reviewer defaults to Riya; Kushal sees every outcome |
| ✅ | Drafts a **personalised email**; **Riya edits and sends it from the dashboard** | Booking card; verified: the draft cited the applicant's 38% repeat rate |
| ✅ | Reads the reply, **follows up after 3 silent working days**, handles a **counter-proposal**, escalates at the cap | `booking.on_reply`, `booking.tick` (scheduled worker); evals BK2–BK9 |
| ⚠ | Checks **Riya's calendar**, offers slots, books **in both calendars** | Desk calendar + .ics invite (see "What's left") |
| ✅ | Riya's corrections feed **both scoring and email drafting** | Verified: her edit became lesson #5; the next brand draft applied it |

## B. Kushal's five questions (Case 04 + L8)
| # | Question | Status | Evidence |
|---|---|---|---|
| 1 | **Does it work?** | ✅ | **116/116** eval cases (run twice, 0 flips, 0 kill criteria); **backtest 10/12** on the fund's real decisions (gate 10); gateway cross-section 16/16 |
| 2 | **Is it safe?** | ✅ | `PROMPT_AUDIT.md`: founder IDs, memo *sections*, claims + redacted text, outside text tagged as data. Retention purge at 180 days. Metadata-only traces. SELECT-only login for the chat assistant. Admin password for erasure. **Separate test and live databases.** `PRIVACY.md` (DPDP/GDPR). |
| 3 | **Can it handle real-world use?** | ✅ | Queue + volume test 20/20; retries 1/2/4 s + jitter; GitHub Actions drains the queue every 5 min; intake limits; read cache; **Cloudflare AI Gateway** (retries, 120/min rate limit, **$28/day spend limit**, no logs or cache) |
| 4 | **Can you operate it?** | ✅ | **Langfuse connected** (every run, step and call with prompt version, tokens, cost); run inspector in the dashboard; `RUNBOOK.md` |
| 5 | **Does the economics work?** | ✅ | ~**INR 10 per application** at Google's published prices (~2% of hand screening); cost page by application, day, week, month; **INR 2,500/day** pause + alert; lite model for simple steps; per-application pricing recommended in the ship call |

## C. L7 Evals
- [x] Kill criteria written first: `evals/KILL_CRITERIA.md` (K1–K14)
- [x] Every decision point with partitions, boundaries and interactions: `evals/cases.json` (**116 cases + canary**, severity tagged)
- [x] Hard and soft assertions; the judge checks every rubric item
- [x] Harness over HTTP only; break-on-purpose; the canary must fail; every case runs twice
- [x] Adversarial rows in forms, decks, web pages, founder replies and chat; injected deck in the volume test
- [x] Blind 10% audit sample written each run (`evals/audit/`): 👤 grading is yours
- [ ] 👤 Judge from a different model family (see "What's left")

## D. Class notes S1–S6
- [x] S1–S2: 9 checks, 5 pre-build decisions, outcome vs output, baseline, capability ceiling, kill criteria, components map (`DESIGN.md`)
- [x] S4: evidence map, loop caps, short circuits, hybrid extraction (HTML cleaned before the model), no LinkedIn scraping
- [x] S5: Act → Signal → Capture → Store → Retrieve → Apply; disagreement score; tag filter before semantic search
- [x] S6: tool cards, state object, edges, retry table (transient vs permanent), framework choice (none: one judgement gate)

## E. Advanced AI S2 and S3
- [x] S2 six checks: sourced numbers; units tested (scores, ₹ Cr/lakh/USD, tokens → USD → INR); no silent defaults; no hidden state; no secrets in the repo; tested beyond one example
- [x] S3 four questions for all five booking tool cards (label, typed inputs, named outputs, what happens on each failure, safe to call twice)

## F. L8 production checks
| | Check | Status |
|---|---|---|
| ✅ | Borderline test set, kill criteria, Kushal's past-decisions test | 116 cases; K1–K14; backtest 10/12 |
| ✅ | Leak 1, what you send out | Founder IDs; memo sections (22.8k → 4.7k chars); claims + redacted text. "Claims only" was tried and **failed the backtest (5/12)**, so the redacted text stays. |
| ✅ | Leak 2, what's left lying around | Retention purge; metadata-only traces; no prompt text stored; Cloudflare logs and cache off; Langfuse "AI features" off |
| ✅ | Leak 3, who can do what | Read-only chat login; admin-only erasure; eval tools 404 on live; run-only gateway token |
| ✅ | No keys in code · test and live separate | `.env` git-ignored, secret scan before every push; `allin_desk_test` vs `allin_desk`, harness refuses live |
| ✅ | The law | `PRIVACY.md` (👤 counsel sign-off) |
| ✅ | 20 at once, retries with jitter, queue, scheduled job, burst limits, cache | Volume test (⏳ re-run on final build), `llm.backoff`, `jobqueue.py`, GitHub Actions, intake limits, read cache |
| ✅ | Gateway with retries and a budget cap | Cloudflare AI Gateway. Portkey closed self-serve sign-up (now a Palo Alto Networks sales process). |
| ✅ | Langfuse tracing with prompt version | Connected and verified on local and live |
| ✅ | An owner, not just a builder | `RUNBOOK.md` |
| ✅ | Cost per run/day/month vs baseline, limit that stops spend, cheaper models, pricing model, **ship call** | Cost tab, INR 2,500 cap + $28 gateway cap, lite model, `reports/trust_contract.md` |

## G. Found by the evals and fixed
- **Booking:** no reply-window timeout; no calendar retry; crashed on a permanent booking error and on a CRM failure; no escalation after email retries ran out; **booked without partner approval** (K7). All fixed.
- **Feedback:** both of two conflicting corrections applied (K14); a drone lesson leaked into a food brand; a no-op "correction" stored. All fixed.
- **Scoring:**
  - A summary blended 1.9 L and 2.1 L into "~2 L": numbers are now quoted exactly.
  - Renamed twins scored up to 16 points apart: two samples are now averaged, and gates need both samples to agree.
  - Trimming the prompt to claims only broke the backtest (5/12): the redacted text was restored (10/12).
- **Cost:** search had been over-counted 2.5× at assumed prices. Re-priced from Google's published list: ~INR 10 per application; daily limit set to INR 2,500.
