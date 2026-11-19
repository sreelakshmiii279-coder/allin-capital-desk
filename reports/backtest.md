# Backtest: the desk vs the fund's own decisions

Run 2026-11-19T05:15 UTC. **Agreement: 11/12** against the pre-agreed gate of 10/12 → **PASS**.

How it was run: each memo became a pseudo-application with the decision and the 'why' paragraph removed; its own memo, every partner-note line naming it, and any correction seeded from it were hidden (leave-one-out); web research was off so hindsight could not leak in. Desk 'Take the call' = leans invest; 'Pass…' = leans pass; 'borderline' counts as a disagreement.

| # | Company | Fund | Desk | Revealed | Written | Agree |
|---|---|---|---|---|---|---|
| 1 | The ePlane Company | INVESTED | Partner judgement - borderline | 48 | 65 | **no** |
| 2 | Petalry | PASSED | Pass | 38 | 66 | yes |
| 3 | Unbox Robotics | INVESTED | Take the call | 66 | 73 | yes |
| 4 | HopBox | PASSED | Pass | 24 | 56 | yes |
| 5 | Wint Wealth | INVESTED | Take the call | 62 | 71 | yes |
| 6 | CampusCredit | PASSED | Pass | 26 | 48 | yes |
| 7 | Giva | INVESTED | Take the call | 60 | 65 | yes |
| 8 | AeroDrop | PASSED | Pass | 32 | 61 | yes |
| 9 | SuperK | INVESTED | Take the call | 66 | 74 | yes |
| 10 | Coinlane | PASSED | Pass - outside the fund's game (partner to confirm) | 28 | 46 | yes |
| 11 | Jai Kisan | INVESTED | Take the call | 72 | 80 | yes |
| 12 | Prepnest | PASSED | Pass | 30 | 53 | yes |

## Where it disagrees, and who looks wrong

**The ePlane Company** — fund INVESTED, desk "Partner judgement - borderline" (48/100). Driving criterion: *path*. Verdict: **desk**. The AI triage desk gave the startup a borderline score of 48/100, heavily penalising it under 'path' (score 1) and 'traction' (score 1) due to a lack of immediate commercial revenue or signed paying customers. In hindsight, the desk was wrong: as a deeptech venture, the company successfully secured $14 million in Series B funding, ~$34 million in government RDI support, and initiated a $50 million Series C round, validating the VC fund's thesis to underwrite long-duration founder commitment over early revenue milestones. [indiatimes.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHEf7Mt-bocwGQ_kZMtTKIwqOOpWS8IHxa-L0gsqOW3WNgURjSpK4j6z0Ojs-L_WJSqkA-JxEh8DeF8yL3SmpT8Pwzi-IN99KRU4qeiVo4WJL_OiSck7yABzzCv5yrsMPJoSYomVoirexTUf0cAFcyG5QkRNQC9OdNgp8yXuj_ud-fMQ6UxDARum9Cq-59QEiT5Oeulqrux3P4o_3DOITmCZx7vuUOKEjuPe8CluycOKmysz4xlDa6rLvxFIIbCmHyK6sbVHs84JoR38AFflnawV7bAcxxP_qc=), [thehindu.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGlmNh7ZkPZq8P0PXtW8AlO-n4SewuDhkbBfdQDRtjdw9MCc7Pm5fzLqP4sVhLuF9JmWegH5hE2Ss-TK2dylztOzJ28zj9k3rl_Gyt7kq06ZftT7q2XTjCzly93vITCNmx1Pz9EpNRJZBa6IK0jSf-4Tdp8GYiqKAVCjrnfa4n8rBqOiv0_RGn5cIUNpz5od6cDxKh8n8c13ZjDUuuI36EAM9enRUB3p1BomyRd6ODqReXNQdkwZnR5tKguL0sPfg==), [inc42.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEe7nPpTBEcuCp7iSIy0awW3Vt5PrGe5w1S0ZXx1UFxiWnDurBxgfGK-d0_xSrhQ2Pz1AJly3nMezo1s8u2DhUCw6mNJ6JKVzAXd-tOnl7QPusWKhFN8ThNQEKx719kRCPd8A==)

## Written vs revealed thesis (Riya's drift question, M5)

With one 60-point line, the written-thesis score matches the fund's invest/pass call on **10/12** and the revealed score on **11/12** - the same count. The difference is separation: under the **written** thesis the fund's passes average **55** and its investments **71** (gap 16 points; passes sit just under or over the line, e.g. Petalry 66). Under the **revealed** thesis passes average **30** and investments **62** (gap 33). The public wording barely tells this fund's yeses from its nos; what the memos show it actually weighs does. That supports Riya's drift observation (M5) without settling Aditya's alternative (a changed applicant mix) - 12 memos cannot.

## Honest limits

- 12 memos is a small sample: one flipped call moves agreement by 8 points.
- Memos contain the partners' read of the founder *after* a call; real applications only have a deck, so live founder scores will be less certain than here.
- Ledgerly (M5, 'Kushal still thinks that was a miss') is not in the pack and has no public trace, so the one known false-pass cannot be tested.
- The thesis criteria were written from these same memos. Leave-one-out removes each company's own memo, but the general lessons still come from the set: this measures consistency with the fund's reasoning, not predictive accuracy on new companies. The quarterly re-run on fresh decisions is the real test.
