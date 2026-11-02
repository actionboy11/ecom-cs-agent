# 项目约定（AGENTS.md）

> 这是所有 agent 的入口说明。业务与设计文档：`README.md`、`docs/SPEC.md`、`docs/PROJECT-REPORT.md`。

## 开始前读这些

- `GLOSSARY.md`：领域术语（**必须**用这里的词，别用 `_Avoid_` 里的近义词）
- `docs/SPEC.md`：设计冻结版，功能边界以它为准
- `docs/adr/`：已定决策，动手前先扫一眼相关条目

## Agent skills

### Issue tracker

Issues and specs live as GitHub issues in `actionboy11/ecom-cs-agent`; use the `gh` CLI for all operations. See `docs/agents/issue-tracker.md`.

### Triage labels

The five canonical triage roles map 1:1 to their label strings (`needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`). See `docs/agents/triage-labels.md`.

### Domain docs

Single-context repo: `GLOSSARY.md` at the root, ADRs in `docs/adr/`. See `docs/agents/domain.md`.
