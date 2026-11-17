# 无双大师 · AutoFinPDF-Bench

**金融PDF结构化解析基准评测**，考察大模型对金融PDF的解析、理解和归纳总结能力。

> 把本仓库地址发给任何新的大模型（或其操作者/智能体），它按 [AGENTS.md](AGENTS.md) 执行即可参评：
> 跑冻结任务 → 确定性脚本评分 → 提 PR → 分数永久留在 [LEADERBOARD.md](LEADERBOARD.md)。

## 排行榜（v1.0.1）

📊 **公开展示页**（可排序 / 搜索 / 逐模型详情雷达图）：**https://chuiziyao.github.io/AutoFinPDF-Bench/**

| # | 提交者 | 模型 | Overall | T1 短篇 | T2 三表 | T3 一致 | T4 深解 | T5 图表 | T6 法律 | T7 扫描 | REITs语义 | 超长文档 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | @chuiziyao | Qwen4-Max-Preview | **0.7761** | 1.0 | 0.9939 | 1.0 | 定性 | 0.9542 | 0.524 | 0.287 | 0.8402 | 0.8334 |
| 2 | @chuiziyao | HY4 (Tencent Hunyuan) | **0.7387** | 1.0 | 0.9591 | 1.0 | 定性 | 0.9412 | 0.451 | 0.24 | 0.7465 | 0.8334 |

> 所有列 **0–1 分，满分 1，越高越好**；Overall = 7 个计数档等权均值（T3 单列展示、T4 定性不入均值）。
> 白话版：T1 短公告抽数 · T2 长报告抽三张财务报表 · T3 美股港股数字对不对得上 · T4 读懂事件与上下游（定性）·
> T5 看图读数 · T6 读法律意见书 · T7 认扫描件 · REITs语义 基金报告运营指标 · 超长文档 1511 页招募书。
> F1/召回等指标口径详见 [docs/SCORING.md](docs/SCORING.md)；完整表格（核验状态/日期）见 [LEADERBOARD.md](LEADERBOARD.md)。

## 为什么做这个基准

金融文档智能的真实难点不在"能不能读 PDF"，而在：**超长文档**（626 页招股书 / 1511 页 REITs 招募书）、
**跨市场跨准则**（A/港/美三市场，US GAAP vs 中国 CAS）、**复杂表格重建**（三表全量、REITs 运营指标）、
**视觉必需**（无数据标签图表、矢量乱序图表）、**无文本层扫描件 OCR**、**密集法律语言解读**，以及**幻觉控制**。
现有公开基准对这些场景覆盖不足。本基准全部语料来自**官方一手披露**（SEC EDGAR / 港交所披露易 / 巨潮资讯 / 交易所 REITs 平台），
逐字段人工核验 GT，确定性脚本评分，难度梯度实测有区分度（标准档 0.99 → 法律 0.52 → 扫描 0.29）。

## 任务设计（47 个真实案例）

| 档 | 任务 | 能力维度 | 实例 | 轮数 |
|---|---|---|---|---|
| T1 | 短篇公告交付/销量抽取 | 精确数值抽取 | 14 | 2 |
| T2 | 长报告三表全量抽取 | 长文档·表格·跨准则 | 4 | 2 |
| T3 | 跨市场一致性（由 T2 派生） | 跨文档归一 | 1 对 | — |
| T4 | 深度理解（事件/上下游/风险） | 语义·关系抽取（定性） | 2 | 2 |
| T5 | 图表视觉抽取 | 多模态·布局理解 | 2 | 2 |
| T6 | 法律意见书解读 | 密集法律推理·要素区分 | 3 | 2 |
| T7 | 扫描件 OCR 结构化 | 无文本层视觉 OCR | 5 | 2 |
| REITs-A | 定期报告运营/财务字段 | 复杂表格·稀缺指标（WALT/续租率/剩余收费年限） | 16 | 1 |
| REITs-B | 1511 页招募书核心信息 | 超长文档·分块·页码定位 | 1 | 1 |

语料覆盖：理想/赛力斯（主）+ 比亚迪/蔚来/小鹏/零跑（扩展），37 只基础设施 REITs 中的 16+1 份官方报告。

## 快速开始

### 我要给一个新模型评测（操作者/智能体）

读 [AGENTS.md](AGENTS.md) —— 机器可执行协议，两条路径：

```bash
# 路径 A：被测模型有 OpenAI 兼容 API
export OPENAI_API_KEY=sk-...
python scripts/run_eval.py --base-url https://api.provider.com/v1 --model <model-id> \
    --out results/<slug>/outputs
python scripts/score_all.py --slug <slug> --name "My Model" --provider "Vendor" --submitter <你的GitHub用户名>
python scripts/validate_submission.py results/<slug>
python scripts/make_leaderboard.py
# 提 PR，分数上榜

# 路径 B：被测模型只有聊天界面
python scripts/make_taskpack.py --out taskpack   # 生成逐字任务包
# 把每个任务发给被测模型，原始响应存 outputs/raw/，然后：
python scripts/parse_outputs.py --out results/<slug>/outputs
# 之后同路径 A 的评分/校验/PR 步骤
```

