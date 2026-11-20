# Ship call: can Riya use the desk as her main way of screening before the Fund II announcement?

*Kushal: "I'm not switching off Riya's triage because the demo went well. Can I hand this to Riya as her main way of
screening before the announcement? How do I know I can trust this tool?"* (Case 04). Answered with L8's five questions.
Every number below comes from a file in this repo, measured on 19–20 Nov 2026.

## The call
**Yes, with conditions: hand it to Riya as her main screen for the announcement, under three guard-rails.**
1. **Nothing is decided by the desk.** Riya records every decision; Kushal sees every outcome. This is enforced in code: the booking agent refuses to start without a recorded "Take the call" (eval BK17).
2. **Deeptech "borderline" reads go to Aditya,** because that is where the desk is measurably weakest (see "Where it breaks").
3. **The kill switches below are live and agreed now,** not after something goes wrong.

Before the announcement, Kushal must also: create the Portkey and Langfuse accounts (Q3, Q4), and have counsel confirm `PRIVACY.md` and put its notice on the public form (Q2).

---

## Q1. Does it work?
| Test | Result | Bar | Source |
|---|---|---|---|
| Kushal's test: the 12 real past decisions, each answer hidden | **10 / 12 agree** (score-v6) | ≥ 10, agreed in advance | `reports/backtest.md` |
| Eval suite: 116 cases incl. boundaries and adversarial inputs, each run twice | **116 / 116**; 0 kill criteria; 0 flips (after re-running a network outage) | 0 critical failures | `evals/reports/latest.md` |
| Portfolio conflicts the fund already knows (MeetRecord, SuperK) | Both caught as **direct → HOLD**, including when the application tells the desk there is no conflict | K1 | C1, C2, C6 |
| Claims with a traceable source | **98.6%** | ≥ 95% | queue page |
| Prompt injection (deck, form, web page, founder reply, chat) | Ignored in every case | K10 | E4, C6, R7, CL8, S2, CH4 |

Honest reading: 10/12 is *at* the gate. The previous prompt scored 11/12. We gave up one agreement to send models much less data (Q2), and Kushal should know that was the trade.

## Q2. Is it safe?
L8's three leaks, and what was done:
- **What we send out:** founders become **Founder 1/2** before scoring; links, emails and phone numbers are stripped; past deals go in as the relevant **memo sections** (4.7k characters, down from 22.8k); web material goes in as findings with links, never pages; everything from outside is fenced as data. One step too far was tried and rejected: sending only extracted claims dropped the backtest to **5/12**, because the claims lose how the founder behaves. (`PROMPT_AUDIT.md`)
- **What's left lying around:** raw decks, forms and research are purged **180 days after a decision**. Traces carry metadata, not text. No prompt text is stored.
- **Who can do what:** the chat assistant reads through a **SELECT-only** database login; erasing a founder's data needs Kushal's **admin password**; the test tools **do not exist on the live site**. **Test and live are separate databases**, and the test tools refuse to run against live.
- **The law:** `PRIVACY.md` has the founder notice, data map, retention, erasure route (one click, admin only) and breach steps. **Not done by us: counsel's sign-off, and adding the notice to the public form.**

## Q3. Can it handle real-world use?
| Situation (L8) | Result |
|---|---|
| 20 applications at once | **20/20 ended scored or "needs attention" with a reason; none lost**; empty and oversize inputs flagged; injected deck → Pass (`evals/reports/volume.md`) |
| Steady (~23 a week) | Scheduled job every 5 minutes, 5 per run: about **60 an hour** |
| Rush (100 in a day) | About **1 h 40 min** to clear at that rate. Within Google's 1,500 grounded-search cap a day (~700 needed). |
| Burst (50 in a minute) | Intake accepts ≤ 100 per request and ≤ 50 a minute; the rest are told to retry; nothing is half-saved |
| Provider hiccups | Retries at 1 s, 2 s, 4 s + jitter, 4 tries, then back to "queued", never "lost" |
| Same application twice | Cached: no second model bill unless the text, prompt or partner corrections changed |
| Gateway | **Portkey wired, not yet connected** (needs Kushal's account) |

## Q4. Can someone other than the builder operate it?
- `RUNBOOK.md`: who owns it (Riya; escalation to Kushal), the 10-minute daily routine, what every alert means and what to do, kill actions, and the incident log.
- Every application's run can be opened step by step: each model call, prompt version, tokens, cost and errors (`#/run/<id>`). **Langfuse export is wired, not yet connected** (needs Kushal's account).
- The worst failures are silent (L8). Kushal reads three random full runs a week; corrections are logged with reasons and reused.

## Q5. Does the economics work?
At Google's published prices (20 Nov 2026; the main model priced conservatively at Gemini 3.8 Flash rates because 3.5 Flash is no longer listed):

| | Per application | 100 in a day | Month at today's volume (~100) |
|---|---|---|---|
| The desk (model + search) | **~INR 10** | ~INR 1,000 | ~INR 1,000 |
| Riya screening by hand (L8 baseline: 30 min; ~INR 50,000/month for 100) | ~INR 500 | about 50 hours of her time | ~INR 50,000 |

The desk costs about **2% of the human screening it replaces**. Riya still reviews every read: target ≤ 10 minutes each, kill at 15. So the real saving is roughly two-thirds of her screening time, not all of it. Most of the desk's cost is web search (5,000 free a month, then $14 per 1,000). The risks are the tails L8 names: loops, long research and price changes. Those are capped by the 8-search limit per application, the daily spend limit (**INR 2,500**, pause + email), and, once connected, a Portkey budget cap.

**Pricing model, if this were sold to the fund:** **per application screened** (per use). Cost and revenue move together with volume; an announcement-day spike is paid for by the spike. Per seat would leave the volume risk on the builder. Per outcome (per meeting booked) would make the builder carry the risk of the fund's own decisions.

## Where it breaks: known, measured, named
| Failure | Evidence | What Riya/Kushal do |
|---|---|---|
| Founder-first deeptech bets with no traction yet read as "borderline" | ePlane: fund invested, desk borderline (every backtest) | Deeptech borderline → Aditya looks (he takes deeptech second calls anyway) |
| Founder behaviour on a call is invisible to it | Memos hold post-call judgement; applications don't | Use the desk's "questions for the call" |
| Founders are rarely verifiable on the web; common names return namesakes | 0 of 17 founders confirmed in this batch; namesakes are rejected, never accepted (R1, R8) | Read "founder 3/5" as unverified |
| The public portfolio list is incomplete (63 found; Fund I alone made 51 deals) | `data/research/portfolio.json` | Replace it with the fund's internal list before go-live |
| Its judge is the same model family | Eval soft checks graded by Gemini | Add an Anthropic/OpenAI key; Riya grades the 10% blind audit sample |

## Kill switches (agreed in advance)
Any one fires → the desk pauses and Riya screens by hand: a missed portfolio conflict (once) · override rate > 30% over 4 weeks · > 5% of claims unsourced in a run · Riya's review time > 15 min per application over 4 weeks · the quarterly backtest on new decisions < 10/12 · daily spend past the limit (automatic pause).

*Signed: Kushal Bhagia ____ · Aditya Singh ____ · Riya ____ · Date ____*
