# All In Capital — Inbound Triage Desk: design, step by step

MESA PGP C4 · Term 2 · AI with Mihirr Sose · Case 03 "All In Capital".
Built in the order the course teaches it (S1 → S6). Nothing was coded before steps 1–4 were written down.
"Write the outcome before you write the prompt" (S1).

| Course step | Session | Section here | Where it lives in code |
|---|---|---|---|
| Does this deserve to be built? (9 checks) | S2 | §1 | — |
| Are we ready to build? (5 pre-build decisions, capability ceiling) | S1, S2 | §2 | `config.py` (ceiling, kill criteria) |
| Components map (inputs → AI → human gate → outputs) | S2 | §3 | `pipeline.py` |
| Reconstructing the thesis from public sources | Case | §4 | `thesis.py`, `data/research/` |
| Evidence map (variable · data · where · sufficient when · max tries · short circuit) | S4 | §5 | `research.py` |
| Scoring with a source behind every claim | Case | §6 | `score.py` |
| Feedback loop (Act · Signal · Capture · Store · Retrieve · Apply) | S5 | §7 | `feedback.py` |
| Booking agent (tools · state object · edges · retry table · framework choice) | S6 | §8 | `booking.py` |
| Backtest against the fund's real decisions | Case | §9 | `backtest.py`, `reports/backtest.md` |
| Trust contract: how far Kushal can trust it, where it breaks | Case | §10 | `reports/trust_contract.md` |

---

## 1. The Nine Checks — does this deserve to be built?

| Group | Check | Answer | Evidence |
|---|---|---|---|
| Objectives | 1. Real problem? | **Yes.** 30 min per application → 19+ working days a quarter of Riya's time, mostly on applications "that were never getting past us". | Case brief |
| | 2. Repeat workflow? | **Yes.** Same five steps every time: read deck, check public presence, look up founders, form a view, write two lines. Weekly batch (11 applications in one week of the notes). | Case brief; Partner notes M1 |
| | 3. Input available? | **Partly — and that's the design constraint.** Deck + form: yes. Fund thesis, criteria, portfolio, founder backgrounds: **not given** → must be found on the public web, and the gaps named. Past decisions: 12 memos + 5 meetings of notes. | Case brief "What you are given" |
| Utility | 4. Valuable output? | **Yes** if it is a criterion-by-criterion read with sources; **useless** if it is a bare "7/10" ("worse than useless" — Kushal). | Case brief |
| | 5. Impact measurable? | **Yes.** Riya's minutes per application, partner override rate, call→second-meeting rate, missed conflicts. | §2.4 |
| | 6. ROI worth it? | **Yes.** ~2 min of model + search calls per application vs 30 min of an associate; the bigger prize is no missed portfolio conflict and fewer good deals lost to a tired Friday read. | §2.1 |
| Reliability | 7. Pattern tracked? | **Yes.** 12 written memos with reasons, plus three logged scoring mistakes (Petalry 6.5, AeroDrop 7.5, the MeetRecord-overlap 7) — a tracked pattern, not one anecdote. | Memos; Partner notes M1, M3, M4 |
| | 8. Human in loop? | **Yes, by rule.** "Kushal sees every outcome before anything is decided. Nobody is auto-rejected or auto-advanced." | Partner notes M5 |
| | 9. Fail-safe built? | **Yes.** Shadow mode (Riya keeps triaging), backtest gate before go-live, kill criteria agreed in advance, booking only after a partner click. | §2.5, §9 |

**Verdict: build it** — but as a *case-maker*, not a decider, and only after the backtest gate.

---

## 2. The Five Pre-Build Decisions