全部脚本 **Python 3.10+ 标准库**，零依赖、跨平台。官方输入（抽取文本 + 页面图像）已含在仓库内，无需下载原文即可参评。

### 我要复核/研究

```bash
python scripts/selftest.py                  # 评分器自检 + 参考成绩回归
python scripts/freeze_benchmark.py --check  # 基准哈希完整性
python scripts/fetch_corpus.py              # 可选：从官方源下载原文 PDF/HTM 并校验 sha256
python scripts/score_reits.py --pred-dir results/qwen4-max-preview/outputs/reits \
    --pdf-dir corpus_original --spotcheck   # 可选：REITs 页码抽查（需 pymupdf）
```

原文 PDF/HTM（43 份，205MB）也归档在 [v1.0.0 Release](https://github.com/chuiziyao/AutoFinPDF-Bench/releases/tag/v1.0.0)
（两个 zip，解压到 `corpus_original/` 即用）；仓库本体保持轻量，**不下载原文也能完整参评**。

## 固定评测办法（v1.0 冻结）

- **同一任务、同一输入、同一逐字 prompt、同一 JSON Schema、同一评分脚本**；每实例 2 轮取均值（REITs 1 轮）。
- 受控科目词表 + 单位归一（yuan/thousand/million/billion/wan/yi/percent/count）+ 币种，保证跨模型可匹配。
- 财务容差 rel 0.5% / 百分比 ±0.1pp / 交付量精确；T5 图表单独容差 rel 3% / ±1.5pp。
- 公平口径：T2 目标期间白名单、成本类按绝对值（消除 GAAP/CAS 列报差异）、可选衍生比率不计幻觉。
- GT 逐字段附页码与原文 snippet，人工核验锁定（[docs/gt/](docs/gt/)）。
- `benchmark.json` 用 sha256 锁定全部 prompt/输入/GT/评分器；任何改动必须升版本。
- 详见 [docs/METHODOLOGY.md](docs/METHODOLOGY.md) 与 [docs/SCORING.md](docs/SCORING.md)。

## 诚信与核验

GT 公开（支持自助评分），配套防作弊机制：被测会话隔离规则、原始输出 + usage 日志/截图证据、
CI 用提交输出**重算分数**、维护者抽查升级 `verified`。详见 [docs/INTEGRITY.md](docs/INTEGRITY.md)。

## 仓库结构

```
AGENTS.md            参评协议（发给新模型就看这个）
benchmark.json       冻结基准定义 + 全量 sha256
prompts/             逐字冻结的 system/task prompt
schema/              输出 JSON Schema + 记录表模板
data/                官方输入：抽取文本(带页标记) + 页面图像 + manifest(来源URL/哈希)
groundtruth/         人工核验 GT（标准档 + 硬档）
scripts/             runner / 评分器 / 校验器 / 排行榜 / 下载器（纯标准库）
results/<model>/     每个模型：outputs(原始+解析) + metrics + summary.json + evidence
LEADERBOARD.md       自动生成的排行榜
docs/                方法学 / 评分口径 / 诚信政策 / 数据说明 / GT 核验记录
```

## 合规与许可

- 语料全部为公开官方披露文件，保留来源 URL + sha256；见 [docs/DATA.md](docs/DATA.md)。
- 代码与评分器：Apache-2.0（[LICENSE](LICENSE)）。GT 标注：CC BY 4.0。
- 原始披露文件版权归披露主体（上市公司/基金管理人/监管机构），本仓库仅以研究目的引用其公开内容。

## 引用

```
AutoFinPDF-Bench v1.0: A Frozen Benchmark for Financial Disclosure PDF Structuring.
https://github.com/<OWNER>/AutoFinPDF-Bench
```

## English Summary

AutoFinPDF-Bench (无双大师 / Wushuang Master) is an open, frozen benchmark for structured extraction from financial disclosure
PDFs (China NEV equities across A/HK/US markets + public infrastructure REITs). 47 instances span
short-notice numeric extraction, full three-statement extraction from 600+ page reports, cross-market
consistency, chart vision, legal-opinion interpretation, textless-scan OCR, and a 1511-page prospectus.
Any new model can enter by following [AGENTS.md](AGENTS.md): run the frozen tasks via an OpenAI-compatible
API (or a verbatim chat task pack), score with deterministic stdlib-only scripts, and open a PR — its
score stays on the leaderboard permanently. Ground truth is public with an evidence + CI re-scoring
integrity model ([docs/INTEGRITY.md](docs/INTEGRITY.md)).
