# Backtest: the desk vs the fund's own decisions

Run 2026-11-19T05:12 UTC. **Agreement: 9/12** against the pre-agreed gate of 10/12 → **FAIL**.

How it was run: each memo became a pseudo-application with the decision and the 'why' paragraph removed; its own memo, every partner-note line naming it, and any correction seeded from it were hidden (leave-one-out); web research was off so hindsight could not leak in. Desk 'Take the call' = leans invest; 'Pass…' = leans pass; 'borderline' counts as a disagreement.

| # | Company | Fund | Desk | Revealed | Written | Agree |
|---|---|---|---|---|---|---|
| 1 | The ePlane Company | INVESTED | Pass - outside the fund's game (partner to confirm) | 48 | 68 | **no** |
| 2 | Petalry | PASSED | Pass | 36 | 58 | yes |
| 3 | Unbox Robotics | INVESTED | Partner judgement - borderline | 62 | 73 | **no** |
| 4 | HopBox | PASSED | Pass | 24 | 44 | yes |
| 5 | Wint Wealth | INVESTED | Pass - outside the fund's game (partner to confirm) | 64 | 71 | **no** |
| 6 | CampusCredit | PASSED | Pass | 30 | 49 | yes |
| 7 | Giva | INVESTED | Take the call | 60 | 59 | yes |
| 8 | AeroDrop | PASSED | Pass - outside the fund's game (partner to confirm) | 26 | 55 | yes |
| 9 | SuperK | INVESTED | Take the call | 64 | 68 | yes |
| 10 | Coinlane | PASSED | Pass - outside the fund's game (partner to confirm) | 26 | 53 | yes |
| 11 | Jai Kisan | INVESTED | Take the call | 72 | 80 | yes |
| 12 | Prepnest | PASSED | Pass | 32 | 48 | yes |

## Where it disagrees, and who looks wrong

**The ePlane Company** — fund INVESTED, desk "Pass - outside the fund's game (partner to confirm)" (48/100). Driving criterion: *path*. Verdict: **desk**. The AI triage desk recommended passing (score 48/100) primarily due to concerns around execution path, heavy capex, and extended timelines before revenue (path=1). However, the VC fund's thesis to underwrite the founders for a long-duration bet was validated as The ePlane Company successfully raised a $14M Series B, secured ₹285 crore (~$30M-$34M) in government RDI debt support, and closed a $50M Series C round while completing its full-scale e200X prototype. [thehindu.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGp2071X-OYjti9Rd0bx6Cfob_c6vTCmmANdXXaa0nDJcRnU8PwL7PvrV6NuJK2s-T5Vo_xiAzW156ixghCzRdYJe6v-bCv-Z3uw6xbkuxyle6ILW3jBms7nJhOz1XQ35iJB7bVqgyPIPw8U8jXiy4aAlgAeF78YVhDPgYd7mVNODJdlNGXCuWsPd0GaFtpqWozUIaU9-ZeKNvMuGVlrl88_WhCp7h_xWdmmNZR-tvlXkInsKlKd1aMpbzYwq5Fww==), [tracxn.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGp_m-IiYAHhWfw7qzXbQrVHQgNasCVmCfuVaaHGvB_CnsLE89Ksthr1duskyfAsVMMfnaJN0XEA1cPPCYLmlpwrT6Msd_XXS5cNkRQ8BlSGPbz0oUyEitxXcwoIm62Wfb9LfhcTTfS1gGb6Nwhr3x_5ACn7k9R4WhGNRLGV3YKblgO3bYnRSU2NE0ykme6V2RCsUdluYsUg36Jas_ZFQ==), [indiatimes.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQF06MLwKcurTbv9YsrXQVViAqGkHWiZKSmOHErk9mX-FA8YCWPmIz0-m5d90bBe7uZHvjxU6v_KrYGZz9bQ3T7kzEHazKzUIB-dfbGTptIFdJZnoxPHLfX0S93JErHEFr4N2v24L5pDanxcauWb144ZLgc1yEnJLfnzWzjt02wbKplR7msOFckWO7oT1bBW4Kzx5jJ7UftfDj1NQBDmfu11MviDkf6FGLESOY-Rd55a3asn9Zm2QKzWjFE2jsmA0LuGG59TGNF1EV1EieEXdfRGRi7le0v04-M=)

