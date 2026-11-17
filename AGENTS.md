# AGENTS.md — 大模型/智能体参评协议

> 你（或你的操作者）把本仓库地址发给一个新的大模型，它按本文件执行即可参加评测，并在排行榜留下分数。
> 本文件是**机器可执行协议**：命令逐条照抄即可，全部脚本仅依赖 Python 3.10+ 标准库，无需 pip install。

## 0. 这是什么

AutoFinPDF-Bench v1.0：金融披露 PDF 结构化解析基准。47 个冻结实例：

| 轨道 | 任务 | 实例数 | 每实例轮数 | 输入 |
|---|---|---|---|---|
| standard | T1 月度交付/销量抽取 | 14 | 2 | 文本 |
| standard | T2 长报告三表全量抽取 | 4 | 2 | 文本（最长 626 页招股书） |
| standard | T4 深度理解（事件/上下游/风险） | 2 | 2 | 文本（定性档，不计数值分） |
| standard | T5 图表视觉抽取 | 2 | 2 | 页面图像 |
| hard | T6 法律意见书解读 | 3 | 2 | 文本 |
| hard | T7 扫描件 OCR 结构化 | 5 | 2 | 扫描图像（无文本层） |
| reits | A 定期报告运营/财务字段 | 16 | 1 | 文本 |
| reits | B 1511 页招募书核心信息 | 1 | 1（13 个 120 页分块） | 文本 |

T3 跨市场一致性为**派生指标**（由 T2 输出计算，无需额外调用）。

## 1. 诚信规则（先读，违反=成绩作废）

1. **被测模型只能看到任务输入**：`prompts/` 里对应的 system+prompt 与 `data/` 里的材料。
   **严禁**把 `groundtruth/`、`scripts/score*.py`、`results/` 或本仓库其他内容喂给被测模型。
   操作者（运行仓库的 agent）与被测模型是两个角色；即使你是同一个模型家族，被测会话也必须隔离。
2. **冻结文件不可改**：`prompts/`、`data/`、`groundtruth/`、`schema/`、`benchmark.json`、`scripts/` 中的评分与协议脚本
   （score*.py / run_eval.py / make_taskpack.py / parse_outputs.py）。
   它们的 sha256 锁在 `benchmark.json` 里，CI 会校验。发现错误请提 issue，不要私改。
3. **禁止编造输出**：找不到填 null/uncertain。原始响应必须真实来自被测模型。
4. **summary.json 必须由脚本生成**，不得手改分数。CI 会用你的原始输出重算并比对。
5. 环境偏差（截断、思考模式不可控、输入方式不同）如实写入 recording/notes。

## 2. 准备

```bash
git clone <本仓库地址> && cd AutoFinPDF-Bench
python scripts/freeze_benchmark.py --check   # 确认基准完整（应输出 integrity OK）
python scripts/selftest.py                   # 评分器自检（应 ALL CHECKS PASSED）
```

给结果目录起名：`results/<slug>/`，slug 用模型名小写连字符，如 `results/my-model-v1/`。

## 3. 路径 A：被测模型有 OpenAI 兼容 API（推荐）

```bash
# Windows PowerShell: $env:OPENAI_API_KEY="sk-..."
export OPENAI_API_KEY=sk-...
python scripts/run_eval.py \
  --base-url https://api.your-provider.com/v1 \
  --model <被测模型的API-id> \
  --api-key-env OPENAI_API_KEY \
  --out results/<slug>/outputs \
  --workers 3
```

- 先冒烟测试：加 `--tracks standard --task T1 --limit 2`，确认输出 JSON 正常再跑全量。
- 厂商私有参数：`--thinking on|off`（发送 `enable_thinking`）或 `--extra-body '{"temperature":0}'`。
  参考运行条件：标准档/硬档思考 on，REITs 思考 off；温度用服务端默认。**无论用什么条件，如实记录**。
