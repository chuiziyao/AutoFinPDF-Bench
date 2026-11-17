# -*- coding: utf-8 -*-
"""Unified scoring orchestrator: produces results/<slug>/summary.json + metrics/.

Usage:
  python scripts/score_all.py --slug my-model --name "My Model v1" \
      [--version api-id] [--provider Vendor] [--date YYYY-MM-DD] [--notes "..."]

Reads outputs from results/<slug>/outputs/{standard,hard,reits}/ and scores every
track with the frozen v1.0 scorers:
  T1/T2/T5  -> scripts/score.py (field-level P/R/F1; T5 chart tolerance)
  T3        -> scripts/score_t3.py (derived cross-market consistency)
  T4        -> collected, qualitative (not numerically scored)
  T6/T7     -> scripts/score_hard.py
  REITs A/B -> scripts/score_reits.py (validation-based)

Overall = mean(T1.f1, T2.f1, T5.f1, T6.element_f1, T7.fact_recall,
               REITs_A.score, REITs_B.score) over AVAILABLE tiers; a submission
missing any tier is flagged partial (overall still shown, marked † on the board).
"""
import argparse
import datetime
import hashlib
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import score_hard  # noqa: E402
import score_t3  # noqa: E402
import score_reits  # noqa: E402

SCORER_FILES = ["score.py", "score_hard.py", "score_t3.py", "score_reits.py", "score_all.py",
                "run_eval.py", "make_taskpack.py", "parse_outputs.py"]
OVERALL_KEYS = [("T1", "f1"), ("T2", "f1"), ("T5", "f1"),
                ("T6", "element_f1"), ("T7", "fact_recall"),
                ("REITs_A", "score"), ("REITs_B", "score")]


def scorer_hash():
    h = hashlib.sha256()
    for fn in SCORER_FILES:
        with open(os.path.join(HERE, fn), "rb") as f:
            h.update(f.read())
    return h.hexdigest()


