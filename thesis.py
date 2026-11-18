"""The fund's working thesis, reconstructed (case: "reconstructing a working thesis from that is part of this case").

Two versions are kept on purpose (Partner notes M5: Riya asked "score against the written thesis or what we actually do?";
Kushal: "tell me which one you used and why").
- WRITTEN thesis: what the fund says publicly (site, press, interviews) -> data/research/thesis_research.md
- REVEALED thesis: what the fund's 12 memos and 5 partner meetings show it actually does.
Every application is scored on the revealed thesis (it predicts the fund's real decisions; see backtest), and the
written-thesis score is shown beside it. A gap between them is shown as a DRIFT flag, so the reconciliation nobody has
done happens one application at a time.

Every criterion names where its definition comes from. Nothing here is a rule the fund published - the fund publishes no
rubric - so each line is a reconstruction a partner can overrule (and their corrections feed back, see feedback.py)."""

CRITERIA = [
    {
        "key": "founder",
        "name": "Founder quality (behaviour, not pedigree)",
        "weight_revealed": 30, "weight_written": 25,
        "written_lens": "Founder-market fit, earned secrets, proof of building, long-shared-history team, 5-6 year commitment",
        "definition": "Does the founder own the risk of their own model, know the numbers that matter for it without notes, "
                      "do the unglamorous customer groundwork first, and stay candid about weak spots? Credentials alone "
                      "score nothing (M3: 'score the evidence, not the pedigree'). Inflated or inconsistent claims about "
                      "themselves, or defensiveness on a weak spot, count against (M1: 'defensive is information').",
        "sources": ["Memo 5 Wint Wealth", "Memo 6 CampusCredit", "Memo 9 SuperK", "Memo 11 Jai Kisan", "Memo 12 Prepnest",
                    "Partner notes M1, M3"],
        "anchors": {"5": "Owns the risk explicitly, knows cohort/default/conversion numbers, field groundwork shown",
                    "3": "Relevant operating experience, numbers partly known, no red flags",
                    "1": "Pushes core risk onto someone else, cannot give the key number, or misstates own background"},
    },
    {
        "key": "path",
        "name": "Path to market",
        "weight_revealed": 20, "weight_written": 15,
        "definition": "Is there a paying customer, a route through any regulator with concrete milestones, liability addressed, "
                      "and a path to viability that a pre-seed cheque can matter to? Kept separate from founder quality (M3).",
        "sources": ["Memo 1 ePlane", "Memo 3 Unbox", "Memo 4 HopBox", "Memo 8 AeroDrop", "Partner notes M3"],
        "anchors": {"5": "Paying customers, regulatory/liability path mapped with milestones, capital need fits pre-seed",
                    "3": "Some paying customers, path plausible but unmapped",
                    "1": "No customer, or depends on regulation changing, or needs far more capital than a pre-seed fund deploys"},
    },
    {
        "key": "traction",
        "name": "Traction quality: earned, not bought",
        "weight_revealed": 20, "weight_written": 15,
        "definition": "Is growth earned (repeat, retention, referrals, pilot conversion) rather than bought (paid acquisition)? "
                      "The KEY NUMBER for the business model must be present; if it is missing the criterion is capped at 2 "
                      "(M1: 'a missing number should drag the score, not be skipped').",
        "sources": ["Memo 2 Petalry", "Memo 7 Giva", "Memo 12 Prepnest", "Partner notes M1"],
        "anchors": {"5": "Key number present and strong, mostly organic/referral growth",
                    "3": "Key number present, mixed acquisition",
                    "1": "Key number absent or growth mostly paid"},
    },
    {
        "key": "fit",
        "name": "Thesis fit: sector, stage, cheque",
        "weight_revealed": 10, "weight_written": 30,
        "written_lens": "Focus sector + pre-seed + a clear 'why now' + a contrarian (non-obvious) bet",
        "definition": "WRITTEN: is it fintech, deeptech, consumer tech or a consumer brand, raising at pre-seed? "
                      "REVEALED: the label matters less than founder behaviour (M2 Jai Kisan: 'label matters less than whether "
                      "the founders own the risk'); the fund's recent yeses lean to commerce infrastructure and consumer plays "
                      "with real repeat (M5). Stage/cheque mismatch is still a real misfit (HopBox: 'wrong game for a pre-seed fund').",
        "sources": ["Fund site / press (data/research)", "Partner notes M2, M5", "Memo 4 HopBox"],
        "anchors": {"5": "Core sector, true pre-seed, cheque meaningful",
                    "3": "Adjacent sector or label mismatch, stage fits",
                    "1": "Outside sectors and stage, or round far larger than a pre-seed cheque"},
    },
    {
        "key": "defensibility",
        "name": "Defensibility",
        "weight_revealed": 10, "weight_written": 10,
        "definition": "What stops a larger, better-funded player copying this? Does it travel beyond the founder? "
                      "Hard-to-copy field execution counts (SuperK).",
        "sources": ["Memo 9 SuperK", "Memo 12 Prepnest", "Memo 3 Unbox"],
        "anchors": {"5": "Clear structural moat or hard-to-copy execution", "3": "Some edge, contestable",
                    "1": "Format easily copied, or the product is the founder"},
    },
    {
        "key": "candour",
        "name": "Candour and consistency of the application",
        "weight_revealed": 10, "weight_written": 5,
        "definition": "Do deck and form agree? Are claims checkable and checked? Are risks named by the founder? "
                      "Contradictions between the founder's own documents, or claims the web contradicts, count against.",
        "sources": ["Partner notes M1 (defensiveness is information)", "Memo 3 Unbox (described failures before asked)"],
        "anchors": {"5": "Consistent, risks volunteered, claims verified", "3": "Minor inconsistencies",
                    "1": "Material contradictions or inflated claims"},
    },
]

