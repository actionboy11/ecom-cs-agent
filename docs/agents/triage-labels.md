# Triage Labels

The skills speak in terms of five canonical triage roles. This file maps those roles to the actual label strings used in this repo's issue tracker.

| Role | Label in our tracker | Meaning |
| --------------------- | -------------------- | ---------------------------------------- |
| `needs-triage`        | `needs-triage`       | 需要维护者评估 |
| `needs-info`          | `needs-info`         | 等待提问者补充信息 |
| `ready-for-agent`     | `ready-for-agent`    | 已充分规格化，可交给 agent 直接实现 |
| `ready-for-human`     | `ready-for-human`    | 需要人工实现或决策 |
| `wontfix`             | `wontfix`            | 明确不做 |

When a skill mentions a role (e.g. "apply the AFK-ready triage label"), use the corresponding label string from this table.

## 标签的创建

```bash
gh label create needs-triage    --color FBCA04 --description "需要维护者评估"
gh label create needs-info      --color D4C5F9 --description "等待补充信息"
gh label create ready-for-agent --color 0E8A16 --description "已规格化，可交给 agent"
gh label create ready-for-human --color 1D76DB --description "需要人工实现"
gh label create wontfix         --color B60205 --description "不做"
```
