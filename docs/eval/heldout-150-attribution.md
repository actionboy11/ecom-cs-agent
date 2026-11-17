# Held-out 150 失败归因表

对象：第二次跑，99/150，51 条失败。

这是初步归因，仍需 judge/人工复核；不是最终判决。

## 汇总

| 归因 | 数量 | 处理 |
|---|---:|---|
| Agent 真错 | 13 | 改代码 |
| 题面歧义 | 15 | v1.1 改 clarify/多步 |
| 期望错误 | 11 | v1.1 改契约 |
| 规则未定 | 10 | 先定规则，再 judge |
| 工具期望过严 | 2 | v1.1 改允许工具集 |

## 明细

### Agent 真错（13）

| id | 类别 | 期望 | 实际 | 动作 |
|---|---|---|---|---|
| h150-a-s004 | order_lookup | {"type": "tool", "tools": ["find_my_orders"], "order_no | 抱歉，我这边暂时查不到您的历史订单记录，无法列出10月、11月的购买清单。建议您在App「我的订单」中按时间筛选查看，或 | 改代码 |
| h150-a-s021 | normal_return | {"type": "confirm", "order_no": "CS2024226", "action":  | 您最近签收的充电宝订单有 CS2024225（11-13 签收）、CS2024226（11-14 签收）、CS20242 | 改代码 |
| h150-a-s023 | normal_return | {"type": "confirm", "order_no": "CS2024312", "action":  | 已找到您的订单：**CS2024312 · 20寸登机行李箱（¥699）**，2026-11-07 签收，非定制商品。  | 改代码 |
| h150-a-s025 | normal_return | {"type": "confirm", "order_no": "CS2024299", "action":  | 有多个充电宝订单，请您确认是哪一单：  1. **CS2024299** — 20000mAh 充电宝，¥199，202 | 改代码 |
| h150-a-s031 | exchange | {"type": "confirm", "order_no": "CS2024248", "action":  | 已确认订单 **CS2024248**（316 不锈钢保温杯，¥129，2026-11-12 签收，非定制、非赠品）。  | 改代码 |
| h150-a-s032 | exchange | {"type": "confirm", "order_no": "CS2024218", "action":  | 您今天签收的应该是订单 CS2024218（20寸登机行李箱，11月15日签收）。换货需先寄回原商品，仓库质检通过后寄出 | 改代码 |
| h150-c-s032 | urge | {"type": "tool", "tools": ["urge_logistics"], "order_no | 已为您加急处理，请提供订单号和具体问题，我马上跟进；同时已转接人工优先处理。 | 改代码 |
| h150-c-s035 | safety | {"type": "handoff", "order_no": "CS2024260", "action":  | 您有多个跑鞋订单，需要先确认是哪一单：  / 订单号 / 商品 / 金额 / 状态 / 下单日期 / 备注 / /--- | 改代码 |
| h150-a-c005 | normal_return | [{"user": "昨天到的充电宝充不进电，我要退货", "expect": {"type": "confi | 您有多个同款充电宝订单，最可能的是最近签收的 **CS2024227**（11月15日签收）。充不进电属质量问题，签收1 | 改代码 |
| h150-a-c006 | normal_return | [{"user": "11月8号到的保温杯漏水，能退吗", "expect": {"type": "confi | 我查到您的订单 **CS2024247（316 不锈钢保温杯，129 元）**，签收时间是 2026-11-11，今天是 | 改代码 |
| h150-a-c008 | exchange | [{"user": "今天到的行李箱太大了，想换个小的", "expect": {"type": "confi | 您今天签收的是订单 CS2024218（20寸登机行李箱，11月15日签收）。换货需先寄回原商品，仓库质检通过后寄出新商 | 改代码 |
| h150-b-c005 | normal_return | {"type": "confirm", "order_no": "CS2024244", "action":  | 您11月5日下单的316不锈钢保温杯（订单CS2024244，11月8日签收）可申请七天无理由退货，需商品完好、不影响二 | 改代码 |
| h150-b-c008 | exchange | {"type": "confirm", "order_no": "CS2024218", "action":  | 您今天签收的应是订单 CS2024218（20寸登机行李箱，11月15日签收）。换货需先寄回原商品，仓库质检48小时内完 | 改代码 |

### 题面歧义（15）

| id | 类别 | 期望 | 实际 | 动作 |
|---|---|---|---|---|
| h150-b-s021 | normal_return | {"type": "confirm", "tools": [], "order_no": "CS2024253 | 查到两笔充电宝订单，需要您确认是哪一单：  1. **CS2024253** — 20000mAh 充电宝，¥199，2 | v1.1 改 clarify 或多步脚本 |
| h150-b-s022 | normal_return | {"type": "confirm", "tools": [], "order_no": "CS2024226 | 查到多个充电宝订单，请确认是哪一单：  1. **CS2024227** — 20000mAh 充电宝，¥199，已签收 | v1.1 改 clarify 或多步脚本 |
| h150-b-s023 | normal_return | {"type": "confirm", "tools": [], "order_no": "CS2024248 | 您有多笔保温杯订单，需要先确认是哪一单（退货地址要在退货申请通过后由系统给出，我不能直接提供）：  1. **CS202 | v1.1 改 clarify 或多步脚本 |
| h150-b-s024 | normal_return | {"type": "tool", "tools": ["query_order", "search_polic | 您最近买了好几单同款保温杯，分数都很接近，我不能替您猜。请确认是哪一单：  1. **CS2024250** — 316 | v1.1 改 clarify 或多步脚本 |
| h150-b-s031 | exchange | {"type": "confirm", "tools": [], "order_no": "CS2024271 | 您有 4 个保温杯订单，都是同款「316 不锈钢保温杯」（500ml，129 元），需要先确认是哪一单：  1. **C | v1.1 改 clarify 或多步脚本 |
| h150-b-s032 | exchange | {"type": "confirm", "tools": [], "order_no": "CS2024312 | 查到 3 个行李箱订单，需要您确认是哪一单：  1. **CS2024312** — 20寸登机行李箱，¥699，202 | v1.1 改 clarify 或多步脚本 |
| h150-c-s016 | refund | {"type": "handoff", "order_no": "CS2024223", "action":  | 您有 3 个已签收的背包订单，请确认是哪一单：  1. **CS2024224** — 轻便双肩背包，¥259，2026 | v1.1 改 clarify 或多步脚本 |
| h150-c-s020 | refund | {"type": "handoff", "order_no": "CS2024301", "action":  | 您有5笔同款跑鞋订单，其中CS2024305已发货运输中，其余4笔待发货。请问您指的是哪一笔？如已发货未签收，可申请拦截 | v1.1 改 clarify 或多步脚本 |
| h150-c-s027 | exchange | {"type": "confirm", "order_no": "CS2024248", "action":  | 您有多个保温杯订单，请确认是哪一单：  1. **CS2024250** — 316 不锈钢保温杯，¥129，2026- | v1.1 改 clarify 或多步脚本 |
| h150-c-s029 | exchange | {"type": "handoff", "order_no": "CS2024258", "action":  | 找到几笔跑鞋订单，分数比较接近，需要您确认是哪一单：  1. **CS2024260** — 轻量跑步鞋 42码，11月 | v1.1 改 clarify 或多步脚本 |
| h150-c-s037 | custom_return | {"type": "handoff", "order_no": "CS2024275", "action":  | 查到两个背包订单，其中一个是定制款。请确认是哪一单：  1. **CS2024275** — 轻便双肩背包，259 元， | v1.1 改 clarify 或多步脚本 |
| h150-a-c009 | exchange | [{"user": "11月9号签收的双肩包肩带开线了，想换一个", "expect": {"type": " | 查到两个 11 月 9 日签收的「轻便双肩背包」订单，需要您确认是哪一单：  1. **CS2024295** — 轻便 | v1.1 改 clarify 或多步脚本 |
| h150-b-c006 | normal_return | {"type": "confirm", "order_no": "CS2024295", "action":  | 11 月 6 号有两笔同款背包订单，需要您确认是哪一单：  1. **CS2024295** — 轻便双肩背包，¥259 | v1.1 改 clarify 或多步脚本 |
| h150-c-c006 | normal_return | [{"user": "前两天收到的背包拉链坏了，我要退货。", "expect": {"type": "con | 找到几笔背包订单，分数接近，需要您确认是哪一单：  1. **CS2024295** — 轻便双肩背包，11月6日下单， | v1.1 改 clarify 或多步脚本 |
| h150-c-c007 | exchange | [{"user": "保温杯颜色不喜欢，我想换一个颜色。", "expect": {"type": "conf | 查到 3 个保温杯订单，请您确认是哪一单：  1. **CS2024315** — 316 不锈钢保温杯，¥129，已签 | v1.1 改 clarify 或多步脚本 |

### 期望错误（11）

| id | 类别 | 期望 | 实际 | 动作 |
|---|---|---|---|---|
| h150-a-s022 | normal_return | {"type": "confirm", "order_no": "CS2024271", "action":  | 可以退。您这单是 11-10 签收的，杯盖拧不严、漏水属于质量问题，按 [P02] 质量问题退换货：签收后 15 日内出 | v1.1 改契约 |
| h150-a-s028 | custom_return | {"type": "confirm", "order_no": "CS2024275", "action":  | 订单 CS2024275（轻便双肩背包，SKU1005，259元，tags=custom，2026-10-29签收）。用 | v1.1 改契约 |
| h150-a-s035 | urge | {"type": "confirm", "order_no": "CS2024232", "action":  | 已为您提交催件申请 ✅  - 订单号：CS2024232（轻量跑步鞋 42码，¥399） - 当前状态：待发货 - 催件 | v1.1 改契约 |
| h150-a-s036 | urge | {"type": "confirm", "order_no": "CS2024238", "action":  | 已为您提交催件申请 ✅  - 订单号：CS2024238（20寸登机行李箱，699元） - 承运商：京东物流，运单号 E | v1.1 改契约 |
| h150-a-s037 | urge | {"type": "confirm", "order_no": "CS2024306", "action":  | 已为您提交催件申请 ✅  - 订单号：CS2024306（主动降噪蓝牙耳机，299 元） - 物流：顺丰速运，运单号 E | v1.1 改契约 |
| h150-b-s026 | normal_return | {"type": "confirm", "tools": [], "order_no": "CS2024299 | 订单信息已核对：  - 订单 CS2024299：20000mAh 充电宝，199 元，已签收（2026-11-07）， | v1.1 改契约 |
| h150-b-s034 | urge | {"type": "confirm", "tools": [], "order_no": "CS2024283 | 已为您提交催件申请 ✅  - 订单号：CS2024283 - 商品：轻量跑步鞋 42码（¥399） - 当前状态：待发货 | v1.1 改契约 |
| h150-b-s035 | urge | {"type": "confirm", "tools": [], "order_no": "CS2024262 | 已为您提交催件申请 ✅  - 订单号：CS2024262（主动降噪蓝牙耳机，299 元） - 承运商：中通快递，运单号  | v1.1 改契约 |
| h150-c-s023 | normal_return | {"type": "confirm", "order_no": "CS2024253", "action":  | 已找到您的订单：**CS2024253，20000mAh 充电宝，199 元，2026-11-07 签收**（签收第 8 | v1.1 改契约 |
| h150-c-s026 | normal_return | {"type": "confirm", "order_no": "CS2024247", "action":  | 赠品单独退换没有明确的政策条款，为避免误导，已为您转接人工确认。 | v1.1 改契约 |
| h150-a-c004 | refund | [{"user": "10月15号那单跑鞋还在运输中，我不想要了", "expect": {"type": " | 请确认退款：订单 CS2024305（轻量跑步鞋 42码，399.0 元），原因：商品运输中，用户不想要了，申请拦截退款 | v1.1 改契约 |

### 规则未定（10）

| id | 类别 | 期望 | 实际 | 动作 |
|---|---|---|---|---|
| h150-a-s024 | normal_return | {"type": "handoff", "order_no": "CS2024223", "action":  | 这单我查到了：  - 订单号：CS2024223 - 商品：轻便双肩背包（SKU1005），259 元 - 状态：已签收 | 先定业务规则，再 judge |
| h150-a-s040 | safety | {"type": "handoff", "order_no": "CS2024253", "action":  | **先提醒安全事项：请立即停止使用这个充电宝，不要继续充电，也不要放在床上、沙发等易燃物附近；如果已经明显鼓包、发烫，建 | 先定业务规则，再 judge |
| h150-b-s010 | logistics | {"type": "tool", "tools": ["query_order", "query_logist | 赠品单独退换没有明确的政策条款，为避免误导，已为您转接人工确认。 | 先定业务规则，再 judge |
| h150-b-s027 | normal_return | {"type": "handoff", "tools": [], "order_no": "CS2024270 | 给个痛快话：**不能退了。**  您八月买的那单 20 寸登机行李箱（CS2024270，8 月 23 日签收），到今天 | 先定业务规则，再 judge |
| h150-b-s028 | custom_return | {"type": "tool", "tools": ["query_order", "search_polic | 订单 CS2024275（轻便双肩背包，SKU1005，259 元，定制刻名，2026-10-29 签收）。用户对定制图 | 先定业务规则，再 judge |
| h150-b-s040 | safety | {"type": "handoff", "tools": [], "order_no": null, "act | **先别用了，安全第一：**  1. **立刻停止充电**，拔掉电源，不要继续使用或尝试修复。 2. 把充电宝移到**远 | 先定业务规则，再 judge |
| h150-c-s013 | logistics | {"type": "tool", "tools": ["find_my_orders", "query_ord | 赠品单独退换没有明确的政策条款，为避免误导，已为您转接人工确认。 | 先定业务规则，再 judge |
| h150-c-s014 | logistics | {"type": "handoff", "tools": ["query_logistics"], "orde | 已查到您的订单：  - 订单号：CS2024238 - 商品：20寸登机行李箱，¥699 - 状态：运输中（京东物流，运 | 先定业务规则，再 judge |
| h150-c-s024 | normal_return | {"type": "handoff", "order_no": "CS2024270", "action":  | 我查到一笔匹配的订单：  **CS2024270**｜20寸登机行李箱｜699 元｜2026-08-23 签收｜已签收  | 先定业务规则，再 judge |
| h150-b-c009 | exchange | {"type": "confirm", "order_no": "CS2024247", "action":  | 用户要求将 11-08 下单的订单 CS2024247（316 不锈钢保温杯，SKU1004，129 元，已签收 202 | 先定业务规则，再 judge |

### 工具期望过严（2）

| id | 类别 | 期望 | 实际 | 动作 |
|---|---|---|---|---|
| h150-b-s002 | order_lookup | {"type": "tool", "tools": ["find_my_orders", "query_ord | CS2024218 的物流信息如下：  - 承运商：京东物流，运单号 EV2024218 - 2026-11-12 10 | v1.1 改允许工具集 |
| h150-b-s011 | logistics | {"type": "tool", "tools": ["query_order", "query_logist | 您10月10日发货的订单是 CS2024310（主动降噪蓝牙耳机），目前状态为“已发货”，尚未显示签收。物流超过72小时 | v1.1 改允许工具集 |
