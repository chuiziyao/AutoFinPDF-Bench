# 贡献指南

## A. 提交评测成绩（最常见）

1. 按 [AGENTS.md](AGENTS.md) 完成评测，得到 `results/<slug>/`（outputs + metrics + summary.json + evidence）。
2. 本地自检必须全绿：
   ```bash
   python scripts/validate_submission.py results/<slug>
   python scripts/make_leaderboard.py
   python scripts/selftest.py
   ```
3. 开分支 `result/<slug>`，**只提交**：
   - `results/<slug>/`（全部输出、明细、summary、证据）
   - `LEADERBOARD.md` + `leaderboard.json`（脚本生成）
4. PR 标题：`result: <模型名> (benchmark v1.0.0)`；按模板填清单。
5. CI 绿 + 维护者核验后合并 → 分数永久留榜。

**成绩 PR 禁止**：修改 prompts/data/groundtruth/schema/benchmark.json/评分脚本；手改 summary.json；
删除他人 results；夹带无关文件。

## B. 报告数据/GT 错误

提 issue，附：doc_id、字段、原文页码截图、正确值与依据。维护者核实后**升版本**修正。
不要在成绩 PR 里顺手改 GT。

## C. 基准变更（升版本）

允许的方向：新增实例/轨道、修正 GT 错误、改进评分口径（如 T6 parties 匹配）、扩充语料。

流程：
1. 先提 issue 讨论（影响可比性，需要共识）。
2. PR 修改冻结文件 + `freeze_benchmark.py` 的 VERSION 与实例定义 → 重新生成 benchmark.json。
3. 更新 docs/METHODOLOGY.md、docs/SCORING.md 的变更说明。
4. **参考成绩处理**：旧版成绩保留并标注版本；新版参考运行由维护者组织重跑。
5. 排行榜按版本分区展示（v1.x 与 v2.x 不直接比较）。

## D. 代码贡献

- 脚本保持 **Python 3.10+ 标准库**（可选功能如页码抽查才允许 pymupdf，且必须 lazy import + 明确报错提示）。
- 评分逻辑改动 = 基准变更，走 C 流程；工具性改动（runner/CLI/文档）正常 PR。
- 新增脚本请附自测（selftest.py 扩展）。

## E. 行为准则

诚实第一：不编造输出、不隐瞒偏差、不刷榜。争议以证据与复跑为准。
