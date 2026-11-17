# -*- coding: utf-8 -*-
"""Manual / chat-mode task pack generator.

For models WITHOUT an API endpoint (chat UI, agent products): generates one
markdown file per run containing the EXACT system prompt and user message the
API runner would send. Feed them to the model under test verbatim, save each raw
response to results/<slug>/outputs/raw/<rid>.txt, then run parse_outputs.py.

Usage:
  python scripts/make_taskpack.py --out taskpack [--tracks standard,hard,reits]
                                  [--task T1] [--doc li_us] [--limit N]
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import run_eval  # noqa: E402


def load(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--tracks", default="standard,hard,reits")
    ap.add_argument("--task", default="")
    ap.add_argument("--doc", default="")
    ap.add_argument("--limit", type=int, default=0)
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
    os.makedirs(args.out, exist_ok=True)
    n = 0
    index = []
    for inst in instances:
        if inst["track"] == "reits" and inst["task_id"] == "B":
            pages = run_eval.split_pages(run_eval.prompt_text(inst["inputs"][0]))
            nums = sorted(pages)
            cs = bench.get("reits_B_chunk_pages", 120)
            for s in range(0, len(nums), cs):
                cn = nums[s:s + cs]
                cid = "chunk_%04d_%04d" % (cn[0], cn[-1])
                msgs = run_eval.build_chunk_messages(inst, {p: pages[p] for p in cn})
                write_task(args.out, cid, inst, msgs,
                           "results/<slug>/outputs/raw/%s.txt" % cid,
                           "reits/prospectus_chunks/%s.json（全部 chunk 完成后由 parse_outputs.py 合并为 prospectus__B.json）" % cid)
                index.append(cid)
                n += 1
            continue
        runs = inst["runs"]
        for r in range(1, runs + 1):
            rid = "%s__%s__r%d" % (inst["doc_id"], inst["task_id"], r)
            if inst["track"] == "reits":
                rid = "%s__A" % inst["doc_id"]
            msgs = run_eval.build_messages(inst)
            write_task(args.out, rid, inst, msgs,
                       "results/<slug>/outputs/raw/%s.txt" % rid,
                       run_eval.out_path("results/<slug>/outputs", inst, r).replace("results/<slug>/outputs/", "").replace("\\", "/"))
            index.append(rid)
            n += 1
    with open(os.path.join(args.out, "00_README.md"), "w", encoding="utf-8") as f:
        f.write(TASKPACK_README % (n, "\n".join("- `%s`" % i for i in index)))
    print("taskpack: %d task files -> %s" % (n, args.out))


def write_task(out, rid, inst, msgs, raw_dest, final_dest):
    sysmsg = msgs[0]["content"]
    user = msgs[1]["content"]
    lines = ["# 任务 %s" % rid, "",
             "- 基准：AutoFinPDF-Bench %s（冻结 prompt，逐字使用，勿改写）" % "v1.0",
             "- 轨道：%s / 任务 %s" % (inst["track"], inst["task_id"]),
             "- 原始响应保存到：`%s`" % raw_dest,
             "- 解析后输出位置：`%s`" % final_dest, "",
             "## SYSTEM（逐字作为系统提示）", "", "```text", sysmsg, "```", "",
             "## USER（逐字作为用户消息）", ""]
    if isinstance(user, str):
        lines += ["```text", user, "```"]
    else:
        for part in user:
            if part["type"] == "text":
                lines += ["```text", part["text"], "```", ""]
        lines += ["附图（仓库相对路径，作为图像输入按顺序附上）："]
        lines += ["- `%s`" % rel for rel in inst["inputs"]]
    with open(os.path.join(out, rid + ".md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


TASKPACK_README = """# AutoFinPDF-Bench 手动评测任务包（%d 个任务）

适用：被测模型没有 API 端点（聊天界面/智能体产品）。

## 步骤
1. 逐个打开任务文件，把 SYSTEM 段逐字作为系统提示、USER 段逐字作为用户消息发给**被测模型**。
   - 图像任务：把标注的仓库图片一并上传（路径相对仓库根目录）。
   - 文本任务的 USER 段已含材料全文，直接整段发送，不要截断（长文需要大上下文窗口）。
   - 每个任务独立会话，避免跨任务污染；同一实例的 r1/r2 也要独立会话。
2. 把模型的**原始响应全文**保存到 `results/<slug>/outputs/raw/<rid>.txt`（rid 见任务文件名）。
   不要手工修改响应内容；模型若输出 markdown 包裹的 JSON，原样保存即可（解析器会处理）。
3. 全部完成后运行：
   ```
   python scripts/parse_outputs.py --out results/<slug>/outputs
   python scripts/score_all.py --slug <slug> --name "模型显示名" --version "版本/工具" --provider "厂商"
   python scripts/validate_submission.py results/<slug>
   python scripts/make_leaderboard.py
   ```
4. 填写 `results/<slug>/evidence/recording.csv`（模板 schema/recording_template.csv）：
   每次运行的工具、输入模式、思考模式、温度、起止时间、偏差说明。聊天工具无法控制的参数如实写 unknown。
5. 提交 PR（见 CONTRIBUTING.md）。

## 诚信要求
- 被测模型只能看到任务文件里的 SYSTEM+USER 内容。**不得**把 groundtruth/、评分脚本或本仓库其他内容喂给被测模型。
- 找不到填 null / uncertain，禁止编造；截断、工具差异等写入 deviation_note。

## 任务清单
%s
"""


if __name__ == "__main__":
    main()