# The question each business model turns on - from the memos' own "why we passed/invested".
KEY_QUESTIONS = [
    {"match": r"d2c|brand|skincare|food|jewel|apparel|beauty|millet|snack|fmcg",
     "question": "Cohort repeat rate and gross margin, known without notes", "precedent": "Petalry (pass) vs Giva (invest)"},
    {"match": r"lend|credit|loan|bnpl|wage|nbfc|financ",
     "question": "Does the founder own default/credit risk, or push it to the NBFC partner?", "precedent": "CampusCredit (pass) vs Jai Kisan (invest)"},
    {"match": r"drone|evtol|robot|hardware|sensor|iot|deeptech|aircraft|machine",
     "question": "Signed/paying customer, pilot-to-paid conversion, and a regulator/certification milestone sequence",
     "precedent": "AeroDrop (pass) vs ePlane, Unbox (invest)"},
    {"match": r"delivery|quick|dark store|density|clinic|capex|store network",
     "question": "Path to positive contribution margin without a raise far bigger than a pre-seed cheque", "precedent": "HopBox (pass) vs SuperK (invest)"},
    {"match": r"content|edtech|exam|creator|app|travel|consumer",
     "question": "30/90-day retention, and does it travel beyond the founder?", "precedent": "Prepnest (pass)"},
    {"match": r"saas|software|b2b|crm|gst|seat",
     "question": "Paying logos, churn/net retention, and cost to acquire a customer", "precedent": "Unbox (pilots as learning)"},
    {"match": r"crypto|web3|token|blockchain|gaming|betting",
     "question": "Does the business exist only if regulation becomes friendlier?", "precedent": "Coinlane (pass on category)"},
]

# Gates: not scored, they change the recommendation. None of them rejects automatically (M5: "nobody is auto-rejected").
ANTI_THESIS = [
    {"key": "regulation_bet", "hard": True, "match": None,
     "why": "The business exists only if regulation becomes friendlier (Memo 10 Coinlane). Judged on the model, NOT on a "
            "'crypto' keyword: the public portfolio includes QuestBook (Web3), so a category ban cannot be sourced."},
    {"key": "stage_mismatch", "hard": True, "match": None,
     "why": "Round far larger than a pre-seed cheque or post-seed stage. Site: cheque USD 250-600K, leads rounds under USD 1M; "
            "Fund II press: first cheques up to INR 5 Cr; avoids later-stage companies with revenue and profits (Inc42 interview). "
            "Memo 4 HopBox: 'we did not want to be the small cheque that gets diluted'."},
    {"key": "capital_density", "hard": False, "match": r"10[- ]minute|quick[- ]commerce|dark store|capex|clinic",
     "why": "Model needs heavy capital / density before it works (Memo 4 HopBox)."},
    {"key": "outside_sectors", "hard": False, "match": None,
     "why": "Outside the four focus sectors. Soft only: Fund II is 'sector-agnostic with special focus' (Inc42), the portfolio "
            "already holds health companies (Arva, Mave, MedMitra, Tross), and M2 says the label matters less than founder behaviour."},
]

# Site: leads rounds under USD 1M (~INR 8.5 Cr); first cheques up to INR 5 Cr. Above this round size the fund is a follower.
MAX_ROUND_CR = 8.5

# WRITTEN thesis - the public record (data/research/thesis_research.md, every line sourced there).
WRITTEN = [
    "Pre-seed and seed; usually leads and is the first cheque; paper-plan stage is fine (allincapital.vc/apply_now)",
    "Sector-agnostic with special focus on consumer tech, deeptech, fintech, consumer brands (Inc42, Outlook Business, Fund II)",
    "'Why now' first: what changed, often technology (Kushal Bhagia, Inc42 interview)",
    "Founder-market fit: founders hold the key skill the opportunity needs; 'earned secrets' from past experience (same)",
    "First-time founders need proof they can build (same)",
    "'Dil Chahta Hai' teams: long shared history, complementary skills; 5-6 year commitment (same)",
    "Contra-bets only - no safe or obvious bets; no later-stage companies with revenue and profits (same)",
]


def key_question_for(text):
    import re
    hits = [k for k in KEY_QUESTIONS if re.search(k["match"], text or "", re.I)]
    return hits[:2] or [{"question": "What single number would prove this business model works?", "precedent": "none close"}]


def as_prompt():
    lines = []
    for c in CRITERIA:
        lines.append(f'- {c["key"]} | {c["name"]}: {c["definition"]} Anchors: 5 = {c["anchors"]["5"]}; 3 = {c["anchors"]["3"]}; '
                     f'1 = {c["anchors"]["1"]}. Defined from: {", ".join(c["sources"])}')
    return "\n".join(lines)
