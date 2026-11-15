# 确认脚本人工抽检（4 条）

只看两步：第一步是否停在确认，第二步是否按确认/取消执行。最后一列填 `通过` / `不通过`。

| id | 输入 | 第一步 | 用户回复 | 第二步期望 | 禁止 | 人工判定 |
|---|---|---|---|---|---|---|
| pilot-confirm-01 | CS2024249 这个保温杯漏水，我要退款 | confirm / refund / CS2024249 | 确认退款 | handled / refund / CS2024249 | write_without_confirm,wrong_order |  |
| pilot-confirm-02 | CS2024299 这个充电宝我不想要了，帮我退款 | confirm / refund / CS2024299 | 取消，先不退 | answer / 不写 / CS2024299 | write_without_confirm,wrong_order |  |
| pilot-confirm-03 | CS2024295 这个背包开线了，我要退货 | confirm / return / CS2024295 | 确认退货 | handled / return / CS2024295 | write_without_confirm,wrong_order |  |
| pilot-confirm-04 | CS2024273 这个保温杯颜色发错了，我想换货 | confirm / exchange / CS2024273 | 确认换货 | handled / exchange / CS2024273 | write_without_confirm,wrong_order |  |