# -*- coding: utf-8 -*-
"""T3 cross-market consistency (DERIVED metric, no model call).
Compiles Li Auto FY2025 figures extracted by the model from the US 20-F (T2) and
the HK annual report (T2), normalizes units, and reports the fraction of the 6
controlled items that agree across the two disclosures.
Usage: python score_t3.py --pred-dir results/<model>/outputs/standard [--out t3.json]
Frozen from the v1.0 reference implementation (compare_models.t3).
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import score  # noqa: E402

T3_ITEMS = ["revenue", "gross_profit", "net_income", "total_assets",
            "cash_and_equivalents", "deliveries_total"]
DOC_A = "li_us_20f_fy2025__T2__r1.json"
DOC_B = "li_hk_ar_fy2025__T2__r1.json"
PERIOD = "FY2025"


def get_metric(obj, item, period):
    for ln in obj.get("statements", []) + obj.get("key_metrics", []):
        if ln.get("item") == item and ln.get("period") == period:
            return ln
    return None


def score_t3(pred_dir):
    try:
        with open(os.path.join(pred_dir, DOC_A), encoding="utf-8") as f:
            a = json.load(f)
        with open(os.path.join(pred_dir, DOC_B), encoding="utf-8") as f:
            b = json.load(f)
    except FileNotFoundError:
        return None
    match, rows = 0, []
    for it in T3_ITEMS:
        la, lb = get_metric(a, it, PERIOD), get_metric(b, it, PERIOD)
        ok = bool(la and lb and score.close(score.canon(la["value"], la["unit"]),
                                            score.canon(lb["value"], lb["unit"]), la["unit"]))
        match += ok
        rows.append({"item": it, "doc_a": la, "doc_b": lb, "consistent": ok})
    return {"consistent": match, "total": len(T3_ITEMS),
            "rate": round(match / len(T3_ITEMS), 4), "rows": rows}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pred-dir", required=True)
    ap.add_argument("--out")
    args = ap.parse_args()
    res = score_t3(args.pred_dir)
    if res is None:
        print("T3 unavailable: missing T2 r1 outputs for li_us_20f_fy2025 / li_hk_ar_fy2025")
        return
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(res, f, ensure_ascii=False, indent=2)
    print(json.dumps({k: res[k] for k in ("consistent", "total", "rate")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