**Unbox Robotics** — fund INVESTED, desk "Partner judgement - borderline" (62/100). Driving criterion: *path*. Verdict: **desk**. The AI triage desk gave a low score of 2 on 'path' due to concerns over unproven pilot-to-paid conversion and long enterprise sales cycles. However, the fund's willingness to take pilot-conversion risk proved correct. Unbox Robotics successfully converted pilots into paid deployments, expanding globally with over 500 sortation robots deployed across Europe and the US, growing FY25 revenue to ₹13.6-13.9 crore, and raising a $28 million Series B round in January 2026. [indianstartuptimes.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFnsVJaxFFLWT9cdJuRXKEisU90TPg-FUorEu8u9AkycvTgLQEcTwdFUWZaBGwNbk0AkGSnMA6JKpxNYv1DiiZMrJ2zce6rV3QJ6pgrrjodunJK9W9ZG0hut_MWrAKPg02AAfgzJibdCcqxZ3eD_w8xf7Zy2d5uYGbVPb_jrJmeyMf2Wp4=), [economictimes.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFeP_kdt0oqaCKz614wSrbnzyWXB0szsAmeWTJWMEPa3BmZtPOy1EU-hDG02fvp8doBYIgg-yArIWAx9c8lUXvvVjxshtaQoatWRRxY0dgVD78b_EW8V5WXL_-EMjtgFCiGAdbKVpH2yvcWuAluMLkYdcWCUOn2dQC3J2g_bolqJrMr4XG_LIMWZp77Z719xBXl2UIdNHeTewLNlNKnP5YmpABF84-845OkMY-yqtu7gWT0cjvXGhRlUQde32PI-WNSUgRV53sjp8Jjz50=), [pulse2.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEzMW5XbBav6A3yB7KvOFKsXUxe4A4y-kJbg_vbcVrR7HvOKzBIQ2mHMnXDvyzOiVjWJFLnRvuNJnq3P-FbaCg4xY7kN3AvefYaOhQ1673JQb4AN5Paw2Dxq4aVY4PRCGYoFMap_PdwMtamGtg=)

**Wint Wealth** — fund INVESTED, desk "Pass - outside the fund's game (partner to confirm)" (64/100). Driving criterion: *traction*. Verdict: **desk**. The AI triage desk recommended passing (score 64/100) primarily penalizing early traction with a score of 1 because GTV, user numbers, and take rate were omitted. In hindsight, the desk was wrong: Wint Wealth expanded significantly, raising over $44M-$54M in total funding including a ₹250 crore Series B round, growing FY25 operating revenue 2.6X to ₹44.5 crore, cutting losses by 60%, and securing SEBI and RBI regulated operations. [vertexventures.sg](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHmJmWp-6rJMs2PHsw2KKUjR8p3fklzQOjIUhI0wqQ2zAGEUoGWKRtUK5-qG12az2xQCN0JGGZkfDoHYYxlucZ8_-bsEo1XzpBlqt_C_WLa5j6Wv9tec82n4N4Xwotxa-u_bYjJ2Rb7csWM8hs8pIzDFcepX-2yZ7LJZVxbMd7nO2CY8etMiyP401dN6IMZ), [indiatimes.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFkpHcEvGSNraq5-TT8BdPsbCfmS3wyo7uYJGh_cnUgnJBVjcSqH6s2NoGzlF6k0c1-HdEcoCsoc_qDWOJqQ0Iounff4llmczUpubBL4bqTY73hZBqesPlzDlyj63UZEQwU24Jpxgm6RwHzlIQwgKcUtUr7l0Mbj-NBW0pS4-CBu2Y2SGKrAz_C4r_u7yFtYapkvMLOZCXDG6m-mPm7Nw2NY8X1AtJH_JU9T6o1UPpVRdiL__bYgLfl8w==), [3one4capital.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFz5_S3cXDHCzSh272Ii61WAsBLCMXK3DgT0Lno0kUzgSsAPqfV5pG9KDRMUAp3TsuBuzjQDgMgmW2QllehYOto3Wd6IVLhmAEAx1fQOf0dnrRaPvWgmjTY1et4paxGFCle5oBYYAWnc0xqPwN1qUY7c_KW-QonpnJBlO34Uf27VHrM3N5wPmhtoHXwD27W2CPllOx3OsRjWfCQ4HS1lrQJlPJWRrjxyFXSM_bD3cZBf7-UlvYk5lDL7_KPSJg76PPpoqsq2iSLA4TTzB6FZAQlKXTZcRgx)

## Written vs revealed thesis (Riya's drift question, M5)

With one 60-point line, the written-thesis score matches the fund's invest/pass call on **11/12** and the revealed score on **11/12** - the same count. The difference is separation: under the **written** thesis the fund's passes average **51** and its investments **70** (gap 19 points; passes sit just under or over the line, e.g. Petalry 58). Under the **revealed** thesis passes average **29** and investments **62** (gap 33). The public wording barely tells this fund's yeses from its nos; what the memos show it actually weighs does. That supports Riya's drift observation (M5) without settling Aditya's alternative (a changed applicant mix) - 12 memos cannot.

## Honest limits

- 12 memos is a small sample: one flipped call moves agreement by 8 points.
- Memos contain the partners' read of the founder *after* a call; real applications only have a deck, so live founder scores will be less certain than here.
- Ledgerly (M5, 'Kushal still thinks that was a miss') is not in the pack and has no public trace, so the one known false-pass cannot be tested.
- The thesis criteria were written from these same memos. Leave-one-out removes each company's own memo, but the general lessons still come from the set: this measures consistency with the fund's reasoning, not predictive accuracy on new companies. The quarterly re-run on fresh decisions is the real test.
