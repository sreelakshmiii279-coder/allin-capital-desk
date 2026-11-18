"""Step 1 - Intake: turn a week's pile (deck text + form response per company) into one record each.
Input folder: data/applications/<Company>_Deck.txt and <Company>_Form*.txt."""
import glob
import os
import re

import config


def slug(name):
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def load_batch(folder=None, batch="2026-W47"):
    folder = folder or os.path.join(config.DATA, "applications")
    by_company = {}
    for path in sorted(glob.glob(os.path.join(folder, "*.txt"))):
        base = os.path.basename(path)
        m = re.match(r"(.+?)_(Deck|Form)", base, re.I)
        if not m:
            continue
        name, kind = m.group(1), m.group(2).lower()
        with open(path, encoding="utf-8") as f:
            text = f.read().replace("\r", "")
        rec = by_company.setdefault(name, {"id": slug(name), "name": name, "batch": batch, "deck_text": "", "form_text": ""})
        rec[f"{kind}_text"] = text
        rec.setdefault("files", []).append(base)
    out = []
    for rec in by_company.values():
        form = rec["form_text"].lower()
        if "warm intro" in form or "introduced by" in form or "referred by" in form:
            rec["source"] = "warm intro"
        elif "public application form" in form:
            rec["source"] = "public form"
        else:
            rec["source"] = "unknown"
        rec["missing_docs"] = [k for k in ("deck_text", "form_text") if not rec[k].strip()]
        out.append(rec)
    return out


if __name__ == "__main__":
    for r in load_batch():
        print(r["id"], r["source"], len(r["deck_text"]), len(r["form_text"]), r["missing_docs"])
