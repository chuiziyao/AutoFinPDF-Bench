# -*- coding: utf-8 -*-
"""Validate a results submission (used locally and by CI on every PR).

Checks:
  1. summary.json exists, required fields present
  2. benchmark_version matches the frozen benchmark
  3. scorer_hash matches the current frozen scorers (re-score if stale)
  4. every claimed tier's score RE-COMPUTES from the submitted raw outputs
  5. output completeness: all expected files for claimed tracks exist
  6. evidence present (usage.jsonl or recording.csv) — required for merge

Usage:
  python scripts/validate_submission.py results/my-model
  python scripts/validate_submission.py --all
"""
import argparse
import json
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import score_all  # noqa: E402

EPS = 1e-6


def load(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def flatten_scores(tracks):
    flat = {}
    for tier, t in tracks.items():
        if not isinstance(t, dict):
            continue
        for k, v in t.items():
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                flat["%s.%s" % (tier, k)] = v
    return flat


def expected_files(bench, tracks_claimed):
    exp = []
    for inst in bench["instances"]:
        track = inst["track"]
        claimed = {"standard": any(t in tracks_claimed for t in ("T1", "T2", "T4", "T5")),
                   "hard": any(t in tracks_claimed for t in ("T6", "T7")),
                   "reits": any(t in tracks_claimed for t in ("REITs_A", "REITs_B"))}[track]
        if not claimed:
            continue
        if track == "reits":
            name = "prospectus__B.json" if inst["task_id"] == "B" else inst["doc_id"] + "__A.json"
            exp.append(os.path.join("outputs", "reits", name))
        else:
            for r in range(1, inst["runs"] + 1):
                exp.append(os.path.join("outputs", track,
                                        "%s__%s__r%d.json" % (inst["doc_id"], inst["task_id"], r)))
    return exp


def validate(res_dir, bench):
    problems, warnings = [], []
    slug = os.path.basename(res_dir.rstrip("/\\"))
    sp = os.path.join(res_dir, "summary.json")
    if not os.path.exists(sp):
        return ["summary.json missing"], []
    summary = load(sp)
    for field in ("model", "benchmark_version", "scorer_hash", "tracks", "overall", "submitted_at"):
        if field not in summary:
            problems.append("summary.json missing field: " + field)
    if problems:
        return problems, warnings
    if summary["benchmark_version"] != bench["version"]:
        problems.append("benchmark_version %s != current %s (re-run under the frozen benchmark)"
                        % (summary["benchmark_version"], bench["version"]))
    if not (summary.get("model") or {}).get("submitter"):
        problems.append("model.submitter missing — pass the submitter's GitHub username via score_all.py --submitter")
    if summary["scorer_hash"] != score_all.scorer_hash():
        problems.append("scorer_hash stale — re-run scripts/score_all.py with the current scorers")
    tracks = summary["tracks"]
    # completeness
    for rel in expected_files(bench, set(tracks.keys())):
        if not os.path.exists(os.path.join(res_dir, rel)):
            problems.append("missing output: " + rel)
    # recompute (scratch dir inside the repo: portable across sandboxes/CI)
    td = os.path.join(ROOT, ".validate_tmp", slug)
    os.makedirs(td, exist_ok=True)
    try:
        recomputed = score_all.compute_tracks(os.path.join(res_dir, "outputs"), td)
    finally:
        shutil.rmtree(td, ignore_errors=True)
    a, b = flatten_scores(tracks), flatten_scores(recomputed)
    for k in sorted(set(a) | set(b)):
        va, vb = a.get(k), b.get(k)
        if va is None or vb is None:
            problems.append("score key mismatch: %s (claimed=%s recomputed=%s)" % (k, va, vb))
        elif abs(va - vb) > EPS:
            problems.append("score mismatch: %s claimed=%s recomputed=%s" % (k, va, vb))
    ov, partial = score_all.overall_of(recomputed)
    if summary.get("overall") is None or ov is None:
        if summary.get("overall") != ov:
            problems.append("overall mismatch: claimed=%s recomputed=%s" % (summary.get("overall"), ov))
    elif abs(summary["overall"] - ov) > EPS:
        problems.append("overall mismatch: claimed=%s recomputed=%s" % (summary["overall"], ov))
    # evidence
    ev = os.path.join(res_dir, "evidence")
    has_ev = os.path.isdir(ev) and any(
        os.path.exists(os.path.join(ev, fn))
        for fn in ("usage.jsonl", "usage_standard.jsonl", "recording.csv"))
    if not has_ev:
        problems.append("evidence missing: provide evidence/usage.jsonl (API) or evidence/recording.csv (manual)")
    if summary.get("verification") not in ("self-reported", "verified"):
        warnings.append("unknown verification level: %s" % summary.get("verification"))
    return problems, warnings


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("path", nargs="?", help="results/<slug> directory")
    ap.add_argument("--all", action="store_true")
    args = ap.parse_args()
    bench = load(os.path.join(ROOT, "benchmark.json"))
    if args.all:
        dirs = [os.path.join(ROOT, "results", d) for d in sorted(os.listdir(os.path.join(ROOT, "results")))
                if os.path.isdir(os.path.join(ROOT, "results", d))]
    elif args.path:
        dirs = [args.path]
    else:
        ap.error("provide a results directory or --all")
    failed = 0
    for d in dirs:
        problems, warnings = validate(d, bench)
        name = os.path.basename(d.rstrip("/\\"))
        for w in warnings:
            print("[WARN] %s: %s" % (name, w))
        if problems:
            failed += 1
            print("[FAIL] %s" % name)
            for p in problems:
                print("   - " + p)
        else:
            print("[OK] %s" % name)
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
