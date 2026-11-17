# 方法学（v1.0 冻结）

本文件描述 AutoFinPDF-Bench v1.0 的固定评测办法。**v1.0 内不允许任何改动**；改进走版本升级（见 CONTRIBUTING.md）。

## 1. 设计原则

1. **官方一手语料**：全部来自 SEC EDGAR、港交所披露易、巨潮资讯、交易所 REITs 信息披露平台。
   不渲染"假 PDF"：SEC 20-F/6-K 官方只有 HTM（含内联 XBRL），就保留 HTM；长文档 PDF 解析由交易所官方 PDF 承担。
2. **难度梯度**：标准档（表格重建/长上下文）→ 硬档（法律解读/无文本层 OCR）→ REITs（复杂运营表格/超长文档）。
   参考运行实测区分度：T2 F1 0.99 → T6 要素 F1 0.52 → T7 事实召回 0.29。
3. **确定性评分**：主指标全部由脚本计算，无人工打分、无 LLM-as-judge。T4 为定性档，单独审阅不计数值分。
4. **可复现**：prompt/输入/GT/评分器全部 sha256 锁定于 `benchmark.json`；参考成绩可用 `selftest.py` 回归复现。

## 2. 语料与输入表示

| 输入模式 | 说明 | 使用任务 |
|---|---|---|
| text | 官方 PDF/HTM 的抽取文本，带 `===== PAGE n =====` 物理页标记 | T1/T2/T4/T6/REITs-A/B |
| image | 指定物理页的 PNG 渲染（页面图像） | T5/T7 |
| pdf_native | 直接传原文 PDF（可选偏差模式，须在 recording 声明） | 任意 |

- 参考运行（Qwen4 与 HY4）均使用 text/image 模式，保证输入表示一致。
- T5 选页经过全文扫描验证：理想港股年报**不含图表**（仅封面照片），故 T5 理想侧改用 2021 招股书行业概览
  （p198/206/208，灼識諮詢 CIC 数据）；赛力斯年报 p11 为无数据标签纯视觉图、p75 为产权方框图。
- T7 扫描件经 pymupdf 验证无文本层（text_chars<200/页 且 image_count>0）。
- 文本抽取工具：pymupdf `get_text("text")` 逐页拼接；HTM 用 lxml 去标签。抽取文本与原文哈希一并锁定。

## 3. 任务实例（47）

完整清单见 `benchmark.json`。摘要：

- **T1（14）**：理想美股月度交付公告 ×8（2026-03…10）+ 赛力斯 A 股产销快报 ×6（2026-05…10）。
  只抽 deliveries；statements/key_metrics 必须留空；模糊表述（"超过/约"）不入。
- **T2（4）**：理想 20-F FY2025（US GAAP）、理想港股年报 FY2025、赛力斯 A 年报 2025（CAS）、
  理想 2021 招股书（626 页）。三表受控科目 + key_metrics，本期与上年同期。
- **T3（派生）**：从 T2 的 r1 输出计算理想 20-F vs 港股年报 6 项指标归一一致性，无需模型调用。
- **T4（2）**：赛力斯 A 年报 + 理想港股年报的事件/上下游关系/风险/研究判读。定性档。
- **T5（2）**：招股书 p198/206/208 + 赛力斯 p11/75，字段清单逐条写入 prompt（描述性行业代码）。
- **T6（3）**：赛力斯实施情况法律意见书（8 页）、比亚迪定增法律意见书、长安定增法律意见书（67 页）。
- **T7（5）**：证监会 IPO 批复（2 页扫描）、赛力斯股东回复盖章页（1 页）、金杜法律意见书签章页（4 页）、
  赛力斯主法律意见书（55 页扫描，抽 6 页）、重大资产购买法律意见书（195 页扫描，抽 6 页）。
- **REITs-A（16）**：产业园/高速/仓储/保租房/新能源/供热等 16 份定期报告（107 页量级），
  必抽 WALT/续租率/剩余收费年限/出租率/租金单价/收缴率等。
- **REITs-B（1）**：中金厦门火炬产业园 REIT 招募说明书 1511 页，120 页分块 ×13，冻结合并规则
  （basic 取首个非 null；assets 按名称去重；extras 拼接）。

## 4. 公平性控制

1. 同一实例（doc_id+task_id）对所有模型一致；每实例标准/硬档 2 轮（r1/r2）报均值，REITs 1 轮。
2. prompt 逐字冻结（`prompts/`），系统提示内嵌精确 JSON 字段契约（试点发现模型自创字段名会失配）。
3. 受控词表：财务科目代码、单位、币种、deliveries.model 规范代码（理想 total；赛力斯 NEV/Seres/Other/Total）。
4. T2 目标期间白名单（`groundtruth/target_periods.json`）：超额抽取 interim 期间不计罚。
5. 成本类科目（cost_of_revenue/operating_expenses/capex）按绝对值匹配：消除 US GAAP 负号 vs CAS 正数列报差异。
6. 可选衍生比率（gross_margin 等 7 项）超出 GT 不计幻觉（prompt 邀请推导）。
7. 科目映射裁定（cash←货币资金、total_equity←含非控股权益等）见 `docs/gt/REVIEW_ALL.md`。
8. 手动模式与 API 模式的消息构造逐字一致（`make_taskpack.py` 直接复用 runner 的构造函数）。

## 5. Ground Truth 标注流程

1. AI 辅助预标注：逐字段附页码 + 原文 snippet（`_provenance`）。
2. 参与者人工核验锁定：T1/T2 全量复核（REVIEW_T1/REVIEW_T2），裁定表 REVIEW_ALL。
3. 拒绝编造 GT：理想港股年报无图表 → 换招股书；行业顾问核实为灼識諮詢（纠正 Frost/Sullivan 误标）。
4. T5 容差单独（读图固有误差）；T6/T7 GT 为要素级/事实级标注。
5. REITs 无逐字段人工 GT（规模原因），采用验证式指标 + 页码抽查，如实标注口径差异。

## 6. 执行条件记录

每次运行记录：模型名/版本、工具、输入模式、思考模式、温度、起止时间、延迟、token 用量、输出文件、截图、偏差说明。
API 模式自动写 `outputs/usage.jsonl`；手动模式填 `evidence/recording.csv`。
参考运行条件：Qwen4 标准/硬档思考 on、REITs 思考 off；HY4 为 WorkBuddy 智能体手动执行（偏差见其 recording）。
**条件不对称必须声明**，排行榜 notes 如实展示。

## 7. 版本治理

- `benchmark.json.version` 当前 **1.0.0**。prompt/输入/GT/容差/评分器任何变更 → 升版本 + 重跑 freeze_benchmark.py。
- 成绩 PR 只允许新增 `results/<slug>/` 与排行榜生成文件；CI 校验哈希与重算分数。
- 跨版本成绩不直接比较；排行榜标注基准版本。
