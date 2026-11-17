# -*- coding: utf-8 -*-
"""AutoFinPDF-Bench model-agnostic runner (OpenAI-compatible chat API, stdlib only).

Runs the frozen v1.0 benchmark against ANY model endpoint and writes outputs in the
exact layout the scorers expect:

  <out>/standard/<doc_id>__<task>__r<N>.json   (+ raw/<rid>.txt)
  <out>/hard/<doc_id>__<task>__r<N>.json
  <out>/reits/<doc_id>__A.json
  <out>/reits/prospectus__B.json               (120-page chunks merged)
  <out>/usage.jsonl                            (per-call evidence log)

Examples:
  set OPENAI_API_KEY=...
  python scripts/run_eval.py --base-url https://api.example.com/v1 \
      --model my-model --out results/my-model/outputs
  python scripts/run_eval.py ... --tracks standard --task T1 --limit 2   # smoke test
  python scripts/run_eval.py ... --dry-run                               # dump messages, no API

Vendor-specific parameters (e.g. enable_thinking) go through --extra-body JSON or
--thinking on|off (sends {"enable_thinking": bool}); use --thinking none to omit.
The API key is read from an environment variable and NEVER logged.
"""
import argparse
import base64
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)


def load(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def prompt_text(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as f:
        return f.read()


def extract_json(text):
    t = text.strip()
    t = re.sub(r"^```(?:json)?\s*", "", t)
    t = re.sub(r"\s*```$", "", t)
    try:
        return json.loads(t)
    except json.JSONDecodeError:
        a, b = t.find("{"), t.rfind("}")
        if a >= 0 and b > a:
            try:
                return json.loads(t[a:b + 1])
            except json.JSONDecodeError:
                pass
    return None


def call(base_url, key, model, messages, max_tokens, timeout, retries, extra_body, stream):
    body = {"model": model, "messages": messages, "max_tokens": max_tokens, "stream": stream}
    body.update(extra_body)
    payload = json.dumps(body).encode()
    t0 = time.time()
    for attempt in range(retries):
        req = urllib.request.Request(base_url.rstrip("/") + "/chat/completions", data=payload,
                                     headers={"Content-Type": "application/json",
                                              "Authorization": "Bearer " + key}, method="POST")
        text, reason_chars, usage = "", 0, None
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                if stream:
                    for raw in resp:
                        line = raw.decode("utf-8", "replace").strip()
                        if not line.startswith("data:"):
                            continue
                        p = line[5:].strip()
                        if p == "[DONE]":
                            break
                        try:
                            ch = json.loads(p)
                        except json.JSONDecodeError:
                            continue
                        if ch.get("usage"):
                            usage = ch["usage"]
                        for c in ch.get("choices", []):
                            d = c.get("delta") or {}
                            if d.get("reasoning_content"):
                                reason_chars += len(d["reasoning_content"])
                            if d.get("content"):
                                text += d["content"]
                else:
                    ch = json.loads(resp.read().decode("utf-8", "replace"))
                    usage = ch.get("usage")
                    for c in ch.get("choices", []):
                        m = c.get("message") or {}
                        if m.get("reasoning_content"):
                            reason_chars += len(m["reasoning_content"])
                        text += m.get("content") or ""
            return text, reason_chars, usage, round(time.time() - t0, 2)
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504) and attempt < retries - 1:
                time.sleep(min(60, 5 * (2 ** attempt)))
                continue
            raise


def image_content(rel):
    with open(os.path.join(ROOT, rel), "rb") as f:
        return {"type": "image_url",
                "image_url": {"url": "data:image/png;base64," + base64.b64encode(f.read()).decode()}}


def build_messages(inst):
    """Reproduce the v1.0 reference message construction exactly."""
    system = prompt_text(inst["system"])
    prompt = prompt_text(inst["prompt"])
    task, track = inst["task_id"], inst["track"]
    if track == "standard":
        if inst["input_mode"] == "image":
            content = [{"type": "text", "text": prompt}] + [image_content(p) for p in inst["inputs"]]
            user = {"role": "user", "content": content}
        else:
            body = prompt_text(inst["inputs"][0])
            user = {"role": "user", "content": prompt + "\n\n材料全文：\n" + body}
    elif track == "hard":
        if task == "T6":
            user = {"role": "user", "content": prompt + prompt_text(inst["inputs"][0])}
        else:
            content = [{"type": "text", "text": prompt}] + [image_content(p) for p in inst["inputs"]]
            user = {"role": "user", "content": content}
    elif track == "reits" and task == "A":
        user = {"role": "user", "content": prompt + prompt_text(inst["inputs"][0])}
    else:
        raise ValueError("task B is chunked; use build_chunk_messages")
    return [{"role": "system", "content": system}, user]


def split_pages(text):
    """Split extracted text on ===== PAGE n ===== markers -> {page_no: page_text}."""
    parts = re.split(r"\n\n===== PAGE (\d+) =====\n\n", text)
    pages = {}
    for i in range(1, len(parts) - 1, 2):
        pages[int(parts[i])] = parts[i + 1]
    return pages


def build_chunk_messages(inst, chunk_pages):
    system = prompt_text(inst["system"])
    template = prompt_text(inst["prompt"])
    nums = sorted(chunk_pages)
    start, end = nums[0], nums[-1]
    text = "".join("\n\n===== PAGE %d =====\n\n" % i + chunk_pages[i] for i in nums)
    user = {"role": "user", "content": (template % (start, end)) + text}
    return [{"role": "system", "content": system}, user]


def merge_prospectus(chunks, total_pages):
    """Frozen v1.0 merge rule: first non-null basic wins; assets dedup by name; extras concat."""
    basic_keys = {"raise_size": "亿元", "fund_term": "年", "offering_price": "元",
                  "total_shares": "亿份", "original_owner": None, "strategic_ratio": None}
    basic = {}
    for k, unit in basic_keys.items():
        val = None
        for c in chunks:
            v = c.get("basic", {}).get(k)
            if isinstance(v, dict) and v.get("value") is not None:
                val = v
                break
        basic[k] = val or {"value": None, "unit": unit, "page_no": None}
    assets, seen = [], set()
    for c in chunks:
        for a in c.get("assets", []):
            nm = (a.get("name") or {}).get("value")
            if nm and nm not in seen:
                seen.add(nm)
                assets.append(a)
    extras = []
    for c in chunks:
        extras.extend(c.get("extras", []))
    return {"source_file": "prospectus_1511p.txt", "total_pages": total_pages,
            "chunks": len(chunks), "basic": basic, "assets": assets, "extras": extras}


def out_path(out, inst, run_idx):
    track, task, did = inst["track"], inst["task_id"], inst["doc_id"]
    if track == "reits":
        name = "prospectus__B.json" if task == "B" else did + "__A.json"
        return os.path.join(out, "reits", name)
    return os.path.join(out, track, "%s__%s__r%d.json" % (did, task, run_idx))


def run_one(ctx, inst, run_idx):
    args = ctx["args"]
    rid = "%s__%s__r%d" % (inst["doc_id"], inst["task_id"], run_idx)
    if inst["track"] == "reits":
        rid = inst["doc_id"] + "__" + inst["task_id"]
    dest = out_path(args.out, inst, run_idx)
    rec = {"id": rid, "doc_id": inst["doc_id"], "task_id": inst["task_id"],
           "track": inst["track"], "run": run_idx, "model": args.model}
    if args.skip_existing and os.path.exists(dest):
        rec["status"] = "cached"
        return rec
    msgs = build_messages(inst)
    if args.dry_run:
        d = os.path.join(args.out, "dry_run")
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, rid + ".messages.json"), "w", encoding="utf-8") as f:
            json.dump(msgs, f, ensure_ascii=False, indent=2)
        rec["status"] = "dry-run"
        return rec
    try:
        text, rc, usage, lat = call(args.base_url, ctx["key"], args.model, msgs,
                                    args.max_tokens, args.timeout, args.retries,
                                    ctx["extra_body"], not args.no_stream)
        rec.update({"latency_s": lat, "reasoning_chars": rc, "usage": usage})
        os.makedirs(os.path.join(args.out, "raw"), exist_ok=True)
        with open(os.path.join(args.out, "raw", rid + ".txt"), "w", encoding="utf-8") as f:
            f.write(text)
        parsed = extract_json(text)
        rec["json_valid"] = parsed is not None
        if parsed is not None:
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            with open(dest, "w", encoding="utf-8") as f:
                json.dump(parsed, f, ensure_ascii=False, indent=2)
        rec["status"] = "ok" if parsed is not None else "no-json"
    except urllib.error.HTTPError as e:
        rec["error"] = "HTTP %s: %s" % (e.code, e.read().decode("utf-8", "replace")[:300])
        rec["status"] = "error"
    except Exception as e:  # noqa: BLE001
        rec["error"] = "%s: %s" % (type(e).__name__, str(e)[:200])
        rec["status"] = "error"
    return rec


