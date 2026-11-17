# 评分口径（v1.0 冻结）

所有指标由确定性脚本计算。脚本：`score.py`（T1/T2/T5）、`score_hard.py`（T6/T7）、
`score_t3.py`（T3 派生）、`score_reits.py`（REITs）、`score_all.py`（编排 → summary.json）。

## 0. 白话速览（给非技术读者）

**所有分数 0–1，满分 1，越高越好。** 各档考什么：

| 显示名 | 考什么（一句话） | 1 分意味着 |
|---|---|---|
| Overall | 7 个计数档的平均 | 各档全满分的理想模型 |
| T1 短篇 | 从短公告里抽月度交付/销量数字 | 每个数字都抽对 |
| T2 三表 | 从几百页年报里抽三张财务报表 | 科目、期间、数值全对 |
| T3 一致 | 同一家公司美股/港股披露的数字对不对得上 | 6 项指标全部一致 |
| T4 深解 | 读懂事件、上下游关系、风险（定性，不打分） | 人工审阅判优 |
| T5 图表 | 看图片里的图表/方框图读数 | 图里每个数都读对 |
| T6 法律 | 读法律意见书，分清假设/限定/风险 | 法律要素齐全不混淆 |
| T7 扫描 | 认没有文字层的扫描件（纯 OCR） | 关键事实全部认对 |
| REITs语义 | 基金定期报告的运营/财务字段（验证式） | 格式全规范+页码全覆盖+稀缺指标全覆盖 |
| 超长文档 | 1511 页招募书的核心信息（验证式） | 核心信息齐全且都带对页码 |

**术语一句话**：
- **F1**：抽得准（precision）和抽得全（recall）的调和平均——既不能漏也不能编。
- **召回（recall）**：标准答案里的字段，你找出来多少比例。
- **精确匹配**：数值与原文完全一致（归一单位后）的比例。
- **幻觉率**：你输出的字段里，原文根本没有的比例（**越低越好**，不在排行榜主表展示）。
- **验证式指标（REITs）**：没有逐字段标准答案，改查"输出质量"——字段名规范、页码齐全、稀缺指标覆盖；
  所以 REITs 的 1 分 ≠ 数值全对，解读时注意（页码抽查可另跑 `--spotcheck`）。

> 显示名映射：REITs语义 = 内部键 REITs_A（任务A）；超长文档 = REITs_B（任务B）。
> v1.0.1 仅新增元数据（提交者）与展示层，**评分逻辑与 v1.0.0 完全一致**。

## 1. T1 / T2 / T5：字段级 P/R/F1

匹配键 = `(group, item, period, currency)`；deliveries 键 = `("delivery", model, month, "CNY")`。
数值先按单位归一到百万（yuan 1e-6 / thousand 1e-3 / million 1 / billion 1e3 / wan 0.01 / yi 100）。

| 指标 | 定义 |
|---|---|
| precision | TP / (TP+FP) |
| recall | TP / (TP+FN) |
| F1 | 2PR/(P+R) |
| exact_match_rate | 归一后完全相等的 GT 字段占比 |
| coverage | 非 missing 的 GT 字段占比 |
| hallucination_rate | 超出 GT 且非可选比率的预测字段 / 预测字段总数 |
| value_error_rate | 键匹配但值超容差的 GT 字段占比 |

**容差**：
- T1/T2：财务相对容差 **0.5%**；百分比 **±0.1pp**；count（交付量）**精确**（差<0.5）。
- T5（`--chart`）：相对 **3%**；百分比 **±1.5pp**（无数据标签读图固有误差，单独报告）。
- 成本类科目按**绝对值**匹配；0==0 视为相等。
- T2 仅统计目标期间白名单内的字段；可选衍生比率（gross_margin/operating_margin/net_margin/
  vehicle_margin/revenue_yoy/deliveries_total/cash_and_short_term_investments）超 GT 不计幻觉。

