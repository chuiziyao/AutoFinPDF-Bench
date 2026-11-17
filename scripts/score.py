# -*- coding: utf-8 -*-
"""Deterministic field-level scoring for AutoFinPDF-Bench (T1/T2 numeric extraction).
Usage:
  python score.py --gt gt.json --pred pred.json [--out metrics.json]
  python score.py --gt-dir groundtruth/ --pred-dir runs/<model>/ [--out agg.json]
Both files share schema/extraction_schema.json shape. Matching key = (group,item,period,currency).
Metrics: precision/recall/F1, exact_match_rate, coverage, hallucination_rate, value_error_rate.
"""
import argparse
import glob
import json
import os
import sys

# magnitude -> factor to canonical "million currency units"
MAG = {"yuan": 1e-6, "thousand": 1e-3, "million": 1.0, "billion": 1e3,
       "wan": 0.01, "yi": 100.0, "percent": 1.0, "count": 1.0, "yuan_per_share": 1.0}
# Cost-type items: match by absolute value to neutralize US GAAP (negative) vs CAS (positive)
# presentation differences. Profit / cash-flow-net signs remain meaningful and are preserved.
COST_ITEMS = {"cost_of_revenue", "operating_expenses", "capex"}
# Optional derived ratios: if the model outputs these beyond GT, treat as bonus
# (correct derivation invited by the prompt), not hallucination. Stated ones in GT score normally.
OPTIONAL_METRICS = {"gross_margin", "operating_margin", "net_margin", "vehicle_margin",
                    "revenue_yoy", "deliveries_total", "cash_and_short_term_investments"}


def canon(value, unit):
    return float(value) * MAG.get(unit, 1.0)


def flatten(obj, periods=None):
    """Return dict key->record for statements/key_metrics/deliveries.
    If periods given, only fields whose period/month is in periods are kept."""
    fields = {}
    for ln in obj.get("statements", []) + obj.get("key_metrics", []):
        per = str(ln.get("period", "")).strip()
        if periods is not None and per not in periods:
            continue
        key = (ln.get("statement", ""), str(ln.get("item", "")).strip().lower(),
               per, ln.get("currency", ""))
        fields[key] = ln
    for d in obj.get("deliveries", []):
        mon = str(d.get("month", "")).strip()
        if periods is not None and mon not in periods:
            continue
        key = ("delivery", str(d.get("model", "")).strip().lower(), mon, "CNY")
        fields[key] = {"value": d.get("count"), "unit": "count", "page": d.get("page")}
    return fields


def close(a, b, unit, rel_tol=0.005, pct_tol=0.1):
    if unit == "count":
        return abs(a - b) < 0.5
    if unit == "percent":
        return abs(a - b) <= pct_tol
    if a == 0 and b == 0:
        return True
    denom = max(abs(a), abs(b), 1e-9)
    return abs(a - b) / denom <= rel_tol