- 长文需要大上下文窗口（T2 最长输入为理想 20-F 约 103 万字符；REITs-B 招募书约 137 万字符，已按 120 页分块）。窗口不足会被截断 → 在 notes 声明，该实例按实际输出评分。
- 断点续跑：`--skip-existing`。只跑部分轨道：`--tracks standard,hard`（缺档会标 partial†）。
- 每次调用的延迟/token 用量自动记录到 `outputs/usage.jsonl`（这就是证据，不要删）。
- 原始响应文本在 `outputs/raw/`，解析后的 JSON 在 `outputs/{standard,hard,reits}/`。

## 4. 路径 B：被测模型只有聊天界面/智能体产品（手动模式）

```bash
python scripts/make_taskpack.py --out taskpack
```

1. 逐个打开 `taskpack/<rid>.md`：SYSTEM 段逐字作系统提示，USER 段逐字作用户消息（图像任务按清单附图），
   发给**被测模型**。每个任务独立会话；r1/r2 也要独立会话。
2. 把原始响应全文存到 `results/<slug>/outputs/raw/<rid>.txt`（不要手改内容）。
3. 解析 + 合并招募书分块：
   ```bash
   python scripts/parse_outputs.py --out results/<slug>/outputs
   ```
4. 填 `results/<slug>/evidence/recording.csv`（模板 `schema/recording_template.csv`）：
   工具、输入模式、思考模式、温度、起止时间、偏差说明。控制不了的参数写 unknown。
5. 保留工具界面/用量截图到 `results/<slug>/evidence/screenshots/`（核验用）。

## 5. 评分 + 自检 + 排行榜

```bash
python scripts/score_all.py --slug <slug> --name "模型显示名" \
  --version "<API-id或版本>" --provider "厂商" --notes "执行条件与偏差说明"
python scripts/validate_submission.py results/<slug>     # 必须 [OK]
python scripts/make_leaderboard.py                       # 更新 LEADERBOARD.md
```

`score_all.py` 生成 `results/<slug>/summary.json`（分数）与 `metrics/`（逐文档明细）。
`validate_submission.py` 会重算你的全部输出并与 summary 比对——不一致就修到一致。

## 6. 留下分数（提交 PR）

```bash
git checkout -b result/<slug>
git add results/<slug> LEADERBOARD.md leaderboard.json
git commit -m "result: <模型名> (benchmark v1.0.0)"
git push origin result/<slug>
```

在 GitHub 开 PR（模板会自动带出清单）。CI 自动执行：基准完整性 → 评分器自检 → 重算你的提交 → 排行榜一致性。
CI 绿 + 维护者核验证据后合并，你的模型就永久留在排行榜上了。

**核验等级**：合并时为 `self-reported`（CI 已通过）；维护者抽查证据（usage 日志/截图/抽样复跑）后可升级为
`verified`。见 [docs/INTEGRITY.md](docs/INTEGRITY.md)。

## 7. 常见问题

- **没有 GPU/不能联网下载原文？** 不需要。官方输入（抽取文本+页面图像）已全在 `data/` 里。
  原文 PDF 只用于可选复核：`python scripts/fetch_corpus.py`。
- **上下文不够长？** 如实声明截断，按实际输出评分；不要分块喂 T2（分块策略只允许用于 REITs-B，且必须用冻结的 120 页协议）。
- **模型拒绝输出 JSON？** 原样保存响应，解析器会尝试提取；提取失败该实例记 0 分并保留 raw 证据。
- **想改 prompt/容差/题目？** 那是 benchmark 变更，走版本升级流程（CONTRIBUTING.md），不能混在成绩 PR 里。
- **REITs 没有逐字段 GT，怎么算分？** 验证式指标（字段名规范率/页码覆盖率/稀缺指标文档覆盖率），公式冻结在 docs/SCORING.md。

人类可读文档：[README.md](README.md) · [方法学](docs/METHODOLOGY.md) · [评分口径](docs/SCORING.md) · [诚信政策](docs/INTEGRITY.md) · [数据说明](docs/DATA.md)
