"""Re-run this week's 10 real applications through the intake queue (same path as production), then drain it."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import intake  # noqa: E402
import jobqueue  # noqa: E402

recs = intake.load_batch(batch="2026-W47")
apps = [{"name": r["name"], "form": r["form_text"], "deck": r["deck_text"]} for r in recs]
ids = jobqueue.enqueue(apps, "2026-W47")
print("queued", len(ids), flush=True)
while True:
    out = jobqueue.work(deadline_s=10_000)
    print(out, jobqueue.counts("2026-W47"), flush=True)
    if not out["processed"]:
        break
