# 开发工作流（留痕约定）

> 目标：让 GitHub 提交历史本身成为**工作证据**——面试官点开仓库，能看到持续 6 周的推进过程，而不是最后一天一次性提交。

---

## 1. 每日节奏

| 时点 | 动作 |
|---|---|
| 开工前（2 分钟） | 打开 `docs/daily/<今天>.md`，看昨天写的「明天做什么」 |
| 开发中 | 每完成一个可验证的小块就提交一次（不用等收工） |
| 收工前（5 分钟） | 更新当日记录三行 + `git commit` + `git push` |

**当日记录模板**（`docs/daily/YYYY-MM-DD.md`）：

```markdown
# YYYY-MM-DD

## 今天做了什么
- 

## 卡在哪 / 踩了什么坑
- 

## 明天做什么
- 
```

## 2. 提交规范

`<type>(<scope>): <描述>`

| type | 用途 |
|---|---|
| `feat` | 新功能 |
| `fix` | 修复 bug |
| `docs` | 文档 / SPEC / 每日记录 |
| `refactor` | 重构（不改行为） |
| `test` | 测试与评测用例 |
| `chore` | 构建、依赖、配置 |
| `ci` | CI / 流水线配置 |

示例：

```
feat(auth): 订单查询增加归属校验，越权返回 404
fix(eval): cases.jsonl 带 BOM 导致解析失败
docs(daily): 2026-11-02 记录代理劫持 localhost 的排查
```

**规则**：一次提交只做一件事；描述写「为什么/影响什么」，不写「修改了文件」。

## 3. 分支与标签

- 单人开发：**main 直推**，不建 feature 分支（避免自欺欺人的 PR 流程）
- 里程碑打 tag：`v0.1-skeleton`（已完成）、`v0.2-auth`、`v0.3-rag-mcp`、`v0.4-eval`、`v1.0-release`
- **CI**：`.github/workflows/ci.yml` 跑 Python（ruff + pytest）、Java（mvn test + MySQL service）、Compose 配置校验。早期「不做 GitHub Actions」的决策已被 P0-3 取代

## 4. 每周复盘（周日 10 分钟）

```markdown
## 第 N 周复盘
- 计划交付：…
- 实际交付：…
- 偏差原因：…
- 下周调整：…
- 投递数据：投 N 家 / 回复 N / 面试 N
```

追加到当周日期的 `docs/daily/` 文件末尾。

## 5. 禁止提交的内容

- `.env`、任何 API Key、数据库密码（已在 `.gitignore`）
- `data/mysql/`、`traces/`、`eval/reports/`、`target/`、`.venv/`
- 大文件（>5MB）与模型权重

## 6. 提交前自检（30 秒）

```bash
git status --short          # 有没有误加文件
git diff --cached --stat    # 这次改了哪些
uv run ruff check .         # lint 必须为 0
uv run pytest -q            # 本地测试是否绿
uv lock --check             # 锁文件是否与 pyproject 一致
```
