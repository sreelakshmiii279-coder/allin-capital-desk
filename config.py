"""Every setting in one place. BUSINESS RULES are marked: change those with Kushal, not alone.
Each rule names the line in the case files it comes from."""
import os
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"), override=True)

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")

# --- Model (technical) ---
MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash")
EXTRACT_TEMPERATURE = 0.0      # pulling facts: no creativity
SCORE_TEMPERATURE = 0.0        # scoring: same input must give the same read
DRAFT_TEMPERATURE = 0.4        # founder emails only

# --- Research loop (S4 evidence map) ---
MAX_TRIES_PER_VARIABLE = 2     # S4: "set loop caps" - a variable gets at most 2 searches
MAX_SEARCHES_PER_APP = 8       # hard cap across all variables (cost + no infinite loops)
MAX_PAGE_CHARS = 5000          # cleaned website text sent to the model (S4: never raw HTML)
FETCH_TIMEOUT_S = 12
USER_AGENT = "AllInCapitalTriageDesk/1.0 (MESA student project)"

# --- Scoring (BUSINESS RULES) ---
# Each criterion is scored 0-5. "unknown" is NOT skipped: it is scored as UNKNOWN_SCORE
# (Partner notes M1: "a missing number should drag the score, not be skipped").
UNKNOWN_SCORE = 1
# Recommendation thresholds on the same 0-100 scale as the overall score.
CALL_THRESHOLD = 60            # >= this, no hard flag, founder & path both >= 3 -> "Take the call"
PASS_THRESHOLD = 40            # < this -> "Pass" (still shown to Kushal; nobody is auto-rejected)
# Founder quality and path to market are separate criteria (Partner notes M3: "Riya had been mixing them").
MIN_FOUNDER_FOR_CALL = 3
MIN_PATH_FOR_CALL = 3

# --- Capability ceiling (S1/S2) - BUSINESS RULE ---
# Calls only Tue/Thu afternoons, 30 minutes (Partner notes M5). 2 afternoons x 4 slots = 8 max;
# Kushal realistically takes ~6. Beyond this the desk ranks "call-worthy, over capacity".
CALL_CAP_PER_WEEK = 6
CALL_DAYS = (1, 3)             # Monday=0 -> Tuesday, Thursday
CALL_SLOTS = ["14:00", "14:45", "15:30", "16:15"]   # IST, 30 min + 15 min buffer
CALL_MINUTES = 30
SLOTS_TO_PROPOSE = 3
ADITYA_JOINS_FOR = {"deeptech"}  # Partner notes M5: "Aditya joins only for deeptech"

# --- Booking agent retry table (S6) ---
MAX_REPLY_ROUNDS = 2           # re-propose times at most twice, then escalate to Riya
TRANSIENT_RETRIES = 3          # email/calendar API timeouts, rate limits (backoff)

# --- Kill criteria (S1/S2) - agreed in advance with Kushal ---
BACKTEST_MIN_AGREEMENT = 10    # of 12 memos, before go-live
OVERRIDE_RATE_KILL = 0.30      # partner overrides of the recommendation, any 4-week window
UNSOURCED_CLAIMS_KILL = 0.05   # share of claims with no traceable source in a run
REVIEW_MINUTES_KILL = 15       # Riya's review time per application, 4-week average

# --- Sending (SAFETY RULE) ---
# Founder emails never go to a founder from this build: they go to TO_ADDRESS (our own inbox), with the
# .ics invite attached, so the flow is real end to end without contacting fictional/real founders.
TO_ADDRESS = os.environ.get("TO_ADDRESS", "").strip()
RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "").strip()
RESEND_FROM = os.environ.get("RESEND_FROM", "").strip() or "All In Capital Desk <onboarding@resend.dev>"

DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()
EDIT_PASSWORD = os.environ.get("EDIT_PASSWORD", "").strip()   # needed to accept/correct/book in the web app
