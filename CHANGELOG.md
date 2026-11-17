# Changelog

## v1.0.1（2026-11-17）

**评分逻辑零变化**；参考成绩不变（Qwen4-Max-Preview 0.7761 / HY4 0.7387，selftest 回归通过）。

- 排行榜补回 **T3 跨市场一致性** 与 **T4 深度理解（定性）** 列。
- 新增 **提交者（GitHub 用户名）** 列：`score_all.py --submitter` 必填，summary schema 升至 1.1；
  排行榜与展示页同时显示提交者 + 模型名。
- 表头白话化：去掉 F1/召回等术语后缀；**REITs-A → REITs语义，REITs-B → 超长文档**；
  表下附白话说明，术语详解见 docs/SCORING.md 第 0 节。
- 新增**公开展示页**（GitHub Pages，`docs/index.html`）：排序/搜索/逐模型详情雷达图/档位说明/参评指引；
  数据由 `make_leaderboard.py` 生成 `docs/leaderboard-data.js`，CI 校验一致性。
- 校验器新增 submitter 必填检查。

## v1.0.0（2026-11-17）

- 首发：47 个冻结实例（T1–T7 + REITs A/B），prompt/输入/GT/评分器 sha256 锁定。
- 模型无关 runner（OpenAI 兼容 API）+ 手动聊天任务包；纯标准库。
- 确定性评分 + CI 重算校验 + 证据政策；自动生成 LEADERBOARD.md。
- 参考成绩：Qwen4-Max-Preview（API 直连）与 HY4（WorkBuddy 手动横评），全部公开数字逐项复现。
- 原文 PDF/HTM 43 份归档于 v1.0.0 Release 附件（205MB，逐文件哈希校验）。
