# -*- coding: utf-8 -*-
"""Download ORIGINAL disclosure documents (PDF/HTM) for verification / optional
pdf-native runs. The official benchmark inputs are the hashed extracted texts and
page images already in data/ — this script is NOT required to participate.

Downloads to corpus_original/<original_file>, verifies sha256 against data/manifest.json.
Stdlib only. Be polite: sequential downloads, identifying User-Agent.

Usage:
  python scripts/fetch_corpus.py [--only li_us_20f_fy2025] [--dest corpus_original]
"""
import argparse
import hashlib
import json
import os
import sys
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
UA = "AutoFinPDF-Bench/1.0 (open benchmark; +https://github.com/OWNER/AutoFinPDF-Bench)"


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="", help="comma-separated doc ids")
    ap.add_argument("--dest", default=os.path.join(ROOT, "corpus_original"))
    args = ap.parse_args()
    manifest = json.load(open(os.path.join(ROOT, "data", "manifest.json"), encoding="utf-8"))
    only = set(args.only.split(",")) if args.only else None
    ok = skip = fail = nourl = 0
    for m in manifest:
        if only and m["id"] not in only:
            continue
        url, rel, want = m.get("source_url"), m.get("original_file"), m.get("sha256_original")
        if not url or not rel:
            nourl += 1
            print("[no-url] %s — %s" % (m["id"], m.get("source_note") or "见 manifest"))
            continue
        dest = os.path.join(args.dest, rel)
        if os.path.exists(dest) and want and sha256(dest) == want:
            skip += 1
            continue
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=120) as resp, open(dest, "wb") as f:
                f.write(resp.read())
            if want and sha256(dest) != want:
                print("[HASH-MISMATCH] %s (downloaded != manifest)" % m["id"])
                fail += 1
                continue
            print("[ok] %s -> %s" % (m["id"], dest))
            ok += 1
            time.sleep(1.0)
        except Exception as e:  # noqa: BLE001
            print("[fail] %s: %s" % (m["id"], str(e)[:160]))
            fail += 1
    print("done: ok=%d cached=%d fail=%d no-url=%d" % (ok, skip, fail, nourl))
    if fail:
        sys.exit(1)


if __name__ == "__main__":
    main()