def load(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def run_score_py(gt_dir, pred_dir, filt, chart, out):
    cmd = [sys.executable, os.path.join(HERE, "score.py"),
           "--gt-dir", gt_dir, "--pred-dir", pred_dir, "--filter", filt, "--out", out]
    if chart:
        cmd.append("--chart")
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    if r.returncode != 0:
        raise RuntimeError("score.py failed: " + r.stderr[-500:])
    return load(out)


def avg_doc_metric(per_doc, suffix, key):
    vals = [v[key] for k, v in per_doc.items() if k.endswith(suffix) and key in v]
    return round(sum(vals) / len(vals), 3) if vals else None


def compute_tracks(pred_root, metrics_dir):
    os.makedirs(metrics_dir, exist_ok=True)
    tracks = {}
    std = os.path.join(pred_root, "standard")
    gt = os.path.join(ROOT, "groundtruth")
    if os.path.isdir(std):
        for tier, chart in (("T1", False), ("T2", False), ("T5", True)):
            out = os.path.join(metrics_dir, tier + ".json")
            res = run_score_py(gt, std, "__" + tier, chart, out)
            tracks[tier] = res.get("aggregate", {})
        t3 = score_t3.score_t3(std)
        if t3 is not None:
            with open(os.path.join(metrics_dir, "T3.json"), "w", encoding="utf-8") as f:
                json.dump(t3, f, ensure_ascii=False, indent=2)
            tracks["T3"] = {k: t3[k] for k in ("consistent", "total", "rate")}
        n_t4 = len([f for f in os.listdir(std) if "__T4__" in f and f.endswith(".json")])
        if n_t4:
            tracks["T4"] = {"status": "collected", "output_files": n_t4,
                            "note": "qualitative deep-understanding tier; reviewed by maintainers, not numerically scored"}
    hard = os.path.join(pred_root, "hard")
    if os.path.isdir(hard):
        per_doc = score_hard.score_directory(os.path.join(gt, "hard"), hard)
        with open(os.path.join(metrics_dir, "hard.json"), "w", encoding="utf-8") as f:
            json.dump(per_doc, f, ensure_ascii=False, indent=2)
        t6 = {"element_f1": avg_doc_metric(per_doc, "__T6.json", "element_f1"),
              "element_recall": avg_doc_metric(per_doc, "__T6.json", "element_recall"),
              "element_precision": avg_doc_metric(per_doc, "__T6.json", "element_precision"),
              "conclusion_overlap": avg_doc_metric(per_doc, "__T6.json", "conclusion_overlap"),
              "documents": sum(1 for k in per_doc if k.endswith("__T6.json") and "element_f1" in per_doc[k])}
        t7 = {"fact_recall": avg_doc_metric(per_doc, "__T7.json", "fact_recall"),
              "fact_precision": avg_doc_metric(per_doc, "__T7.json", "fact_precision"),
              "party_recall": avg_doc_metric(per_doc, "__T7.json", "party_recall"),
              "documents": sum(1 for k in per_doc if k.endswith("__T7.json") and "fact_recall" in per_doc[k])}
        if t6["element_f1"] is not None:
            tracks["T6"] = t6
        if t7["fact_recall"] is not None:
            tracks["T7"] = t7
    reits = os.path.join(pred_root, "reits")
    if os.path.isdir(reits):
        ra = score_reits.score_a(reits)
        rb = score_reits.score_b(reits)
        with open(os.path.join(metrics_dir, "reits.json"), "w", encoding="utf-8") as f:
            json.dump({"REITs_A": ra, "REITs_B": rb}, f, ensure_ascii=False, indent=2)
        if ra["fields"] > 0:
            tracks["REITs_A"] = ra
        if rb is not None:
            tracks["REITs_B"] = rb
    return tracks


def overall_of(tracks):
    vals = []
    for tier, key in OVERALL_KEYS:
        t = tracks.get(tier) or {}
        v = t.get(key)
        if v is None:
            return (round(sum(vals) / len(vals), 4) if vals else None), True
        vals.append(v)
    return round(sum(vals) / len(vals), 4), False


def build_summary(slug, name, version, provider, date, notes, pred_root, metrics_dir):
    bench = load(os.path.join(ROOT, "benchmark.json"))
    tracks = compute_tracks(pred_root, metrics_dir)
    overall, partial = overall_of(tracks)
    return {
        "schema_version": "1.0",
        "model": {"slug": slug, "name": name, "version": version or "", "provider": provider or ""},
        "benchmark_version": bench["version"],
        "scorer_hash": scorer_hash(),
        "submitted_at": date or datetime.date.today().isoformat(),
        "verification": "self-reported",
        "tracks": tracks,
        "overall": overall,
        "partial": partial,
        "notes": notes or "",
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--slug", required=True, help="results directory name, e.g. my-model-v1")
    ap.add_argument("--name", required=True, help="display name, e.g. My Model v1")
    ap.add_argument("--version", default="", help="API model id / version string")
    ap.add_argument("--provider", default="")
    ap.add_argument("--date", default="", help="submission date YYYY-MM-DD (default today)")
    ap.add_argument("--notes", default="")
    ap.add_argument("--pred", default=None, help="outputs root (default results/<slug>/outputs)")
    ap.add_argument("--out", default=None, help="summary path (default results/<slug>/summary.json)")
    args = ap.parse_args()
    res_dir = os.path.join(ROOT, "results", args.slug)
    pred = args.pred or os.path.join(res_dir, "outputs")
    out = args.out or os.path.join(res_dir, "summary.json")
    if not os.path.isdir(pred):
        raise SystemExit("outputs not found: %s" % pred)
    summary = build_summary(args.slug, args.name, args.version, args.provider,
                            args.date, args.notes, pred, os.path.join(res_dir, "metrics"))
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(json.dumps({"overall": summary["overall"], "partial": summary["partial"],
                      "tiers": {k: (v.get("f1") or v.get("element_f1") or v.get("fact_recall")
                                    or v.get("rate") or v.get("score"))
                                for k, v in summary["tracks"].items()}},
                     ensure_ascii=False, indent=2))
    print("summary ->", out)


if __name__ == "__main__":
    main()
