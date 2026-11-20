# Data protection: All In Capital triage desk

L8: *"The All In Capital form collects founders' personal details, and the agent researches them. That is regulated activity."*
In India that is the **Digital Personal Data Protection Act, 2023** (Rules notified Nov 2025; penalties up to ₹250 crore for security failures and ₹200 crore for failing to notify a breach). For EU founders it is the **GDPR**. This page is the builder's working answer, not legal advice. The fund's counsel should confirm it before go-live.

## 1. Notice to show founders on the public form (before they submit)
> All In Capital uses an assisted screening tool to review applications. We process the details in your form and deck, and
> we look up public information about you and your company (company website, news, and professional profiles via web search),
> to decide whether to invite you to a call. A person at the fund makes every decision. AI services (Google Gemini) process
> this data on our behalf. We keep your application material for up to 180 days after we decide, then delete it and keep only
> the decision. You can ask us to see, correct or erase your data at any time: write to the address on this form.

## 2. What the desk holds, where, and for how long
| Data | Where | Kept |
|---|---|---|
| Form + deck text (names, background, numbers) | Neon `applications`, `jobs` | Until **180 days after a partner's decision** (`RETENTION_DAYS`), then deleted by the scheduled worker |
| The read: extracted facts, research findings with links | Neon `reads` | Same: facts and research purged, the decision record kept |
| Review decision, booking state, corrections | Neon `reviews`, `bookings`, `corrections` | Decision record kept; erasable on request |
| Cost and trace metadata (tokens, cost, step, prompt version) | Neon `model_calls`, `runs` | **No prompt or answer text is stored**; erasable per applicant |
| Langfuse traces (when connected) | Langfuse cloud | **Metadata only** by default (`LOG_CONTENT_TO_TRACES=0`): "logs are a second copy of founders' data" |
| Emails | Resend → our own inbox only, in this build | Mailbox policy |

## 3. What each AI call receives (minimum necessary)
See `PROMPT_AUDIT.md`. The scorer gets **founder IDs, not names**, extracted claims (not the whole deck), and memo *sections* (not every memo). Names go only to the steps that need them: extraction, web research, and the email greeting.

## 4. Founders' rights
- **Access / correction:** Riya exports the application page; corrections are re-scored.
- **Erasure:** on each application's page, *Data protection → Erase this applicant*, or `POST /api/applicant/<id>/erase`. It needs the **admin password** (Kushal) and the typed id. It deletes the row in every table: application, read, review, booking, slots, jobs, corrections, events, cost lines, runs. An `erasure` event records only that it happened.

## 5. Who can do what (least privilege)
| Who / what | Can |
|---|---|
| Riya (desk password) | Review, correct, edit and send the invite, run the queue, ask the assistant |
| Kushal (admin password) | Additionally: erase an applicant |
| Chat assistant | **Read only**: a separate SELECT-only database login (`allin_reader`). It cannot record decisions or send anything. |
| Eval endpoints | **Do not exist on the live site** (404). Evals run only against the test environment. |
| Test vs live | Separate databases (`allin_desk_test` / `allin_desk`). The harness and volume test refuse to run unless the server reports `env=test`. |

## 6. If there is a breach
1. Rotate the database password, `EDIT_PASSWORD`, `ADMIN_PASSWORD`, `CRON_SECRET` and the model keys in Vercel; redeploy.
2. Work out which applicants are affected (Neon access logs, the `events` table).
3. Notify the Data Protection Board and the affected founders as the DPDP Rules require. Counsel to confirm the timing; the Rules set a deadline for a detailed report.
4. Write down what happened and what changed (`RUNBOOK.md` → incident log).

## 7. Processors
Google (Gemini models + search grounding), Cloudflare AI Gateway (passes model calls through; payload logging and caching switched **off**, so it keeps no copy), Neon (database), Vercel (hosting), Resend (email), Langfuse (traces, metadata only; its "AI features" switched off).
