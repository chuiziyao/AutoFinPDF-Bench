# -*- coding: utf-8 -*-
"""Parse raw chat-mode responses into scored JSON outputs.

Reads <out>/raw/*.txt (saved by the operator from the model under test), extracts
the JSON object exactly like the API runner does, and writes it to the layout the
scorers expect. Also merges prospectus chunks into prospectus__B.json.

Usage: python scripts/parse_outputs.py --out results/<slug>/outputs
"""
import argparse
import glob
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import run_eval  # noqa: E402

STANDARD_TASKS = {"T1", "T2", "T4", "T5"}
HARD_TASKS = {"T6", "T7"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    raw_dir = os.path.join(args.out, "raw")
    if not os.path.isdir(raw_dir):
        raise SystemExit("no raw directory: " + raw_dir)
    ok = bad = 0
    chunks = []
    for p in sorted(glob.glob(os.path.join(raw_dir, "*.txt"))):
        rid = os.path.basename(p)[:-4]
        with open(p, encoding="utf-8") as f:
            text = f.read()
        obj = run_eval.extract_json(text)
        if rid.startswith("chunk_"):
            if obj is None:
                obj = {"_error": "no JSON in raw response"}
                bad += 1
            else:
                ok += 1
            m = re.match(r"chunk_(\d+)_(\d+)", rid)
            if m:
                obj["_pages"] = [int(m.group(1)), int(m.group(2))]
            cd = os.path.join(args.out, "reits", "prospectus_chunks")
            os.makedirs(cd, exist_ok=True)
            with open(os.path.join(cd, rid + ".json"), "w", encoding="utf-8") as f:
                json.dump(obj, f, ensure_ascii=False, indent=2)
            chunks.append(obj)
            continue
        if obj is None:
            print("NO-JSON:", rid)
            bad += 1
            continue
        m = re.match(r"(.+)__(T\d)__r(\d+)$", rid)
        if m:
            did, task, _r = m.groups()
            track = "standard" if task in STANDARD_TASKS else "hard"
            dest = os.path.join(args.out, track, rid + ".json")
        elif rid.endswith("__A"):
            dest = os.path.join(args.out, "reits", rid + ".json")
        else:
            print("SKIP (unknown rid pattern):", rid)
            continue
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        with open(dest, "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False, indent=2)
        ok += 1
    if chunks:
        chunks.sort(key=lambda c: c.get("_pages", [0])[0])
        bench = json.load(open(os.path.join(ROOT, "benchmark.json"), encoding="utf-8"))
        total = 1511
        merged = run_eval.merge_prospectus(chunks, total)
        dest = os.path.join(args.out, "reits", "prospectus__B.json")
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        with open(dest, "w", encoding="utf-8") as f:
            json.dump(merged, f, ensure_ascii=False, indent=2)
        print("merged %d chunks -> %s" % (len(chunks), dest))
    print("parsed ok=%d bad=%d" % (ok, bad))
    if bad:
        sys.exit(1)


if __name__ == "__main__":
    main()
