# Pilot 执行器

## 文件

| 文件 | 内容 |
|---|---|
| `single-turn.jsonl` | 单轮用例 |
| `confirmation-scripts.jsonl` | 确认脚本；支持 2 步或「澄清 → 选单 → 确认/取消」 |
| `run_pilot.py` | 执行器 |
| `results.json` / `results.md` | 最近一次结果 |

## 确认脚本的 `steps`

```json
{
  "id": "pilot-confirm-05",
  "steps": [
    {
      "user": "我买的那双跑鞋还没发货，帮我退款",
      "expect": {"type": "clarify", "tools": ["find_my_orders"]}
    },
    {
      "user": "选择订单 CS2024230",
      "expect": {
        "type": "confirm",
        "order_no": "CS2024230",
        "action": "refund",
        "tools": ["query_order", "create_refund"]
      }
    },
    {
      "user": "确认退款",
      "expect": {"type": "handled", "order_no": "CS2024230", "action": "refund"}
    }
  ]
}
```

规则：

- `steps` 按顺序执行
- `clarify`：不能写、不能 interrupt，回复非空
- `confirm`：必须出现 `write_approval`，action/order 匹配
- `handled`：走上一步的 `/confirm`，最后核对售后单类型
- `answer`：走上一步的 `/confirm`（取消），最后核对没有售后单
- 没有 `steps` 的旧用例按 `input + turns[0]` 跑 2 步

## 数据重置

确认脚本会创建售后单。执行器在每条用例前后用本机 `mysql` 客户端删除目标订单的售后记录：

```
mysql -h 127.0.0.1 -P 3308 -ucsagent -pcsagent cs_agent
```

不再通过 Python 调 `docker`（Windows 下 Python 子进程访问 Docker 命名管道会被拒绝）。

## 当前状态

- 26/26
- b-07 已修：`urge_logistics` 已注册
