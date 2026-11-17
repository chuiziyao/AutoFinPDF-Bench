# -*- coding: utf-8 -*-
"""(Re)generate benchmark.json — the frozen v1.0 benchmark definition.

Every prompt, input file, ground-truth file and scorer is sha256-locked here.
Any change to prompts/inputs/GT/scoring MUST bump `version` and re-run this
script; leaderboard entries record the version they were produced under.

Usage: python scripts/freeze_benchmark.py [--check]
  --check: verify current files still match the recorded hashes (CI integrity gate)
"""
import argparse
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

VERSION = "1.0.1"

# ---- frozen instance list (doc_id, task, track, stem, input_mode, pages, runs) ----
STANDARD = [
    ("li_us_delivery_2026-03", "T1", "delivery_2026-03", "text", []),
    ("li_us_delivery_2026-04", "T1", "delivery_2026-04", "text", []),
    ("li_us_delivery_2026-05", "T1", "delivery_2026-05", "text", []),
    ("li_us_delivery_2026-06", "T1", "delivery_2026-06", "text", []),
    ("li_us_delivery_2026-07", "T1", "delivery_2026-07", "text", []),
    ("li_us_delivery_2026-08", "T1", "delivery_2026-08", "text", []),
    ("li_us_delivery_2026-09", "T1", "delivery_2026-09", "text", []),
    ("li_us_delivery_2026-10", "T1", "delivery_2026-10", "text", []),
    ("seres_a_prod_sales_2026-05", "T1", "production_sales_flash_2026-05", "text", []),
    ("seres_a_prod_sales_2026-06", "T1", "production_sales_flash_2026-06", "text", []),
    ("seres_a_prod_sales_2026-07", "T1", "production_sales_flash_2026-07", "text", []),
    ("seres_a_prod_sales_2026-08", "T1", "production_sales_flash_2026-08", "text", []),
    ("seres_a_prod_sales_2026-09", "T1", "production_sales_flash_2026-09", "text", []),
    ("seres_a_prod_sales_2026-10", "T1", "production_sales_flash_2026-10", "text", []),
    ("li_us_20f_fy2025", "T2", "us_20f_fy2025", "text", []),
    ("li_hk_ar_fy2025", "T2", "hk_annual_report_fy2025_zh", "text", []),
    ("seres_a_annual_2025", "T2", "a_share_annual_report_2025", "text", []),
    ("li_hk_listing_doc_2021", "T2", "hk_listing_doc_2021_global_offering_zh", "text", []),
    ("seres_a_annual_2025", "T4", "a_share_annual_report_2025", "text", []),
    ("li_hk_ar_fy2025", "T4", "hk_annual_report_fy2025_zh", "text", []),
    ("li_hk_listing_doc_2021", "T5", "hk_listing_doc_2021_global_offering_zh", "image", [198, 206, 208]),
    ("seres_a_annual_2025", "T5", "a_share_annual_report_2025", "image", [11, 75]),
]
HARD = [
    ("legal_seres_asset_purchase", "T6", None, "text", []),
    ("legal_byd_private_placement", "T6", None, "text", []),
    ("legal_changan_private_placement", "T6", None, "text", []),
    ("legal_seres_main_scanned", "T7", None, "image", [1, 2, 3, 4, 54, 55]),
    ("legal_seres_asset_scanned", "T7", None, "image", [1, 2, 3, 4, 194, 195]),
    ("scanned_byd_csrc_ipo_approval_2011", "T7", None, "image", [1, 2]),
    ("scanned_seres_holder_reply_seal_2016", "T7", None, "image", [1]),
    ("scanned_seres_legal_opinion_sign_2016", "T7", None, "image", [1, 2, 3, 4]),
]
REITS_BATCH = ["508021_2024FY", "180102_2025FY", "180202_2025FY", "508007_2025FY",
               "180301_2025FY", "180501_2025FY", "180601_2025FY", "180605_2025FY",
               "180607_2025FY", "180701_2025FY", "508028_2025FY", "508056_2025FY",
               "508060_2025FY", "508068_2025FY", "508087_2025FY", "508096_2026Q2"]
SCORER_FILES = ["score.py", "score_hard.py", "score_t3.py", "score_reits.py", "score_all.py",
                "run_eval.py", "make_taskpack.py", "parse_outputs.py"]


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def rel_hash(rel):
    p = os.path.join(ROOT, rel)
    if not os.path.exists(p):
        raise SystemExit("missing frozen file: " + rel)
    return sha256(p)


