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
REPLY_WINDOW_WORKING_HOURS = 72  # 3 working days of silence -> one follow-up

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

# --- Cost (Case 04 task 5) ---
# ASSUMED list prices in USD - confirm against your Google AI Studio billing page and change here; every cost figure uses them.
PRICE_IN_PER_M = float(os.environ.get("PRICE_IN_PER_M", "0.30"))       # per 1M input tokens
PRICE_OUT_PER_M = float(os.environ.get("PRICE_OUT_PER_M", "2.50"))     # per 1M output (incl. thinking) tokens
PRICE_SEARCH_PER_CALL = float(os.environ.get("PRICE_SEARCH_PER_CALL", "0.035"))  # Google Search grounding, per grounded call
PRICE_EMBED_PER_M = float(os.environ.get("PRICE_EMBED_PER_M", "0.15"))
USD_INR = float(os.environ.get("USD_INR", "88"))
DAILY_COST_LIMIT_INR = float(os.environ.get("DAILY_COST_LIMIT_INR", "4000"))   # 100 applications x ~INR 34 (volume test) + headroom

# --- Gateway + tracing (Case 04 tasks 3 and 4) - switch on by adding keys to .env ---
PORTKEY_API_KEY = os.environ.get("PORTKEY_API_KEY", "").strip()
PORTKEY_PROVIDER = os.environ.get("PORTKEY_PROVIDER", "google").strip()   # "google" (key sent per request) or "@your-slug"
PORTKEY_RETRY_ATTEMPTS = int(os.environ.get("PORTKEY_RETRY_ATTEMPTS", "3"))
PORTKEY_ROUTE_SEARCH = os.environ.get("PORTKEY_ROUTE_SEARCH", "1") == "1"
LANGFUSE_PUBLIC_KEY = os.environ.get("LANGFUSE_PUBLIC_KEY", "").strip()
LANGFUSE_SECRET_KEY = os.environ.get("LANGFUSE_SECRET_KEY", "").strip()
LANGFUSE_HOST = os.environ.get("LANGFUSE_HOST", "https://cloud.langfuse.com").strip()

# --- Queue (Case 04 task 2) ---
QUEUE_WORKERS = int(os.environ.get("QUEUE_WORKERS", "3"))      # applications processed at once (Gemini rate limits)
JOB_MAX_ATTEMPTS = 2                                            # a job that fails twice becomes "needs attention"
JOB_STUCK_MINUTES = 15                                          # a 'running' job older than this is reclaimed
EDIT_PASSWORD = os.environ.get("EDIT_PASSWORD", "").strip()   # needed to accept/correct/book in the web app

# --- Consistency ---
SCORE_SAMPLES = int(os.environ.get("SCORE_SAMPLES", "2"))   # score twice, average, gates need agreement (volume test)

# --- Google News (world context) ---
NEWS_CACHE_HOURS = int(os.environ.get("NEWS_CACHE_HOURS", "12"))
NEWS_DAYS_COMPANY = 365     # company mentions: last year
NEWS_DAYS_SECTOR = 90       # sector context: last quarter
