## 评测成绩提交 / Result Submission

**模型**：<显示名 + API-id/版本>
**厂商**：
**基准版本**：v1.0.0
**执行路径**：API 模式 / 手动聊天模式
**执行条件**：思考模式、温度、输入模式、并发、起止日期
**偏差声明**：截断/工具限制/输入方式差异（无则写"无"）

### 自检清单（本地必须全绿）

- [ ] `python scripts/freeze_benchmark.py --check` 通过
- [ ] `python scripts/selftest.py` 通过
- [ ] `python scripts/validate_submission.py results/<slug>` 输出 [OK]
- [ ] `python scripts/make_leaderboard.py` 已更新排行榜
- [ ] 证据齐全：API 模式 outputs/usage.jsonl + raw/；手动模式 evidence/recording.csv + 截图
- [ ] 被测会话隔离：被测模型未接触 groundtruth/评分脚本/仓库其他内容（AGENTS.md 第 1 节）
- [ ] PR 只含 results/<slug>/ + LEADERBOARD.md + leaderboard.json，未改冻结文件
- [ ] summary.json 由 score_all.py 生成，未手改

### 分数摘要（从 summary.json 复制）

| Overall | T1 | T2 | T5 | T3 | T6 | T7 | REITs-A | REITs-B |
|---|---|---|---|---|---|---|---|---|
| | | | | | | | | |

### 备注

<!-- 失败案例、观察、想对维护者说的话 -->