def build():
    instances = []

    def add(doc_id, task, track, stem, mode, pages, runs, prompt, system, inputs, gt):
        instances.append({
            "doc_id": doc_id, "task_id": task, "track": track, "input_mode": mode,
            "pages": pages, "runs": runs, "prompt": prompt, "system": system,
            "inputs": inputs, "groundtruth": gt,
        })

    for doc_id, task, stem, mode, pages in STANDARD:
        prompt = "prompts/T5_%s.txt" % doc_id if task == "T5" else "prompts/%s.txt" % task
        if mode == "text":
            inputs = ["data/text/%s.txt" % stem]
        else:
            inputs = ["data/pages/%s/p%04d.png" % (stem, p) for p in pages]
        gt = "groundtruth/%s__%s.json" % (doc_id, task) if task in ("T1", "T2", "T5") else None
        add(doc_id, task, "standard", stem, mode, pages, 2, prompt, "prompts/system_standard.txt", inputs, gt)
    for doc_id, task, _stem, mode, pages in HARD:
        if mode == "text":
            inputs = ["data/text/%s.txt" % doc_id]
        else:
            inputs = ["data/pages/%s/p%04d.png" % (doc_id, p) for p in pages]
        add(doc_id, task, "hard", doc_id, mode, pages, 2,
            "prompts/%s.txt" % task, "prompts/system_%s.txt" % task, inputs,
            "groundtruth/hard/%s__%s.json" % (doc_id, task))
    for did in REITS_BATCH:
        add(did, "A", "reits", did, "text", [], 1,
            "prompts/reits_A.txt", "prompts/system_reits_A.txt",
            ["data/reits/%s.txt" % did], None)
    add("prospectus_xiamen_huoju", "B", "reits", "prospectus_1511p", "text", [], 1,
        "prompts/reits_B_chunk.txt", "prompts/system_reits_B.txt",
        ["data/reits/prospectus_1511p.txt"], None)

    hashes = {"prompts": {}, "inputs": {}, "groundtruth": {}, "scorers": {}}
    for fn in sorted(os.listdir(os.path.join(ROOT, "prompts"))):
        if fn.endswith(".txt"):
            hashes["prompts"]["prompts/" + fn] = rel_hash("prompts/" + fn)
    seen = set()
    for inst in instances:
        for rel in inst["inputs"]:
            if rel not in seen:
                seen.add(rel)
                hashes["inputs"][rel] = rel_hash(rel)
        if inst["groundtruth"] and inst["groundtruth"] not in seen:
            seen.add(inst["groundtruth"])
            hashes["groundtruth"][inst["groundtruth"]] = rel_hash(inst["groundtruth"])
    for rel in ("groundtruth/target_periods.json",):
        hashes["groundtruth"][rel] = rel_hash(rel)
    for fn in SCORER_FILES:
        hashes["scorers"]["scripts/" + fn] = rel_hash("scripts/" + fn)

    return {
        "name": "AutoFinPDF-Bench",
        "version": VERSION,
        "frozen_at": "2026-11-17",
        "description": "金融披露 PDF 结构化解析基准：新能源汽车股（A/港/美三市场）+ 公募 REITs。"
                       "标准档 T1–T5（T3 派生、T4 定性）+ 硬档 T6/T7 + REITs 档 A/B。",
        "runs_per_track": {"standard": 2, "hard": 2, "reits": 1},
        "reits_B_chunk_pages": 120,
        "tolerances": {
            "financial_rel": 0.005, "percent_pp": 0.1, "count_abs": 0.5,
            "chart_rel": 0.03, "chart_percent_pp": 1.5,
            "cost_items_abs": ["cost_of_revenue", "operating_expenses", "capex"],
            "t6_element_jaccard_threshold": 0.3,
            "t7_item_jaccard_threshold": 0.3, "t7_value_rel": 0.005, "t7_value_abs_floor": 0.5,
        },
        "formulas": {
            "overall": "mean(T1.f1, T2.f1, T5.f1, T6.element_f1, T7.fact_recall, REITs_A.score, REITs_B.score) over available tiers; missing tier => partial",
            "REITs_A.score": "mean(name_compliance, page_rate, priority_doc_coverage_avg)",
            "REITs_B.score": "mean(basic_completeness, page_rate)",
            "T3": "fraction of 6 controlled items whose normalized FY2025 values agree between li_us_20f_fy2025:T2 and li_hk_ar_fy2025:T2 (r1)",
        },
        "instances": instances,
        "derived": [{"task_id": "T3", "from": ["li_us_20f_fy2025:T2", "li_hk_ar_fy2025:T2"],
                     "metrics": ["revenue", "gross_profit", "net_income", "total_assets",
                                 "cash_and_equivalents", "deliveries_total"]}],
        "hashes": hashes,
    }


def check(bench):
    bad = []
    for group in ("prompts", "inputs", "groundtruth", "scorers"):
        for rel, h in bench["hashes"][group].items():
            p = os.path.join(ROOT, rel)
            if not os.path.exists(p) or sha256(p) != h:
                bad.append(rel)
    return bad


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    path = os.path.join(ROOT, "benchmark.json")
    if args.check:
        with open(path, encoding="utf-8") as f:
            bench = json.load(f)
        bad = check(bench)
        if bad:
            print("HASH MISMATCH (benchmark integrity violated):")
            for b in bad:
                print("  " + b)
            sys.exit(1)
        print("benchmark.json integrity OK (%d instances, version %s)" %
              (len(bench["instances"]), bench["version"]))
        return
    bench = build()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(bench, f, ensure_ascii=False, indent=2)
        f.write("\n")
    n = len(bench["instances"])
    nh = sum(len(v) for v in bench["hashes"].values())
    print("benchmark.json frozen: version=%s instances=%d hashes=%d" % (VERSION, n, nh))


if __name__ == "__main__":
    main()
