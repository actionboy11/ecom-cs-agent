# 电商售后客服 Agent

本上下文描述「买家发起售后诉求 → AI Agent 处理 → 必要时交给坐席」这条链路中使用的业务语言。代码、文档、提交信息、面试讲述都应使用这里的术语。

## Language

**买家 Customer**:
发起订单并可能提出售后诉求的自然人。
_Avoid_: 用户、客户、consumer、consumer user

**坐席 CS Agent**:
处理人工转接的真人客服。与本系统的 AI Agent 是两个不同的角色。
_Avoid_: Agent、客服、人工客服（口语可，正式文档用坐席）

**AI Agent**:
本系统中由 LangGraph 驱动、代替坐席处理售后诉求的程序。
_Avoid_: 机器人、bot、智能体（口语可）

**会话 Thread**:
一段有唯一 ID、归属于某个买家的连续对话。
_Avoid_: session、对话窗口、chat

**轮次 Turn**:
一条买家消息加上 AI Agent 对它的完整处理。
_Avoid_: 回合、message count、循环次数

**订单 Order**:
买家的一次购买记录，含商品、金额与状态。
_Avoid_: 单、交易、order record

**售后请求 After-Sales Request**:
买家针对某笔订单发起的售后诉求，类型为退款、退货或换货。
_Avoid_: 退款单、工单、售后单（作为泛称）、refund（泛称）

**退款 Refund**:
售后请求的一种类型：买家不寄回商品或寄回后，平台把钱退回。
_Avoid_: 用"退款"泛指所有售后

**退货 Return**:
售后请求的一种类型：买家寄回商品并申请退款。
_Avoid_: 与"退款"混用

**换货 Exchange**:
售后请求的一种类型：买家寄回商品，换取同款的其他规格。
_Avoid_: 与"退货"混用

**拒答 Refusal**:
AI Agent 对越权、竞品比较、无关闲聊、违规请求四类问题的标准拒绝响应。
_Avoid_: 兜底话术、error reply

**物流 Logistics**:
订单对应的承运与配送信息。
_Avoid_: 快递、shipment、配送

**轨迹事件 Trace Event**:
物流中单个时间点的节点记录。
_Avoid_: 进度、节点、log entry

**政策 Policy**:
平台公布的售后规则条目，编号 P01–P12。
_Avoid_: 规则、条款、SOP、knowledge

**意图 Intent**:
买家一条消息的业务分类，取值为 order_query / logistics / refund / policy / complaint / product_info / other。
_Avoid_: 类型、类别、topic

**槽位 Slot**:
完成一次处理所必需的参数，如订单号、SKU、退款原因。
_Avoid_: 参数、字段、entity

**人工转接 Handoff**:
把会话交给坐席的过程，包含挂起与恢复两个阶段。
_Avoid_: 转人工、升级、escalation

**审计日志 Audit Log**:
业务侧记录「谁、对哪个资源、做了什么、结果如何」，用于追责与排查。
_Avoid_: 日志、trace、log

**运行轨迹 Agent Trace**:
AI Agent 节点级的执行记录，含耗时与中间结果。
_Avoid_: 审计、日志、monitoring

**越权 Denied Access**:
已认证身份尝试访问不属于自己的资源。
_Avoid_: 无权限、403、forbidden
