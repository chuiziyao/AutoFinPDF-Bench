# -*- coding: utf-8 -*-
"""REITs track scorer (validation-based; no field-level human GT exists for REITs).

Task A (16 periodic reports): deterministic output-quality metrics —
  * name_compliance: fraction of fields whose name follows 「项目名-指标名」 (contains '-')
  * page_rate:       fraction of fields carrying a page number
  * priority_counts: raw keyword matches for the 6 scarce priority metrics (comparable
                     with the v1.0 reference report)
  * priority_doc_coverage: per priority metric, fraction of the 16 docs with >=1 match,
                     averaged (normalized, anti-verbosity)
  * score_A = mean(name_compliance, page_rate, priority_doc_coverage)

Task B (1511-page prospectus):
  * basic_completeness: fraction of the 6 basic keys with non-null value
  * page_rate_B: fraction of non-null entries (basic/assets/extras) carrying page_no
  * score_B = mean(basic_completeness, page_rate_B)

Optional page spot-check against the original PDFs (requires pymupdf + fetched corpus):
  python score_reits.py --pred-dir ... --pdf-dir corpus_original --spotcheck
Frozen keyword lists from the v1.0 reference implementation (compare_models.KW).
"""
import argparse
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

BATCH_IDS = ["508021_2024FY", "180102_2025FY", "180202_2025FY", "508007_2025FY",
             "180301_2025FY", "180501_2025FY", "180601_2025FY", "180605_2025FY",
             "180607_2025FY", "180701_2025FY", "508028_2025FY", "508056_2025FY",
             "508060_2025FY", "508068_2025FY", "508087_2025FY", "508096_2026Q2"]
KW = {"WALT": ["walt", "加权剩余租期", "weighted"], "续租率": ["续租"],
      "剩余收费年限": ["剩余收费", "收费年限"], "出租率": ["出租率", "occupancy"],
      "租金单价": ["租金单价", "租金"], "收缴率": ["收缴"]}
BASIC_KEYS = ["raise_size", "fund_term", "offering_price", "total_shares",
              "original_owner", "strategic_ratio"]


def load(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def score_a(pred_dir):
    fields, per_doc, missing = [], {}, []
    for did in BATCH_IDS:
        p = os.path.join(pred_dir, did + "__A.json")
        if not os.path.exists(p):
            missing.append(did)
            per_doc[did] = 0
            continue
        fs = load(p).get("fields", [])
        per_doc[did] = len(fs)
        for f in fs:
            f = dict(f)
            f["_doc"] = did
            fields.append(f)
    n = len(fields)
    name_ok = sum(1 for f in fields if "-" in str(f.get("name", "")))
    page_ok = sum(1 for f in fields if f.get("page") is not None)
    counts = {k: sum(1 for f in fields if any(w in str(f.get("name", "")).lower() for w in kws))
              for k, kws in KW.items()}
    doc_cov = {}
    for k, kws in KW.items():
        hit = sum(1 for did in BATCH_IDS
                  if any(any(w in str(f.get("name", "")).lower() for w in kws)
                         for f in fields if f["_doc"] == did))
        doc_cov[k] = round(hit / len(BATCH_IDS), 4)
    name_compliance = round(name_ok / n, 4) if n else 0.0
    page_rate = round(page_ok / n, 4) if n else 0.0
    priority_doc_coverage = round(sum(doc_cov.values()) / len(doc_cov), 4)
    score = round((name_compliance + page_rate + priority_doc_coverage) / 3, 4)
    return {"docs": len(BATCH_IDS), "docs_missing": missing, "fields": n,
            "fields_per_doc": per_doc,
            "name_compliance": name_compliance, "page_rate": page_rate,
            "priority_counts": counts, "priority_doc_coverage": doc_cov,
            "priority_doc_coverage_avg": priority_doc_coverage, "score": score}


def _entries_b(obj):
    """Yield (value, page_no) for every basic/assets/extras entry."""
    for v in obj.get("basic", {}).values():
        if isinstance(v, dict):
            yield v.get("value"), v.get("page_no")
    for a in obj.get("assets", []):
        for v in a.values():
            if isinstance(v, dict):
                yield v.get("value"), v.get("page_no")
    for e in obj.get("extras", []):
        yield e.get("value"), e.get("page_no")


def score_b(pred_dir):
    p = os.path.join(pred_dir, "prospectus__B.json")
    if not os.path.exists(p):
        return None
    obj = load(p)
    basic = obj.get("basic", {})
    filled = sum(1 for k in BASIC_KEYS
                 if isinstance(basic.get(k), dict) and basic[k].get("value") is not None)
    basic_completeness = round(filled / len(BASIC_KEYS), 4)
    entries = [(v, pg) for v, pg in _entries_b(obj) if v is not None]
    paged = sum(1 for v, pg in entries if pg is not None)
    page_rate = round(paged / len(entries), 4) if entries else 0.0
    score = round((basic_completeness + page_rate) / 2, 4)
    return {"basic_completeness": basic_completeness, "basic_filled": filled,
            "assets": len(obj.get("assets", [])), "extras": len(obj.get("extras", [])),
            "entries_with_value": len(entries), "page_rate": page_rate, "score": score}


def spotcheck_a(pred_dir, pdf_dir, sample_size=30, seed=42):
    """Optional: verify a deterministic random sample of numeric fields against the
    original PDF page text (requires pymupdf and fetched originals)."""
    import random
    import fitz  # noqa: import-outside-top-level
    manifest = {m["id"]: m for m in load(os.path.join(ROOT, "data", "manifest.json"))}
    fields = []
    for did in BATCH_IDS:
        p = os.path.join(pred_dir, did + "__A.json")
        if os.path.exists(p):
            for f in load(p).get("fields", []):
                f = dict(f)
                f["_doc"] = did
                fields.append(f)
    random.seed(seed)
    numf = [f for f in fields if isinstance(f.get("value"), (int, float)) and f.get("page")]
    sample = random.sample(numf, min(sample_size, len(numf)))
    docs, match, mismatch, examples = {}, 0, 0, []
    for f in sample:
        did = f["_doc"]
        if did not in docs:
            rel = manifest[did].get("original_file")
            docs[did] = fitz.open(os.path.join(pdf_dir, rel))
        pg = f["page"]
        if pg > docs[did].page_count:
            mismatch += 1
            continue
        txt = re.sub(r"[\s,，]", "", docs[did][pg - 1].get_text("text"))
        v = f["value"]
        ok = str(v) in txt or str(round(v, 2)) in txt or str(round(v, 1)) in txt or (v == int(v) and str(int(v)) in txt)
        match += ok
        mismatch += (not ok)
        if not ok and len(examples) < 5:
            examples.append({"doc": did, "name": f["name"], "value": v, "page": pg})
    return {"sample": len(sample), "match": match, "mismatch": mismatch,
            "pass_rate": round(match / len(sample), 4) if sample else 0.0,
            "mismatch_examples": examples}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pred-dir", required=True)
    ap.add_argument("--out")
    ap.add_argument("--pdf-dir", default=None, help="original PDFs dir for optional spotcheck")
    ap.add_argument("--spotcheck", action="store_true")
    args = ap.parse_args()
    res = {"REITs_A": score_a(args.pred_dir), "REITs_B": score_b(args.pred_dir)}
    if args.spotcheck:
        if not args.pdf_dir:
            ap.error("--spotcheck requires --pdf-dir")
        res["REITs_A"]["page_spotcheck"] = spotcheck_a(args.pred_dir, args.pdf_dir)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(res, f, ensure_ascii=False, indent=2)
    print(json.dumps(res, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