### 2.1 Outcome definition (what must change in the world, not what the bot does)
*Behavioural requirement (inspect the output):* every application gets a sourced, criterion-by-criterion read.
*Outcome requirement (measure the world):*
1. **Partner/associate time on applications that never pass falls from 19+ days a quarter to ≤ 4 days a quarter** — Riya reviews reads instead of producing them (~15 associate-days a quarter returned; "everything ends in paisa": that is ~15 days of an associate's cost redirected from reading to sourcing and diligence).
2. **Zero missed portfolio conflicts** (the MeetRecord near-miss is the failure we pay for in reputation, not minutes).
3. **No drop in the quality of calls taken:** the share of first calls that lead to a second meeting stays at or above today's rate.
Keep asking "so what?": time saved → associate time on sourcing/diligence → better Fund II deployment. We do **not** stop at "time saved".

### 2.2 Baseline (same units as the outcome)
| Metric | Today | Source |
|---|---|---|
| Associate time per application | ~30 min (3 of 11 in one week took 40+ min because founder background was hard to find) | Brief; Notes M1 |
| Associate days per quarter on first-pass triage | 19+ | Brief |
| Implied volume | ~300 applications a quarter (19 days × 8 h × 60 / 30 min) ≈ 23 a week | derived |
| Known scoring errors in the notes | 3 of 3 cited first-pass scores were later judged too high (Petalry 6.5, AeroDrop 7.5, overlap-co 7) | Notes M1, M3, M4 |
| Missed conflicts caught only by memory | 1 (MeetRecord overlap) | Notes M4 |
| Call → second-meeting rate | **Not in the files.** Must be pulled from the fund's CRM before go-live; the system cannot measure outcome 2.1.3 without it. | gap |

### 2.3 Workflow change (around the capability ceiling)
**Before:** application → Riya reads deck, Googles founders, forms a view, writes 2 lines → partners discuss weekly → someone emails/calendars the founder.

**After:**
1. Weekly intake batch (form + warm intros) goes into the desk.
2. Desk: conflict check vs the *full* portfolio list → anti-thesis check → web research loop on company + founders → criterion-by-criterion score with sources → named unknowns → recommendation + two-line summary, with past partner corrections applied.
3. **Human gate:** Kushal (and Riya) see *every* application's read in one queue, sorted. They accept, correct a criterion (one-line reason, mandatory), or change the recommendation. Nothing is rejected or advanced automatically.
4. On Kushal's "take the call": booking agent proposes Tue/Thu afternoon 30-min slots (Aditya added for deeptech), drafts the email and holds the slot. On founder confirmation, books and logs it.
5. Riya's role changes from *drafter* to *reviewer and corrector* — and in shadow weeks she still triages in parallel (Kushal: "I'm not switching off Riya's triage because a demo went well").

**Capability ceiling.** Calls happen only Tue/Thu afternoons, 30 min each. With 2 afternoons × 4 bookable slots = **8 first calls a week, max**; realistically Kushal takes ~4–6. So the desk never recommends "take the call" for more than `CALL_CAP_PER_WEEK = 6` applications a week; anything beyond is ranked "call-worthy, over capacity" for Kushal to choose. The review queue itself is capped at the week's batch (~25) so Kushal reads one screen of two-liners, not 25 decks.

### 2.4 Measurement plan
| What | How | When |
|---|---|---|
| Associate minutes per application | Riya logs review time in the desk (timer on the review page) vs 30-min baseline | weekly |
| Disagreement score | % of applications where a partner changed the recommendation; average absolute change per criterion; # corrections | weekly (dashboard) |
| Sourcing quality | % of criterion claims with a source attached (target 100%; anything unsourced is shown as an unknown) | every run |
| Conflict recall | every portfolio overlap Riya/Kushal flag that the desk did not | every run |
| Backtest agreement | desk call/no-call vs fund decision on the 12 memos | before go-live, then quarterly |
| Outcome | call → second-meeting rate for desk-recommended vs Riya-recommended calls | quarterly |

### 2.5 Kill criteria — agreed in advance, in numbers
**Gate before go-live (backtest, §9):** the desk must agree with the fund's actual call on **≥ 10 of 12** past memos, and for every disagreement it must name which criterion drove it. Fewer than 10 → do not go live; redesign.

**Early-warning kill switch (doesn't wait for lagged outcomes, S2):**
- Partner override rate on the recommendation **> 30% over any 4-week window** → pause, back to redesign.
- **Any missed portfolio conflict** → stop the conflict module immediately, Riya checks manually until fixed.
- **> 5% of claims without a traceable source** in a run → the run is withheld from Kushal.
- Riya's review time **> 15 min per application** for 4 weeks (i.e. reviewing costs half of doing it) → kill; the desk is not saving time.

**Lagging kill:** after two quarters, if desk-recommended calls convert to second meetings at a lower rate than Riya-only calls → retire the recommendation layer, keep only research + conflict check.

---

## 3. Components map

```
 INPUTS                       CLEAN / EXTRACT               AI LOGIC (capped loops)                       HUMAN GATE              OUTPUTS
 ───────                      ───────────────               ────────────────────────                     ──────────              ───────
 Deck text  ─┐                                         ┌─► [A] Conflict check vs full portfolio list ──┐
 Form text  ─┼─► intake.py ─► extract.py ──────────────┤   (short circuit = HOLD, never auto-reject)    │
 (weekly     │   (one record   (structured facts,      ├─► [B] Anti-thesis screen ─────────────────────┤
  batch)     │    per company)  each with its quote)   │   (hard flags still go to Kushal)              │
             │                                         ├─► [C] Research loop (evidence map §5) ────────┤
 Public web ─┘◄── research.py: Gemini + Google Search  │   founders · company · claims · market ·       ├─► score.py ─► review queue ─► Kushal/Riya ─┬─► Accept ──────────► record
 (cited only)     grounding; company site via          │   max 2 tries/variable, total cap 8 searches   │   per-criterion      (every app,     accept /       │
                  requests + HTML cleaning             │                                                │   0–5 + sources     sorted)         correct +      ├─► Correct ─► feedback.py (Capture/Store)
                  (no LinkedIn scraping: ToS, hiQ)     └─► [D] Retrieve past corrections (feedback) ───┘   + unknowns                         reason         │
                                                                                                           + recommendation                                └─► Take call ─► booking.py agent ─► email draft (own inbox) + .ics hold + CRM log
 Thesis (§4): public sources + 12 memos + partner notes  ──────────────────────────────────────────────────►  (written vs revealed thesis, both shown)
```
Failure modes designed for: website down (→ unknown, not zero), search returns nothing (→ named gap), model returns non-JSON (→ retry, then "needs human"), deck claims contradicted by web (→ shown as conflict, score uses the weaker), founder not findable (→ named gap: "deck is the only source").

---
(§4 onwards is filled in as each step is built.)

## 4. Reconstructing the thesis (the case says this is part of the work)

Two theses, kept apart on purpose (`thesis.py`):

| | Written thesis (public) | Revealed thesis (what the fund does) |
|---|---|---|
| Source | allincapital.vc, Inc42 / Outlook Business / Entrackr, Kushal Bhagia's Inc42 interview: every line sourced in `data/research/thesis_research.md` | 12 deal memos + 5 partner meetings |
| Sectors | "Sector-agnostic, special focus" on fintech, deeptech, consumer tech, consumer brands | Label matters less than founder behaviour (M2 Jai Kisan); recent yeses lean to commerce infra and consumer with real repeat (M5) |
| Stage / cheque | Pre-seed/seed, usually lead, USD 250–600K, leads rounds < USD 1M, Fund II first cheques up to INR 5 Cr | Avoids being the small cheque in a capital-heavy game (HopBox) |
| Founder | Founder-market fit, earned secrets, proof of building, long-shared-history teams, 5–6 yr commitment | Owns the risk (CampusCredit vs Jai Kisan), knows cohorts/margins (Petalry vs Giva), customer groundwork first (Wint, SuperK), defensiveness is information (M1), evidence not pedigree (M3) |
| Anti-thesis | Only "safe/obvious bets" and later-stage profitable companies are sourced | Business that exists only if regulation turns friendly (Coinlane); density/capex games (HopBox) |

**What the public record does NOT say, and what that absence costs** (case: "you say what that absence costs your system"):
| Not public | Cost to the system | How the desk handles it |
|---|---|---|
| Scoring rubric / weights | Weights are a reconstruction; a wrong weight mis-ranks silently | Weights live in `thesis.py`; backtest checks them against 12 real calls; every correction is logged |
| Ownership target | Can't judge whether a round's valuation works for the fund | Not scored; shown as a question for the call |
| Formal exclusion list | Can't hard-reject a category; a "crypto" keyword ban would be wrong (QuestBook, Web3, is in the portfolio) | Anti-thesis judged on the model ("depends on regulation changing"), and still sent to Kushal |
| Which logos are Fund I/II vs the partners' earlier angel cheques | Conflict check may over-flag | Portfolio list carries `confirmed` + source; unconfirmed entries can only raise "adjacent", never HOLD |
| Founder backgrounds (all links in this batch are `.example` placeholders) | Founder criterion rests on self-description | Research reports "not found / namesake only"; founder claims stay unverified and the call questions target them |
| Ledgerly notes (M5) | One known miss can't be studied | Named as a gap in the backtest report |

**Which thesis is used, and why** (M5: "tell me which one you used and why"): the recommendation uses the **revealed** thesis
because it is the one that reproduces the fund's real decisions (see §9); the written score is shown next to it and a
**drift** flag fires when they differ by 15+ points. That turns Riya's unreconciled observation into a number per application.

## 5. Evidence map — see the table at the top of `research.py`
Variables: company presence, each founder, up to 2 traction claims, competition, regulation (regulated models only).
Request-based fetch first (cheap), HTML cleaned by rules before any model sees it (S4: never raw HTML). Google-grounded
search for everything else; no LinkedIn scraping (ToS; hiQ v LinkedIn). Caps: 2 tries per variable, 8 searches per
application. Short circuit: a round far above a pre-seed cheque skips deep research. A search with no sources = not found.
Identity guard: a source about a namesake is rejected ("Arun Kumar" returns many Arun Kumars).

## 6. Scoring — `score.py`
Six criteria, 0–5 with anchors, each defined from named memos/notes. The model must cite a source for every claim; code drops
any claim it can't trace (quote not in the document, URL not returned by research) and an untraceable criterion becomes
**unknown, which counts as 1, not skipped** (M1). Traction is capped at 2 when the business model's key number is missing.
Overall = weighted sum on 0–100; the recommendation is plain code (thresholds in `config.py`). A direct portfolio overlap
forces HOLD but keeps the merit read visible.

## 7. Feedback loop — `feedback.py` (header has the six steps)
Seeded with the three corrections already in Riya's notes (Petalry, AeroDrop, the MeetRecord overlap). A correction is refused
without a one-line reason. Retrieval: strict tag filter (sector / business-model family) → Gemini embeddings + keyword rank.
Applied corrections are injected into the prompt **and shown on the read**, so Kushal can see when an old correction is steering.
"Re-score" re-runs only the scoring step so the effect of a correction is visible in ~30 seconds.

## 8. Booking agent — `booking.py` (header has tools, state object, edges, retry table)
No framework (one judgement gate). Starts only on a partner's "Take the call". Tue/Thu afternoon slots, 30 min, Aditya added
for deeptech, slots held so nobody is double-booked, max 2 re-proposal rounds then escalate to Riya. Emails (with .ics) go to
our own inbox, never to a founder, in this build.

## 9. Backtest — `backtest.py`, results in `reports/backtest.md`
## 10. Trust contract — `reports/trust_contract.md`
