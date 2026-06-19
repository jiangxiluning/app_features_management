# 版本发布日志

本目录记录每次发布的版本说明与升级指南。每个版本一个文档，文件名为版本号。

| 版本 | 日期 | 说明 |
|------|------|------|
| [0.9.0](0.9.0.md) | 2026-06-19 | 方案 M+：JWT、COW 审核、revision、SSE、schema 2.0.0 |

## 版本号规范

采用语义化版本 `MAJOR.MINOR.PATCH`：

- **MAJOR**：不兼容的 API 或 schema 变更
- **MINOR**：向后兼容的功能新增
- **PATCH**：向后兼容的问题修复

## 发布检查清单

- [ ] `run_plan_tests.py` 全部通过
- [ ] `test_sse_e2e.py` 通过
- [ ] 迁移脚本在 staging 演练（含 dry-run）
- [ ] 更新本目录发布日志
- [ ] 更新 `docs/README.md` 当前版本号
