# -*- coding: utf-8 -*-
"""Self-tests for the frozen scorers + regression against the published v1.0 numbers.

Usage: python scripts/selftest.py
No third-party dependencies. CI runs this on every PR.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import score  # noqa: E402
import score_hard  # noqa: E402
import score_reits  # noqa: E402

PASS = 0


def check(name, cond):
    global PASS
    if not cond:
        print("FAIL:", name)
        sys.exit(1)
    PASS += 1
    print("ok:", name)


def gt_field(item, period, value, unit="million", currency="CNY", statement="income_statement"):
    return {"statement": statement, "item": item, "period": period,
            "value": value, "unit": unit, "currency": currency, "page": 1}


def test_score_pair():
    gt = {"statements": [gt_field("revenue", "FY2025", 100.0),
                         gt_field("cost_of_revenue", "FY2025", -60.0),
                         gt_field("net_income", "FY2025", 10.0)],
          "key_metrics": [gt_field("gross_margin", "FY2025", 40.0, "percent", statement="metric")],
          "deliveries": [{"month": "2026-03", "model": "total", "count": 41053, "page": 0}]}
    # exact prediction
    pred = json.loads(json.dumps(gt))
    r = score.score_pair(gt, pred)
    check("exact f1=1", r["f1"] == 1.0 and r["hallucination_rate"] == 0.0)
    # cost sign flip must still match (abs rule)
    pred["statements"][1]["value"] = 60.0
    r = score.score_pair(gt, pred)
    check("cost abs match", r["f1"] == 1.0)
    # 0.4% relative error within 0.5% tolerance
    pred = json.loads(json.dumps(gt))
    pred["statements"][0]["value"] = 100.4
    r = score.score_pair(gt, pred)
    check("rel tolerance 0.5%", r["tp"] == 5)
    # 1% relative error outside tolerance
    pred["statements"][0]["value"] = 101.0
    r = score.score_pair(gt, pred)
    check("rel error counted", r["value_error_rate"] == 0.2)
    # unit normalization: 100 million == 100000 thousand
    pred = json.loads(json.dumps(gt))
    pred["statements"][0]["value"] = 100000.0
    pred["statements"][0]["unit"] = "thousand"
    r = score.score_pair(gt, pred)
    check("unit canon", r["f1"] == 1.0)
    # optional derived ratio beyond GT is not hallucination
    pred = json.loads(json.dumps(gt))
    pred["key_metrics"].append(gt_field("operating_margin", "FY2025", 12.0, "percent", statement="metric"))
    r = score.score_pair(gt, pred)
    check("optional ratio bonus", r["hallucination_rate"] == 0.0)
    # invented item IS hallucination
    pred["key_metrics"].append(gt_field("made_up_item", "FY2025", 1.0, statement="metric"))
    r = score.score_pair(gt, pred)
    check("hallucination detected", r["hallucination_rate"] > 0)
    # deliveries exact count
    pred = json.loads(json.dumps(gt))
    pred["deliveries"][0]["count"] = 41054
    r = score.score_pair(gt, pred)
    check("count exactness", r["value_error_rate"] > 0)
    # percent tolerance ±0.1pp
    pred = json.loads(json.dumps(gt))
    pred["key_metrics"][0]["value"] = 40.05
    r = score.score_pair(gt, pred)
    check("percent tolerance", r["f1"] == 1.0)
    # chart tolerance ±1.5pp
    pred["key_metrics"][0]["value"] = 41.0
    r = score.score_pair(gt, pred, rel_tol=0.03, pct_tol=1.5)
    check("chart tolerance", r["f1"] == 1.0)


def test_hard():
    # NOTE: the frozen v1.0 T6 matcher reads element text from content/topic/term only.
    # Real GT parties(name/role) and approvals(authority/matter) therefore score 0 text
    # overlap by design; fixtures below use content-bearing categories accordingly.
    gt = {"parties": [],
          "assumptions": [{"content": "假设文件真实有效"}],
          "qualifications": [{"content": "本意见仅基于中国法律"}],
          "approvals": [], "key_clauses": [{"topic": "交割", "content": "交割先决条件"}],
          "risk_flags": [], "definitions": [{"term": "标的资产", "definition": "目标公司股权"}],
          "conclusion": {"overall": "本次交易合法合规"}}
    pred = json.loads(json.dumps(gt))
    r = score_hard.score_t6(gt, pred)
    check("t6 identical content-elements f1=1", r["element_f1"] == 1.0)
    gt_parties = {"parties": [{"name": "甲方公司", "role": "发行人"}]}
    r = score_hard.score_t6(gt_parties, json.loads(json.dumps(gt_parties)))
    check("t6 parties text-blind (frozen v1.0 quirk)", r["per_category"]["parties"]["recall"] == 0.0)
    pred["assumptions"] = []
    r = score_hard.score_t6(gt, pred)
    check("t6 missing element lowers recall", r["element_recall"] < 1.0)
    gt7 = {"meta": {"date": "2011年6月7日", "title": "核准批复"},
           "parties": [{"name": "比亚迪股份有限公司"}],
           "key_facts": [{"item": "发行股数", "value": 7900, "unit": "万股"}]}
    pred7 = {"meta": {"date": "2011年6月7日", "title": "核准批复"},
             "parties": [{"name": "比亚迪股份有限公司"}],
             "key_facts": [{"item": "发行股数", "value": "7,900", "unit": "万股"}]}
    r = score_hard.score_t7(gt7, pred7)
    check("t7 comma-normalized value match", r["fact_recall"] == 1.0)
    pred7["key_facts"][0]["value"] = 8000
    r = score_hard.score_t7(gt7, pred7)
    check("t7 wrong value rejected", r["fact_recall"] == 0.0)


def test_reits():
    check("batch ids frozen", len(score_reits.BATCH_IDS) == 16)
    obj = {"basic": {k: {"value": (1 if i < 4 else None), "page_no": (10 if i < 4 else None)}
                     for i, k in enumerate(score_reits.BASIC_KEYS)},
           "assets": [{"name": {"value": "项目A", "page_no": 5}}],
           "extras": [{"key": "k", "value": "v", "page_no": None}]}
    # exercise _entries_b + completeness logic inline
    filled = sum(1 for k in score_reits.BASIC_KEYS
                 if isinstance(obj["basic"].get(k), dict) and obj["basic"][k].get("value") is not None)
    check("basic completeness 4/6", filled == 4)
    entries = [(v, pg) for v, pg in score_reits._entries_b(obj) if v is not None]
    paged = sum(1 for v, pg in entries if pg is not None)
    check("B page rate", abs(paged / len(entries) - 5 / 6) < 1e-9)


def test_reference_regression():
    """The two imported reference runs MUST reproduce the published v1.0 numbers."""
    expected = {
        "qwen4-max-preview": {"T1": 1.0, "T2": 0.9939, "T5": 0.9542, "T3": 1.0,
                              "T6": 0.524, "T7": 0.287, "reits_fields": 751},
        "hy4": {"T1": 1.0, "T2": 0.9591, "T5": 0.9412, "T3": 1.0,
                "T6": 0.451, "T7": 0.24, "reits_fields": 303},
    }
    for slug, exp in expected.items():
        sp = os.path.join(ROOT, "results", slug, "summary.json")
        if not os.path.exists(sp):
            print("skip regression (no summary):", slug)
            continue
        s = json.load(open(sp, encoding="utf-8"))
        t = s["tracks"]
        check("%s T1" % slug, t["T1"]["f1"] == exp["T1"])
        check("%s T2" % slug, t["T2"]["f1"] == exp["T2"])
        check("%s T5" % slug, t["T5"]["f1"] == exp["T5"])
        check("%s T3" % slug, t["T3"]["rate"] == exp["T3"])
        check("%s T6" % slug, t["T6"]["element_f1"] == exp["T6"])
        check("%s T7" % slug, t["T7"]["fact_recall"] == exp["T7"])
        check("%s REITs fields" % slug, t["REITs_A"]["fields"] == exp["reits_fields"])


def test_benchmark_integrity():
    import freeze_benchmark
    bench = json.load(open(os.path.join(ROOT, "benchmark.json"), encoding="utf-8"))
    bad = freeze_benchmark.check(bench)
    check("benchmark hashes intact (%d files)" % sum(len(v) for v in bench["hashes"].values()), not bad)
    check("47 instances", len(bench["instances"]) == 47)


if __name__ == "__main__":
    test_score_pair()
    test_hard()
    test_reits()
    test_reference_regression()
    test_benchmark_integrity()
    print("\nALL %d CHECKS PASSED" % PASS)
