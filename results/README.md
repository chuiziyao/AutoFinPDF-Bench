# results/ — 每个模型的成绩目录

布局（由脚本生成，勿手改 summary）：

```
results/<slug>/
  outputs/
    standard/<doc_id>__<task>__r<N>.json   # 解析后的模型输出（44 个）
    hard/<doc_id>__<task>__r<N>.json       # 16 个
    reits/<doc_id>__A.json                 # 16 个
    reits/prospectus__B.json               # 招募书合并结果
    reits/prospectus_chunks/               # B 的 13 个分块原始结果
    raw/<rid>.txt                          # 模型原始响应全文（证据）
    usage.jsonl                            # API 模式逐调用日志（证据）
  metrics/                                 # score_all 生成的逐文档明细
    T1.json T2.json T5.json T3.json hard.json reits.json
  summary.json                             # 分数（CI 重算比对的对象）
  evidence/                                # 手动模式：recording.csv + 截图 + 评测文档
```

当前收录：

| slug | 模型 | 来源 |
|---|---|---|
| qwen4-max-preview | Qwen4-Max-Preview | 参考运行（API 直连，2026-11-15） |
| hy4 | HY4 (Tencent Hunyuan) | 基线横评（WorkBuddy 智能体手动，2026-11-16） |

新模型参评：见 [../AGENTS.md](../AGENTS.md)。