def run_prospectus(ctx, inst):
    args = ctx["args"]
    dest = out_path(args.out, inst, 1)
    rec = {"id": "prospectus_xiamen_huoju__B", "doc_id": inst["doc_id"],
           "task_id": "B", "track": "reits", "run": 1, "model": args.model}
    if args.skip_existing and os.path.exists(dest):
        rec["status"] = "cached"
        return rec
    pages = split_pages(prompt_text(inst["inputs"][0]))
    nums = sorted(pages)
    chunk_size = ctx["chunk_pages"]
    chunks = []
    chunk_dir = os.path.join(args.out, "reits", "prospectus_chunks")
    for s in range(0, len(nums), chunk_size):
        cn = nums[s:s + chunk_size]
        cid = "chunk_%04d_%04d" % (cn[0], cn[-1])
        cp = os.path.join(chunk_dir, cid + ".json")
        if args.skip_existing and os.path.exists(cp):
            chunks.append(load(cp))
            continue
        msgs = build_chunk_messages(inst, {n: pages[n] for n in cn})
        if args.dry_run:
            d = os.path.join(args.out, "dry_run")
            os.makedirs(d, exist_ok=True)
            with open(os.path.join(d, cid + ".messages.json"), "w", encoding="utf-8") as f:
                json.dump(msgs, f, ensure_ascii=False, indent=2)
            continue
        try:
            text, rc, usage, lat = call(args.base_url, ctx["key"], args.model, msgs,
                                        args.max_tokens, args.timeout, args.retries,
                                        ctx["extra_body"], not args.no_stream)
            obj = extract_json(text) or {}
            obj["_pages"] = [cn[0], cn[-1]]
            obj["_usage"] = usage
            obj["_latency_s"] = lat
        except Exception as e:  # noqa: BLE001
            obj = {"_pages": [cn[0], cn[-1]], "_error": str(e)[:150]}
        os.makedirs(chunk_dir, exist_ok=True)
        with open(cp, "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False, indent=2)
        chunks.append(obj)
    if args.dry_run:
        rec["status"] = "dry-run"
        return rec
    merged = merge_prospectus(chunks, max(nums))
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    with open(dest, "w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False, indent=2)
    rec["status"] = "ok"
    rec["chunks"] = len(chunks)
    return rec


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base-url", help="OpenAI-compatible API base, e.g. https://api.openai.com/v1")
    ap.add_argument("--model", help="model id sent to the API")
    ap.add_argument("--api-key-env", default="OPENAI_API_KEY", help="env var holding the API key")
    ap.add_argument("--out", required=True, help="outputs root, e.g. results/my-model/outputs")
    ap.add_argument("--tracks", default="standard,hard,reits")
    ap.add_argument("--task", default="", help="filter task_id (T1/T2/T4/T5/T6/T7/A/B)")
    ap.add_argument("--doc", default="", help="filter doc_id substring")
    ap.add_argument("--runs", type=int, default=0, help="override runs for standard/hard (default: frozen 2)")
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--thinking", choices=["on", "off", "none"], default="none",
                    help="on/off sends {enable_thinking: bool}; none omits the parameter")
    ap.add_argument("--extra-body", default="{}", help="extra JSON merged into request body")
    ap.add_argument("--max-tokens", type=int, default=65536)
    ap.add_argument("--timeout", type=int, default=900)
    ap.add_argument("--retries", type=int, default=6)
    ap.add_argument("--no-stream", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--skip-existing", action="store_true")
    ap.add_argument("--dry-run", action="store_true", help="write messages to <out>/dry_run, no API calls")
    args = ap.parse_args()

    bench = load(os.path.join(ROOT, "benchmark.json"))
    tracks = set(args.tracks.split(","))
    instances = [i for i in bench["instances"] if i["track"] in tracks]
    if args.task:
        instances = [i for i in instances if i["task_id"] == args.task]
    if args.doc:
        instances = [i for i in instances if args.doc in i["doc_id"]]
    if args.limit:
        instances = instances[:args.limit]
    if not instances:
        raise SystemExit("no instances match the filters")

    key = os.environ.get(args.api_key_env, "")
    if not args.dry_run:
        if not args.base_url or not args.model:
            raise SystemExit("--base-url and --model are required (or use --dry-run)")
        if not key:
            raise SystemExit("API key env var %s is empty" % args.api_key_env)
    extra_body = json.loads(args.extra_body)
    if args.thinking != "none":
        extra_body["enable_thinking"] = args.thinking == "on"
    ctx = {"args": args, "key": key, "extra_body": extra_body,
           "chunk_pages": bench.get("reits_B_chunk_pages", 120)}

    os.makedirs(args.out, exist_ok=True)
    jobs = []
    for inst in instances:
        if inst["track"] == "reits":
            jobs.append((inst, 1))
        else:
            runs = args.runs or inst["runs"]
            jobs.extend((inst, r) for r in range(1, runs + 1))
    print("benchmark %s | %d instances | %d calls | model=%s" %
          (bench["version"], len(instances), len(jobs), args.model or "(dry-run)"), flush=True)

    done = 0
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = []
        for inst, r in jobs:
            if inst["track"] == "reits" and inst["task_id"] == "B":
                futs.append(ex.submit(run_prospectus, ctx, inst))
            else:
                futs.append(ex.submit(run_one, ctx, inst, r))
        for fu in futs:
            rec = fu.result()
            done += 1
            with open(os.path.join(args.out, "usage.jsonl"), "a", encoding="utf-8") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            print("[%d/%d] %s %s" % (done, len(jobs), rec["id"], rec.get("status", "?")), flush=True)
    print("DONE ->", args.out)


if __name__ == "__main__":
    main()
