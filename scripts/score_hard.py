# -*- coding: utf-8 -*-
"""Hard-tier scorer: T6 legal element overlap + T7 scanned OCR accuracy.
Usage: python score_hard.py --pred-dir results/<model>/outputs/hard [--gt-dir groundtruth/hard] [--out metrics.json]
Averages 2 runs. T6 uses char-bigram Jaccard element matching; T7 uses key_facts value match.
Scoring logic is frozen from AutoFinPDF-Bench v1.0 reference implementation (do not edit
without a benchmark version bump).
"""
import argparse
import glob
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def bigrams(s):
    s = re.sub(r"\s+", "", str(s))
    return set(s[i:i + 2] for i in range(len(s) - 1)) if len(s) > 1 else ({s} if s else set())


def jac(a, b):
    A, B = bigrams(a), bigrams(b)
    return len(A & B) / len(A | B) if (A | B) else 0.0


def norm_val(v):
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).replace(",", "").replace("，", "").strip()
    try:
        return float(s)
    except ValueError:
        return s


def val_match(a, b):
    na, nb = norm_val(a), norm_val(b)
    if isinstance(na, float) and isinstance(nb, float):
        return abs(na - nb) <= max(0.5, abs(na) * 0.005)
    return jac(str(a), str(b)) >= 0.8 or str(na) == str(nb)


def match_elements(gt_list, pred_list, thr=0.3):
    """Return (recall, precision, f1) by best-overlap element matching."""
    if not gt_list and not pred_list:
        return 1.0, 1.0, 1.0
    if not gt_list:
        return 0.0, 0.0, 0.0
    if not pred_list:
        return 0.0, 0.0, 0.0
    gt_texts = [e.get("content") or e.get("topic") or e.get("term") or "" for e in gt_list]
    pd_texts = [e.get("content") or e.get("topic") or e.get("term") or "" for e in pred_list]
    rec = sum(1 for g in gt_texts if max((jac(g, p) for p in pd_texts), default=0) >= thr) / len(gt_texts)
    prec = sum(1 for p in pd_texts if max((jac(p, g) for g in gt_texts), default=0) >= thr) / len(pd_texts)
    f1 = 2 * rec * prec / (rec + prec) if (rec + prec) else 0.0
    return rec, prec, f1


def score_t6(gt, pred):
    cats = ["parties", "approvals", "assumptions", "qualifications", "key_clauses", "risk_flags", "definitions"]
    rs, ps = [], []
    per_cat = {}
    for c in cats:
        r, p, f = match_elements(gt.get(c, []), pred.get(c, []))
        per_cat[c] = {"gt": len(gt.get(c, [])), "pred": len(pred.get(c, [])),
                      "recall": round(r, 3), "precision": round(p, 3)}
        if gt.get(c):
            rs.append(r)
            ps.append(p)
    conc = jac(gt.get("conclusion", {}).get("overall", ""), pred.get("conclusion", {}).get("overall", ""))
    rec = sum(rs) / len(rs) if rs else 0.0
    prec = sum(ps) / len(ps) if ps else 0.0
    f1 = 2 * rec * prec / (rec + prec) if (rec + prec) else 0.0
    return {"element_recall": round(rec, 3), "element_precision": round(prec, 3),
            "element_f1": round(f1, 3), "conclusion_overlap": round(conc, 3), "per_category": per_cat}


def score_t7(gt, pred):
    gf, pf = gt.get("key_facts", []), pred.get("key_facts", [])
    matched = 0
    for g in gf:
        ok = any(jac(g.get("item", ""), p.get("item", "")) >= 0.3 and val_match(g.get("value"), p.get("value"))
                 for p in pf)
        matched += ok
    fact_recall = matched / len(gf) if gf else 0.0
    fact_prec = matched / len(pf) if pf else 0.0
    gp = {p.get("name", "") for p in gt.get("parties", [])}
    pp = {p.get("name", "") for p in pred.get("parties", [])}
    party_rec = (sum(1 for g in gp if max((jac(g, p) for p in pp), default=0) >= 0.5) / len(gp)) if gp else 0.0
    date_ok = jac(gt.get("meta", {}).get("date", ""), pred.get("meta", {}).get("date", "")) >= 0.8
    title_ok = jac(gt.get("meta", {}).get("title", ""), pred.get("meta", {}).get("title", "")) >= 0.5
    return {"fact_recall": round(fact_recall, 3), "fact_precision": round(fact_prec, 3),
            "gt_facts": len(gf), "pred_facts": len(pf), "party_recall": round(party_rec, 3),
            "date_match": bool(date_ok), "title_match": bool(title_ok)}


def score_directory(gt_dir, pred_dir):
    results = {}
    for gpath in sorted(glob.glob(os.path.join(gt_dir, "*.json"))):
        name = os.path.basename(gpath)
        base = name[:-5]
        tier = "T6" if base.endswith("__T6") else "T7"
        with open(gpath, encoding="utf-8") as f:
            gt = json.load(f)
        runs = []
        for r in (1, 2):
            pp = os.path.join(pred_dir, "%s__r%d.json" % (base, r))
            if os.path.exists(pp):
                with open(pp, encoding="utf-8") as f:
                    pred = json.load(f)
                runs.append(score_t6(gt, pred) if tier == "T6" else score_t7(gt, pred))
        if not runs:
            results[name] = {"error": "no prediction"}
            continue
        keys = [k for k in runs[0] if isinstance(runs[0][k], (int, float, bool))]
        avg = {k: round(sum(float(r[k]) for r in runs) / len(runs), 3) for k in keys}
        avg["runs"] = len(runs)
        avg["tier"] = tier
        results[name] = avg
    return results


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--gt-dir", default=os.path.join(ROOT, "groundtruth", "hard"))
    ap.add_argument("--pred-dir", required=True)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    results = score_directory(args.gt_dir, args.pred_dir)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
    for name, m in results.items():
        print(name, json.dumps({k: v for k, v in m.items() if k != "per_category"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