**聚合**：每实例 2 轮分别评分取均值 → 档内按实例平均（macro）→ 输出 aggregate。

## 2. T3：跨市场一致性（派生）

取 `li_us_20f_fy2025__T2__r1` 与 `li_hk_ar_fy2025__T2__r1`，对 FY2025 的
revenue/gross_profit/net_income/total_assets/cash_and_equivalents/deliveries_total
逐项单位归一后按 T1/T2 容差比较，`rate = 一致项 / 6`。

## 3. T4：定性档

输出 events/relationships/risks/notes 收集于 outputs，维护者审阅（页码可溯源性/关系准确性/判读质量），
**不产生数值分**，不参与 Overall。

## 4. T6：法律要素级匹配

要素文本 = `content || topic || term`；字符二元组 Jaccard 相似度，阈值 **0.3** 最佳重叠匹配。
- element_recall = GT 要素被覆盖比例；element_precision = 预测要素被 GT 覆盖比例；element_f1 = 调和平均。
- 类别：parties/approvals/assumptions/qualifications/key_clauses/risk_flags/definitions（仅 GT 非空类别参与平均）。
- conclusion_overlap = 总体结论的 Jaccard。
- **v1.0 已知限制**：parties（name/role）与 approvals（authority/matter）无 content/topic/term 字段，
  文本匹配恒为 0 —— 参考成绩即在此口径下产生，为保持可比性 v1.0 不修正；v1.1 候选改进。

## 5. T7：扫描事实匹配

key_facts：item 名 Jaccard ≥ **0.3** 且 value 匹配（数值：绝对差 ≤ max(0.5, 0.5%)；
字符串：千分位归一后相等或 Jaccard ≥ 0.8）。
- fact_recall = 命中 GT 事实 / GT 事实数；fact_precision = 命中 / 预测事实数。
- 另报 party_recall（名称 Jaccard ≥ 0.5）、date_match（≥0.8）、title_match（≥0.5）。

## 6. REITs：验证式指标（无逐字段 GT）

**REITs-A（16 份）**：
- name_compliance = 含「项目名-指标名」连字符的字段占比
- page_rate = 带页码字段占比
- priority_counts = 6 类稀缺指标关键词命中数（WALT/续租率/剩余收费年限/出租率/租金单价/收缴率，原始计数，与参考报告可比）
- priority_doc_coverage = 每类指标"至少命中 1 条的文档数 / 16"，再对 6 类取平均（归一化、防刷量）
- **score_A = mean(name_compliance, page_rate, priority_doc_coverage_avg)**
- 可选页码抽查（`--spotcheck`，需原文 PDF + pymupdf）：seed=42 抽 30 条数值字段，页文本含值（千分位归一）即通过。

**REITs-B（招募书）**：
- basic_completeness = 6 个 basic 键非 null 比例
- page_rate = 非 null 条目（basic/assets/extras）带 page_no 比例
- **score_B = mean(basic_completeness, page_rate)**

> 口径声明：REITs 分数衡量**输出质量与稀缺指标覆盖**，不是对 GT 的准确率；与 T1–T7 的 F1/召回并列展示，
> 解读时注意差异。这是 v1.0 的诚实折中（78 份 REITs 逐字段人工 GT 超出当前核验能力）。

## 7. Overall 与排行榜

```
Overall = mean(T1.f1, T2.f1, T5.f1, T6.element_f1, T7.fact_recall, REITs_A.score, REITs_B.score)
```
- 按**可用档**计算；缺任何档 → `partial=true`，榜上标 †。
- T3 单独列展示（派生指标，不入 Overall）；T4 定性不入榜。
- 并列时按 slug 字典序；缺 Overall 排最后。

## 8. 舍入与复算

- 比率保留 4 位小数（硬档 3 位）；CI 重算容差 1e-6。
- `validate_submission.py` 用提交的原始输出完整重算并与 summary.json 比对，不一致即拒绝。
