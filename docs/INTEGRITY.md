# 诚信与核验政策

## 1. 信任模型（诚实声明）

GT 是**公开**的——这是"发仓库地址就能自助参评"的前提。公开 GT 意味着理论上存在作弊空间
（把答案喂给被测模型）。本基准用**流程隔离 + 证据 + 重算 + 抽查**四层机制把风险压到可接受，
并如实区分核验等级。没有任何公开 GT 基准能完全杜绝作弊；我们选择透明而非假装安全。

## 2. 四层机制

### 层 1：会话隔离（流程规则）
- 被测模型只能接收 `prompts/` 对应 system+prompt 与 `data/` 材料。
- 操作者 agent 与被测模型是**两个角色**：操作者读仓库、跑脚本；被测会话只看到任务输入。
- 即使操作者与被测是同一模型家族，被测会话也不得携带仓库上下文（AGENTS.md 第 1 节）。
- runner 的消息构造保证只发送任务输入（可 `--dry-run` 审计每条消息）。

### 层 2：证据（提交必备）
- API 模式：`outputs/usage.jsonl`（每次调用的模型 id/延迟/token 用量/错误）+ `outputs/raw/` 原始响应。
- 手动模式：`evidence/recording.csv`（逐次运行记录）+ 工具界面/用量截图。
- 证据缺失 → `validate_submission.py` 直接 FAIL，CI 不绿。

### 层 3：CI 重算（自动）
- 每个 PR：基准哈希完整性 → 评分器自检 → **用提交的原始输出重算全部分数** → 与 summary.json 比对 → 排行榜一致性。
- 手改 summary、删改输出、用过期评分器，都会被拒绝。
- 伪造输出能骗过重算，但骗不过层 4 与证据审查（零延迟、无用量、GT 逐字复现、页码全对但值来源不明等异常）。

### 层 4：维护者核验（人工抽查）
- 合并门槛：CI 绿 + 证据齐全。合并时等级 = `self-reported`。
- 升级 `verified` 的抽查项（至少）：
  1. usage 日志合理性（延迟分布、token 量级与任务规模匹配、模型 id 一致）；
  2. 随机抽 2–3 个实例要求操作者提供会话截图/录屏，或维护者用同端点复跑比对；
  3. 高分异常审查（如 T7 事实召回 >0.8、T2 满分且零延迟）触发强制复核；
  4. 手动模式核对 recording.csv 与截图时间线。
- 发现作弊：成绩移除、slug 拉黑、PR 记录留痕。

## 3. 核验等级

| 等级 | 含义 | 榜上标记 |
|---|---|---|
| self-reported | CI 重算通过，证据齐全，未经人工抽查 | self-reported |
| verified | 维护者完成层 4 抽查 | ✅ verified |

## 4. 偏差与截断

- 输入模式偏离（pdf_native 替代 text）、思考模式不可控、工具截断长文 → 必须写入 recording/notes。
- 截断实例按实际输出评分（不豁免），榜上 notes 展示，供读者自行折扣。
- 未声明的偏差一经查实按作弊处理。

## 5. 给维护者的合并清单

- [ ] CI 全绿（integrity / selftest / validate --all / leaderboard --check）
- [ ] `results/<slug>/` 结构完整：outputs + metrics + summary.json + evidence
- [ ] summary 的 benchmark_version/scorer_hash 与当前一致
- [ ] notes 如实描述执行条件与偏差
- [ ] 无冻结文件改动（PR diff 只含 results/ 与排行榜生成文件）
- [ ] 高分异常已抽查（或明确标注 self-reported 留待后续核验）
