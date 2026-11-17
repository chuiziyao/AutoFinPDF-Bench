# GT 人工核验总清单（AutoFinPDF-Bench v1.0）

状态：全部预标注完成，`verified=false`，待参与者核验锁定。

## 核验分工与合规
AI 辅助预标注；**核验、判定与署名由参与者负责**（活动原创性 + 数据真实性要求）。核完把对应 GT 文件 `meta._provenance.verified=true`、填 verifier/日期（或告知 lead 代改）。来源 URL/sha256 见 corpus/manifest.json。

## T1 交付量（14 份 / 32 字段）— 建议全核
见 [REVIEW_T1.md](REVIEW_T1.md)。理想 8 月度 total + 赛力斯 6×4 分部。独立 QA 0 问题；Qwen4 试跑满分（F1=1.0）。
注意：赛力斯 Seres⊂NEV，Total=NEV+Other（不是 Seres+Other）。

## T2 长报告三表（4 份 / 182 字段）— 必核 headline + 随机抽 3 科目
见 [REVIEW_T2.md](REVIEW_T2.md)。headline：revenue / gross_profit / net_income / total_assets / cash_and_equivalents。
单位：20-F / 港股年报 / 招股书 = thousand CNY；赛力斯 A 年报 = yuan CNY。period：前三 FY2025+FY2024；招股书 FY2020+FY2019。
独立恒等式复核 0 问题；20-F↔港股年报 42 值逐一相同（T3 就绪）。

## T5 视觉图表（2 份 / 90 字段）— 全核（按图核系列值）
- 招股书 p198/206/208（灼識 CIC 行业图，矢量文本乱序→视觉必需）：li_hk_listing_doc_2021__T5.json，73 字段。
- 赛力斯 p11（无数据标签读图）/ p75（产权 raster）：seres_a_annual_2025__T5.json，17 字段。核验图：corpus/pages/a_share_annual_report_2025/p0011_fig1.png、p0011_fig2.png、p0075_ownership.png。
- T5 评分用图表容差（rel 3% / percent ±1.5pp），与 T1/T2 精确评分分开报告。

## 需你裁定的约定（lead 已默认采用，可 override）
1. **符号**：GT 保留原文符号；成本类（cost_of_revenue/operating_expenses/capex）评分按绝对值，消除 US GAAP（负）/CAS（正）列报差异；利润/现金流净额符号保留。
2. **赛力斯 deliveries_total** = 合计 516,860（非 NEV 头条 472,269），与 T1 快报 Total 同口径。
3. **cash_and_equivalents** = 资产负债表货币资金（赛力斯含约 389 亿受限保证金，已注明）。
4. **港股年报准则 = US_GAAP**（核数师报告确认，非 IFRS；与 20-F 一致）。
5. **T5 行业指标用描述性代码**（受控词表面向公司财务）；prompt 已列明确切字段保证匹配。

## 锁定后
lead 跑 Qwen4 全量（T2/T4/T5 + 思考 on/off 消融）+ T3 派生；你按 standard/ 跑 HY4；统一评分 → 数据库 → 报告。
