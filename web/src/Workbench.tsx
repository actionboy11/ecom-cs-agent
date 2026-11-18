import { useCallback, useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import * as api from "./api";

type Message = {
  role: "user" | "assistant";
  content: string;
  details?: api.ChatReply;
  actions?: api.PendingAction[];
};

type View = "chat" | "orders" | "after-sales" | "map";

const THREAD_PREFIX = "ui-";
const WRITE_TYPES = new Set(["refund", "return", "exchange"]);

const CAPABILITIES = [
  {
    key: "order",
    mark: "01",
    title: "查订单",
    body: "按商品、时间、状态找回订单，不再让用户背订单号。",
    prompt: "查一下我最近买的耳机",
  },
  {
    key: "return",
    mark: "02",
    title: "退货退款",
    body: "按待发货、运输中、已签收分流；签收后按 7 / 15 / 30 天判断。",
    prompt: "那个水杯漏水了，我要退货",
  },
  {
    key: "exchange",
    mark: "03",
    title: "换货",
    body: "质量问题优先换货；签收 16–30 天需原因，运费买家承担。",
    prompt: "耳机有杂音，我想换一个",
  },
  {
    key: "address",
    mark: "04",
    title: "改地址",
    body: "只对未发货订单开放；识别订单后由用户在前端填写。",
    prompt: "帮我把水杯那单的地址改到公司",
  },
  {
    key: "invoice",
    mark: "05",
    title: "开发票",
    body: "签收 30 天内可开；先识别订单，再让用户填抬头税号。",
    prompt: "那个水杯的发票怎么开",
  },
  {
    key: "urge",
    mark: "06",
    title: "催件",
    body: "物流超过 72 小时无更新可催；已签收订单不再重复催。",
    prompt: "我的耳机怎么还没到",
  },
] as const;

const STEPS = [
  ["识别", "先定位订单，不预设订单号"],
  ["判断", "状态 + 天数 + 质量问题"],
  ["动作", "直接办 / 表单 / 拦截 / 转人工"],
  ["留痕", "确认、售后单、审计记录"],
];

function roleLabel(role: string): string {
  const key = role.toUpperCase().replace(/^ROLE_/, "");
  if (key === "CS_AGENT") return "坐席";
  if (key === "CUSTOMER") return "买家";
  return role;
}

function isWriteAction(action: api.PendingAction): boolean {
  return WRITE_TYPES.has(action.type || "");
}

function withoutTable(text: string): string {
  return text
    .split("\n")
    .filter((line) => !line.trim().startsWith("|"))
    .join("\n")
    .trim();
}

function CandidateCards({
  candidates,
  onPick,
  onNone,
  disabled,
}: {
  candidates: NonNullable<api.ChatReply["candidates"]>;
  onPick: (orderNo: string) => void;
  onNone: () => void;
  disabled: boolean;
}) {
  return (
    <div className="candidates">
      {candidates.slice(0, 3).map((item) => (
        <div className="candidate" key={item.orderNo}>
          <div className="candidate-main">
            <strong>{item.orderNo}</strong>
            <span>{item.item}</span>
          </div>
          <div className="candidate-meta">
            <span>{item.status}</span>
            <span>¥{item.amount}</span>
            <span>下单 {item.createdAt}</span>
            {item.deliveredAt && <span>签收 {item.deliveredAt.slice(0, 10)}</span>}
          </div>
          {item.reasons && item.reasons.length > 0 && (
            <div className="candidate-reasons">{item.reasons.join(" · ")}</div>
          )}
          <button onClick={() => onPick(item.orderNo || "")} disabled={disabled}>
            就是这单
          </button>
        </div>
      ))}
      <button className="ghost none-button" onClick={onNone} disabled={disabled}>
        都不是，重新找
      </button>
    </div>
  );
}

function UserActionCard({
  token,
  action,
  toast,
}: {
  token: string;
  action: NonNullable<api.ChatReply["ui_action"]>;
  toast: (text: string) => void;
}) {
  const orderNo = action.order_no || "";
  const [receiver, setReceiver] = useState("");
  const [phone, setPhone] = useState("");
  const [address, setAddress] = useState("");
  const [title, setTitle] = useState("");
  const [taxId, setTaxId] = useState("");
  const [email, setEmail] = useState("");
  const [reason, setReason] = useState("");
  const [evidence, setEvidence] = useState("");
  const [target, setTarget] = useState("");
  const [done, setDone] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit() {
    if (!orderNo) {
      toast("未识别到订单，请先选择订单");
      return;
    }
    setBusy(true);
    try {
      if (action.action === "change_address") {
        await api.updateAddress(token, orderNo, {
          receiver: receiver.trim(),
          phone: phone.trim(),
          address: address.trim(),
        });
        setDone("地址已更新");
      } else if (action.action === "invoice") {
        await api.createInvoice(token, orderNo, {
          title: title.trim(),
          taxId: taxId.trim(),
          email: email.trim(),
        });
        setDone("开票申请已提交");
      } else {
        const detail = evidence.trim() ? `${reason.trim()}；凭证：${evidence.trim()}` : reason.trim();
        await api.createAfterSales(token, {
          orderNo,
          type: action.action === "return" ? "RETURN" : "EXCHANGE",
          reason: target.trim() ? `${detail}；目标规格：${target.trim()}` : detail,
        });
        setDone(action.action === "return" ? "退货申请已提交" : "换货申请已提交");
      }
    } catch (err) {
      toast(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  if (done) return <div className="user-action done">{done}</div>;

  return (
    <div className="user-action">
      <div className="action-head">
        <span>{action.message || "请补充信息"}</span>
        <span className="action-order">{orderNo}</span>
      </div>
      {action.action === "change_address" && (
        <>
          <label>
            收件人
            <input value={receiver} onChange={(e) => setReceiver(e.target.value)} />
          </label>
          <label>
            手机号
            <input value={phone} onChange={(e) => setPhone(e.target.value)} />
          </label>
          <label>
            新地址
            <input value={address} onChange={(e) => setAddress(e.target.value)} />
          </label>
        </>
      )}
      {action.action === "invoice" && (
        <>
          <label>
            发票抬头
            <input value={title} onChange={(e) => setTitle(e.target.value)} />
          </label>
          <label>
            税号
            <input value={taxId} onChange={(e) => setTaxId(e.target.value)} />
          </label>
          <label>
            邮箱
            <input value={email} onChange={(e) => setEmail(e.target.value)} />
          </label>
        </>
      )}
      {(action.action === "return" || action.action === "exchange") && (
        <>
          <label>
            原因
            <input value={reason} onChange={(e) => setReason(e.target.value)} placeholder="例如：商品漏水，质量问题" />
          </label>
          <label>
            凭证/说明
            <input value={evidence} onChange={(e) => setEvidence(e.target.value)} />
          </label>
          {action.action === "exchange" && (
            <label>
              目标规格
              <input value={target} onChange={(e) => setTarget(e.target.value)} />
            </label>
          )}
        </>
      )}
      <button onClick={submit} disabled={busy}>
        {busy ? "提交中…" : "提交"}
      </button>
    </div>
  );
}

function OrderHistory({
  token,
  request,
  toast,
}: {
  token: string;
  request: NonNullable<api.ChatReply["history_request"]>;
  toast: (text: string) => void;
}) {
  const [page, setPage] = useState(request.page || 1);
  const [data, setData] = useState<api.OrderPage | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    setBusy(true);
    api
      .orderPage(token, {
        page,
        page_size: request.page_size || 10,
        created_from: request.created_from,
        created_to: request.created_to,
      })
      .then(setData)
      .catch((err) => toast(err instanceof Error ? err.message : String(err)))
      .finally(() => setBusy(false));
  }, [page, request.created_from, request.created_to, request.page_size, token, toast]);

  return (
    <div className="order-history">
      {data && (
        <>
          <table>
            <thead>
              <tr>
                <th>订单</th>
                <th>商品</th>
                <th>金额</th>
                <th>状态</th>
                <th>下单</th>
              </tr>
            </thead>
            <tbody>
              {data.items.map((item) => (
                <tr key={item.orderNo}>
                  <td>{item.orderNo}</td>
                  <td>{item.item}</td>
                  <td>¥{item.amount}</td>
                  <td>{item.status}</td>
                  <td>{item.createdAt}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="pager">
            <button className="ghost" disabled={busy || page <= 1} onClick={() => setPage((p) => Math.max(1, p - 1))}>
              上一页
            </button>
            <span>
              第 {data.page} 页 / 共 {data.total} 条
            </span>
            <button className="ghost" disabled={busy || !data.hasMore} onClick={() => setPage((p) => p + 1)}>
              下一页
            </button>
          </div>
        </>
      )}
    </div>
  );
}

function Landing({ onTry }: { onTry: (prompt: string) => void }) {
  return (
    <div className="landing">
      <div className="landing-copy">
        <p className="kicker">售后工作台 / 买家端</p>
        <h1>先定位订单，再决定怎么处理。</h1>
        <p>
          查单、退款、退货、换货、改地址、发票、催件，都在同一条订单上下文里完成。
          每个动作先判断状态与时效，再给结果。
        </p>
      </div>
      <div className="capability-grid">
        {CAPABILITIES.map((item) => (
          <button className="capability" key={item.key} onClick={() => onTry(item.prompt)}>
            <span className="capability-mark">{item.mark}</span>
            <span className="capability-title">{item.title}</span>
            <span className="capability-body">{item.body}</span>
            <span className="capability-prompt">试：{item.prompt}</span>
          </button>
        ))}
      </div>
    </div>
  );
}

function OrderPanel({
  token,
  toast,
  onAsk,
}: {
  token: string;
  toast: (text: string) => void;
  onAsk: (text: string) => void;
}) {
  const [page, setPage] = useState(1);
  const [data, setData] = useState<api.OrderPage | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    setBusy(true);
    api
      .orderPage(token, { page, page_size: 10 })
      .then(setData)
      .catch((err) => toast(err instanceof Error ? err.message : String(err)))
      .finally(() => setBusy(false));
  }, [page, token, toast]);

  return (
    <section className="panel">
      <div className="panel-head">
        <div>
          <p className="kicker">全部订单</p>
          <h2>我的订单</h2>
        </div>
        <span className="muted">{data ? `共 ${data.total} 单` : "加载中"}</span>
      </div>
      <table>
        <thead>
          <tr>
            <th>订单</th>
            <th>商品</th>
            <th>金额</th>
            <th>状态</th>
            <th>下单</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {data?.items.map((item) => (
            <tr key={item.orderNo}>
              <td>{item.orderNo}</td>
              <td>{item.item}</td>
              <td>¥{item.amount}</td>
              <td>{item.status}</td>
              <td>{item.createdAt}</td>
              <td>
                <button className="text-button" onClick={() => onAsk(`订单 ${item.orderNo} 是什么情况`)}>
                  问这单
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <div className="pager">
        <button className="ghost" disabled={busy || page <= 1} onClick={() => setPage((p) => p - 1)}>
          上一页
        </button>
        <span>第 {data?.page || page} 页</span>
        <button className="ghost" disabled={busy || !data?.hasMore} onClick={() => setPage((p) => p + 1)}>
          下一页
        </button>
      </div>
    </section>
  );
}

function AfterSalesPanel({ token, toast }: { token: string; toast: (text: string) => void }) {
  const [rows, setRows] = useState<api.AfterSale[] | null>(null);
  useEffect(() => {
    api
      .myAfterSales(token)
      .then(setRows)
      .catch((err) => toast(err instanceof Error ? err.message : String(err)));
  }, [token, toast]);

  return (
    <section className="panel">
      <div className="panel-head">
        <div>
          <p className="kicker">售后进度</p>
          <h2>我的售后</h2>
        </div>
        <span className="muted">{rows ? `${rows.length} 条` : "加载中"}</span>
      </div>
      {rows && rows.length === 0 && <p className="muted">还没有售后申请。</p>}
      {rows && rows.length > 0 && (
        <table>
          <thead>
            <tr>
              <th>申请单</th>
              <th>订单</th>
              <th>类型</th>
              <th>状态</th>
              <th>时间</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.requestNo}>
                <td>{row.requestNo}</td>
                <td>{row.orderNo}</td>
                <td>{row.type}</td>
                <td>
                  <span className={`status-dot ${row.status.toLowerCase()}`}>{row.status}</span>
                </td>
                <td>{row.createdAt || ""}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}

function CapabilityMap() {
  return (
    <section className="panel">
      <div className="panel-head">
        <div>
          <p className="kicker">能力地图</p>
          <h2>什么能做，什么不能做</h2>
        </div>
      </div>
      <div className="map-grid">
        <div>
          <h3>直接执行</h3>
          <p>查订单、查物流、催件、待发货退款、已签收退货/换货。</p>
        </div>
        <div>
          <h3>用户填写</h3>
          <p>改地址（待发货）、开发票（签收 30 天内）、退货原因与凭证。</p>
        </div>
        <div>
          <h3>先拦截</h3>
          <p>运输中退款先通知快递拦截，成功后再确认退款。</p>
        </div>
        <div>
          <h3>转人工</h3>
          <p>超过 30 天、拦截失败、安全问题、投诉升级。</p>
        </div>
      </div>
      <table>
        <thead>
          <tr>
            <th>状态</th>
            <th>退款</th>
            <th>退货</th>
            <th>换货</th>
            <th>发票</th>
            <th>地址</th>
          </tr>
        </thead>
        <tbody>
          <tr><td>待发货</td><td>可，确认后</td><td>—</td><td>—</td><td>—</td><td>可</td></tr>
          <tr><td>运输中</td><td>先拦截</td><td>拦截/拒收</td><td>拦截/拒收</td><td>—</td><td>—</td></tr>
          <tr><td>签收 0–7 天</td><td>退货退款</td><td>无理由</td><td>无理由</td><td>可</td><td>—</td></tr>
          <tr><td>签收 8–15 天</td><td>质量问题</td><td>质量 + 凭证</td><td>质量 + 凭证</td><td>可</td><td>—</td></tr>
          <tr><td>签收 16–30 天</td><td>原因 + 买家运费</td><td>可</td><td>可</td><td>可</td><td>—</td></tr>
          <tr><td>签收 30 天以上</td><td>解释 / 转人工</td><td>—</td><td>—</td><td>解释 / 转人工</td><td>—</td></tr>
        </tbody>
      </table>
    </section>
  );
}

export default function BuyerWorkbench({
  user,
  onLogout,
  toast,
}: {
  user: api.User;
  onLogout: () => void;
  toast: (text: string) => void;
}) {
  const thread = `${THREAD_PREFIX}${user.username}`;
  const [messages, setMessages] = useState<Message[]>([]);
  const [text, setText] = useState("");
  const [sending, setSending] = useState(false);
  const [view, setView] = useState<View>("chat");
  const [lastReply, setLastReply] = useState<api.ChatReply | null>(null);
  const [orders, setOrders] = useState<api.OrderPage | null>(null);
  const listRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = useCallback(() => {
    const box = listRef.current;
    if (!box) return;
    box.scrollTop = box.scrollHeight;
  }, []);

  useEffect(() => {
    api
      .history(user.token, thread)
      .then((rows) =>
        setMessages(rows.map((row) => ({ role: row.role as Message["role"], content: row.content }))),
      )
      .catch(() => setMessages([]));
  }, [thread, user.token]);

  useEffect(() => {
    api
      .orderPage(user.token, { page: 1, page_size: 10 })
      .then(setOrders)
      .catch(() => setOrders(null));
  }, [user.token]);

  useEffect(scrollToBottom, [messages, scrollToBottom]);

  async function dispatch(content: string) {
    if (!content || sending) return;
    setSending(true);
    setText("");
    setView("chat");
    setMessages((prev) => [
      ...prev.map((message) => ({ ...message, actions: undefined })),
      { role: "user", content },
    ]);
    try {
      const reply = await api.chat(user.token, thread, content);
      setLastReply(reply);
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: reply.reply, details: reply, actions: reply.pending_actions },
      ]);
      if (reply.history_request) {
        setView("chat");
      }
    } catch (err) {
      toast(err instanceof Error ? err.message : String(err));
      setMessages((prev) => [...prev, { role: "assistant", content: "服务暂时不可用，请稍后再试。" }]);
    } finally {
      setSending(false);
    }
  }

  async function handleWrite(message: Message, approved: boolean) {
    if (sending) return;
    setSending(true);
    setMessages((prev) => [
      ...prev.map((item) => ({ ...item, actions: undefined })),
      { role: "user", content: approved ? "确认办理" : "取消办理" },
    ]);
    try {
      const reply = await api.confirmWrite(user.token, thread, approved);
      setLastReply(reply);
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: reply.reply, details: reply, actions: reply.pending_actions },
      ]);
    } catch (err) {
      toast(err instanceof Error ? err.message : String(err));
    } finally {
      setSending(false);
    }
  }

  const currentOrder = orders?.items.find((item) => item.orderNo === lastReply?.order_no);

  return (
    <div className="workbench">
      <aside className="rail">
        <div className="rail-brand">
          <span className="rail-mark">CS</span>
          <span>售后工作台</span>
        </div>
        <nav className="rail-nav">
          <button className={view === "chat" ? "active" : ""} onClick={() => setView("chat")}>
            <span>对话</span>
            <small>处理当前问题</small>
          </button>
          <button className={view === "orders" ? "active" : ""} onClick={() => setView("orders")}>
            <span>我的订单</span>
            <small>{orders ? `${orders.total} 单` : "加载中"}</small>
          </button>
          <button className={view === "after-sales" ? "active" : ""} onClick={() => setView("after-sales")}>
            <span>售后进度</span>
            <small>申请与审核</small>
          </button>
          <button className={view === "map" ? "active" : ""} onClick={() => setView("map")}>
            <span>能力地图</span>
            <small>边界与规则</small>
          </button>
        </nav>
        <div className="rail-foot">
          <div>{user.displayName || user.username}</div>
          <small>{roleLabel(user.role)}</small>
          <button className="rail-logout" onClick={onLogout}>
            退出
          </button>
        </div>
      </aside>

      <main className="stage">
        <header className="stage-head">
          <div>
            <p className="kicker">{view === "chat" ? "当前会话" : "工作台"}</p>
            <h2>
              {view === "chat" && "售后对话"}
              {view === "orders" && "订单"}
              {view === "after-sales" && "售后进度"}
              {view === "map" && "能力边界"}
            </h2>
          </div>
          <div className="stage-status">
            <span className="status-dot live">在线</span>
            <span className="muted">本地演示 · 真实业务接口</span>
          </div>
        </header>

        {view === "chat" && (
          <>
            {messages.length === 0 ? (
              <Landing onTry={dispatch} />
            ) : (
              <div className="messages" ref={listRef} aria-live="polite">
                {messages.map((message, index) => (
                  <article className={`msg ${message.role}`} key={index}>
                    <div className="msg-role">{message.role === "user" ? "你" : "售后助手"}</div>
                    <div className="body">
                      <ReactMarkdown remarkPlugins={[remarkGfm]}>
                        {message.details?.candidates?.length ? withoutTable(message.content) : message.content}
                      </ReactMarkdown>
                    </div>
                    {message.details?.candidates && message.details.candidates.length > 0 && (
                      <CandidateCards
                        candidates={message.details.candidates}
                        onPick={(orderNo) => dispatch(`选择订单 ${orderNo}`)}
                        onNone={() => dispatch("都不是，请重新查")}
                        disabled={sending}
                      />
                    )}
                    {message.details?.history_request && (
                      <OrderHistory token={user.token} request={message.details.history_request} toast={toast} />
                    )}
                    {message.details?.ui_action && (
                      <UserActionCard token={user.token} action={message.details.ui_action} toast={toast} />
                    )}
                    {message.actions && message.actions.length > 0 && (
                      <div className="actions">
                        <button
                          onClick={() =>
                            message.actions!.some(isWriteAction)
                              ? handleWrite(message, true)
                              : dispatch("确认执行")
                          }
                          disabled={sending}
                        >
                          {message.actions!.some(isWriteAction)
                            ? message.actions!.find(isWriteAction)?.label || "确认办理"
                            : "确认执行"}
                        </button>
                        <button
                          className="ghost"
                          onClick={() =>
                            message.actions!.some(isWriteAction)
                              ? handleWrite(message, false)
                              : dispatch("取消")
                          }
                          disabled={sending}
                        >
                          取消
                        </button>
                      </div>
                    )}
                    {message.details?.fallback_reason && (
                      <p className="fallback-note">已切换到确定性流程（原因：{message.details.fallback_reason}）</p>
                    )}
                  </article>
                ))}
              </div>
            )}

            <form className="composer" onSubmit={(e) => { e.preventDefault(); dispatch(text.trim()); }}>
              <input
                value={text}
                onChange={(e) => setText(e.target.value)}
                placeholder="说说你遇到的问题，例如：那个水杯漏水了"
                autoComplete="off"
              />
              <button type="submit" disabled={sending}>
                {sending ? "处理中…" : "发送"}
              </button>
            </form>
          </>
        )}

        {view === "orders" && <OrderPanel token={user.token} toast={toast} onAsk={dispatch} />}
        {view === "after-sales" && <AfterSalesPanel token={user.token} toast={toast} />}
        {view === "map" && <CapabilityMap />}
      </main>

      <aside className="context">
        <section className="context-block">
          <p className="kicker">当前订单</p>
          {currentOrder ? (
            <div className="context-order">
              <strong>{currentOrder.item}</strong>
              <span>{currentOrder.orderNo}</span>
              <span>
                {currentOrder.status} · ¥{currentOrder.amount}
              </span>
              <span>下单 {currentOrder.createdAt}</span>
            </div>
          ) : (
            <p className="muted">还没有锁定订单。先描述商品或时间，助手会先帮你定位。</p>
          )}
        </section>

        <section className="context-block">
          <p className="kicker">下一步会怎么走</p>
          <ol className="step-list">
            {STEPS.map(([title, body]) => (
              <li key={title}>
                <strong>{title}</strong>
                <span>{body}</span>
              </li>
            ))}
          </ol>
        </section>

        <section className="context-block">
          <p className="kicker">能直接试</p>
          <div className="quick-list">
            {CAPABILITIES.slice(0, 4).map((item) => (
              <button key={item.key} onClick={() => dispatch(item.prompt)}>
                {item.title}
                <small>{item.prompt}</small>
              </button>
            ))}
          </div>
        </section>
      </aside>
    </div>
  );
}
