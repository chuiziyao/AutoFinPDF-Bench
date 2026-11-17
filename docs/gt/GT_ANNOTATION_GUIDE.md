# Ground Truth 标注与核验规范

ground truth（GT）是评分基准，其可信度决定整个评测的说服力。活动「数据真实性审核」要求数据可交叉验证，「原创性审核」要求体现参与者本人判断。因此 GT 采用 **AI 辅助预标注 + 参与者人工核验** 的双段流程，核验责任在参与者。

## 流程
1. **预标注（lead/AI 辅助）**：从原文逐字段抽取，每条附 `page`（PDF 1-based 物理页）与 `source_snippet`（原文片段），写入 `groundtruth/<doc_id>__<task>.json`，初始 `verified: false`。
2. **人工核验（参与者）**：对照原文核对数值/单位/币种/期间/页码。T1 建议全核（字段少）；T2 必核 headline（revenue/gross_profit/net_income/total_assets/cash_and_equivalents）并随机抽 3 个科目；T5 全核。
3. **锁定**：核验通过改 `verified: true`，记录核验人与日期；GT 目录打哈希锁定版本，评分以锁定版为准。

## 输出形态
- T1/T2/T5：符合 `schema/extraction_schema.json`（meta/statements/key_metrics/deliveries/events/uncertain）。
- T3：`{reconciliations:[{item,period,doc_a_value,doc_a_unit,doc_b_value,doc_b_unit,normalized_equal,reason}], meta}`。
- T4：`{events,relationships,risks,notes}`（relationships/risks 附 page）。
- 每条 GT 额外含 `_provenance`：{source_snippet, page, verified, verifier, verified_date}（评分脚本忽略下划线字段）。

## 词表与单位（与 prompts.md 一致）
item 必须用受控代码；unit ∈ {yuan,thousand,million,billion,wan,yi,percent,count,yuan_per_share}；currency ∈ {CNY,USD}；period 形如 FY2025/Q3 2025/2025-10。
**单位归一**：评分按 million 归一（亿=100、万=0.01、千元=0.001）；百分比容差±0.1；交付量精确匹配；财务值相对容差 0.5%（吸收四舍五入）。

## 页码规范
- PDF：1-based 物理页码（与 corpus/text 的 ===== PAGE n ===== 一致）。
- HTM（美股 SEC 文件）：无物理页，`page=0` 并在 _provenance 注明 section。**页码准确性仅对 PDF 文档评分**，HTM 不计页码分。

## 合规声明
预标注由 AI 辅助生成，**核验、判定与最终署名由参与者负责**。保留原文 snippet 与来源 URL/sha256（见 corpus/manifest.json），供活动交叉验证。禁止编造 GT；无法确定者不入 GT。
