"""python run.py                 -> run this week's batch (data/applications) into the review queue
   python run.py talkbook        -> one company
   python run.py --seed          -> load the partner-notes corrections into the feedback store (once)"""
import sys

import feedback
import pipeline

if __name__ == "__main__":
    args = sys.argv[1:]
    if "--seed" in args:
        print("seeded corrections:", feedback.seed()); args.remove("--seed")
        if not args:
            sys.exit()
    reads = pipeline.run_batch(only=set(args) or None)
    for r in sorted(reads, key=lambda r: -(r.get("score_revealed") or 0)):
        print(f'{r["company"]:<14} {str(r.get("score_revealed")):>4} (written {r.get("score_written")})  {r["recommendation"]:<45} '
              f'flags={[f["key"] for f in r.get("flags", [])]} untraced={r.get("claims_untraced")}/{r.get("claims_total")} {r.get("seconds")}s {r.get("error","")}')