def score_pair(gt, pred, rel_tol=0.005, pct_tol=0.1, periods=None):
    g = flatten(gt, periods)
    p = flatten(pred, periods)
    tp = fp = fn = halluc = value_err = exact = 0
    errors = []
    for key, gl in g.items():
        if key not in p:
            fn += 1
            errors.append({"type": "missing", "key": list(key)})
            continue
        pl = p[key]
        gv, pv = canon(gl["value"], gl["unit"]), canon(pl["value"], pl["unit"])
        if key[1] in COST_ITEMS:
            gv, pv = abs(gv), abs(pv)
        if close(gv, pv, gl["unit"], rel_tol, pct_tol):
            tp += 1
            if abs(gv - pv) < 1e-9:
                exact += 1
        else:
            fn += 1
            fp += 1
            value_err += 1
            errors.append({"type": "value_mismatch", "key": list(key),
                           "gt": gl["value"], "pred": pl["value"],
                           "gt_unit": gl["unit"], "pred_unit": pl["unit"]})
    for key in p:
        if key not in g:
            if key[0] == "metric" and key[1] in OPTIONAL_METRICS:
                continue
            fp += 1
            halluc += 1
            errors.append({"type": "hallucination", "key": list(key)})
    prec = tp / (tp + fp) if (tp + fp) else 0.0
    rec = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * prec * rec / (prec + rec) if (prec + rec) else 0.0
    return {
        "gt_fields": len(g), "pred_fields": len(p),
        "tp": tp, "fp": fp, "fn": fn,
        "precision": round(prec, 4), "recall": round(rec, 4), "f1": round(f1, 4),
        "exact_match_rate": round(exact / len(g), 4) if g else 0.0,
        "coverage": round((len(g) - sum(1 for e in errors if e["type"] == "missing")) / len(g), 4) if g else 0.0,
        "hallucination_rate": round(halluc / len(p), 4) if p else 0.0,
        "value_error_rate": round(value_err / len(g), 4) if g else 0.0,
        "errors": errors,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--gt")
    ap.add_argument("--pred")
    ap.add_argument("--gt-dir")
    ap.add_argument("--pred-dir")
    ap.add_argument("--out")
    ap.add_argument("--chart", action="store_true",
                    help="T5 chart-reading tolerance: rel 3%%, percent +/-1.5pp (reported separately)")
    ap.add_argument("--filter", default="", help="only score GT filenames containing this substring")
    args = ap.parse_args()
    rel_tol, pct_tol = (0.03, 1.5) if args.chart else (0.005, 0.1)

    results = {}
    if args.gt and args.pred:
        with open(args.gt, encoding="utf-8") as f:
            gt = json.load(f)
        with open(args.pred, encoding="utf-8") as f:
            pred = json.load(f)
        results[os.path.basename(args.gt)] = score_pair(gt, pred, rel_tol, pct_tol)
    elif args.gt_dir and args.pred_dir:
        mkeys = ["precision", "recall", "f1", "exact_match_rate", "coverage",
                 "hallucination_rate", "value_error_rate"]
        tp_path = os.path.join(args.gt_dir, "target_periods.json")
        tp = {}
        if os.path.exists(tp_path):
            with open(tp_path, encoding="utf-8") as f:
                tp = json.load(f)
        for gpath in sorted(glob.glob(os.path.join(args.gt_dir, "*.json"))):
            name = os.path.basename(gpath)
            if args.filter and args.filter not in name:
                continue
            with open(gpath, encoding="utf-8") as f:
                gt = json.load(f)
            base = name[:-5] if name.endswith(".json") else name
            preds = sorted(glob.glob(os.path.join(args.pred_dir, base + "__r*.json")))
            if not preds:
                single = os.path.join(args.pred_dir, name)
                preds = [single] if os.path.exists(single) else []
            if not preds:
                results[name] = {"error": "prediction missing"}
                continue
            runs = []
            periods = (tp.get(base) or tp.get(base.rsplit("__", 1)[0])) if base.endswith("__T2") else None
            for pp in preds:
                with open(pp, encoding="utf-8") as f:
                    pred = json.load(f)
                runs.append(score_pair(gt, pred, rel_tol, pct_tol, periods))
            avg = {k: round(sum(r[k] for r in runs) / len(runs), 4) for k in mkeys}
            avg["runs"] = len(runs)
            avg["gt_fields"] = runs[0]["gt_fields"]
            avg["pred_fields"] = runs[0]["pred_fields"]
            avg["per_run_f1"] = [r["f1"] for r in runs]
            avg["errors_r1"] = runs[0]["errors"]
            results[name] = avg
    else:
        ap.error("provide --gt/--pred or --gt-dir/--pred-dir")

    scored = [r for r in results.values() if "f1" in r]
    agg = {}
    if scored:
        n = len(scored)
        agg = {k: round(sum(r[k] for r in scored) / n, 4)
               for k in ["precision", "recall", "f1", "exact_match_rate",
                         "coverage", "hallucination_rate", "value_error_rate"]}
        agg["documents"] = n
        agg["total_gt_fields"] = sum(r["gt_fields"] for r in scored)
    out = {"aggregate": agg, "per_document": results}
    text = json.dumps(out, ensure_ascii=False, indent=2)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(text)
    print(json.dumps(agg, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    sys.exit(main())
