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

const INTENT_LABELS: Record<string, string> = {
  order_query: "订单查询",
  logistics: "物流",
  refund: "退款/售后",
  policy: "政策",
  product_info: "商品",
  complaint: "投诉",
  other: "其他",
};

function roleLabel(role: string): string {
  const key = role.toUpperCase().replace(/^ROLE_/, "");
  return key === "CS_AGENT" ? "坐席" : key === "CUSTOMER" ? "买家" : role;
}

function Toast({ text }: { text: string }) {
  return text ? <div className="toast">{text}</div> : null;
}

function Login({ onLogin }: { onLogin: (user: api.User) => void }) {
  const [username, setUsername] = useState("buyer_a");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setError("");
    try {
      const user = await api.login(username.trim(), password);
      onLogin({ ...user, username: username.trim() });
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      setError(message.includes("401") ? "用户名或密码错误" : `登录失败：${message}`);
    }
  }

  return (
    <main id="login-view" className="card login-card">
      <div className="kicker">售后调度台</div>
      <h1>把每一单售后，落到具体的人手里。</h1>
      <p className="sub">买家用它对话，坐席用它审批。</p>
      <form className="login-form" onSubmit={submit}>
        <label>
          用户名
          <input id="username" value={username} onChange={(e) => setUsername(e.target.value)} autoComplete="username" />
        </label>
        <label>
          密码
          <input
            id="password"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete="current-password"
          />
        </label>
        <button type="submit">登录</button>
        {error && <p className="error">{error}</p>}
      </form>
    </main>
  );
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
            <span>{item.amount} 元</span>
            <span>下单 {item.createdAt}</span>
            {item.deliveredAt && <span>签收 {item.deliveredAt.slice(0, 10)}</span>}
          </div>
          {item.reasons && item.reasons.length > 0 && (
            <div className="candidate-reasons">{item.reasons.join(" · ")}</div>
          )}
          <button onClick={() => onPick(item.orderNo || "")} disabled={disabled}>
            选这单
          </button>
        </div>
      ))}
      <button className="ghost none-button" onClick={onNone} disabled={disabled}>
        都不是
      </button>
    </div>
  );
}

function Details({ reply }: { reply: api.ChatReply }) {
  const intent = INTENT_LABELS[reply.intent || ""] || reply.intent || "—";
  const chain = reply.chain === "llm" ? "模型生成" : "模板兜底";
  const tool = reply.tool_result;
  const status = tool?.data
    ? String(tool.data.status || tool.data.orderStatus || tool.data.state || "")
    : "";
  return (
    <details className="details">
      <summary>这次是怎么处理的</summary>
      <p>
        意图：{intent} · 链路：{chain} · 耗时：{reply.latency_ms ?? 0} ms
      </p>
      {tool && (
        <p>
          工具：
          {tool.error ? `调用失败（${tool.error}）` : tool.tool || "业务工具"}
          {!tool.error && status ? ` · 当前状态：${status}` : ""}
        </p>
      )}
      {(reply.policy_refs?.length ?? 0) > 0 && <p>政策引用：{reply.policy_refs!.join("、")}</p>}
      {(reply.tool_trace?.length ?? 0) > 0 && (
        <p>
          工具轨迹：
          {reply.tool_trace!
            .map((item) => `${item.tool || "?"}${item.error ? "（失败）" : ""}`)
            .join(" → ")}
        </p>
      )}
    </details>
  );
}

function BuyerChat({ user, onLogout, toast }: { user: api.User; onLogout: () => void; toast: (t: string) => void }) {
  const thread = `ui-${user.username}`;
  const [messages, setMessages] = useState<Message[]>([]);
  const [text, setText] = useState("");
  const [sending, setSending] = useState(false);
  const [afterSales, setAfterSales] = useState<api.AfterSale[] | null>(null);
  const [showAfterSales, setShowAfterSales] = useState(false);
  const listRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = useCallback(() => {
    const box = listRef.current;
    if (!box) return;
    box.scrollTop = box.scrollHeight;
    requestAnimationFrame(() => {
      box.scrollTop = box.scrollHeight;
    });
  }, []);

  useEffect(() => {
    api
      .history(user.token, thread)
      .then((rows) => setMessages(rows.map((row) => ({ role: row.role as Message["role"], content: row.content }))))
      .catch(() => setMessages([]));
  }, [thread, user.token]);

  useEffect(scrollToBottom, [messages, scrollToBottom]);

  async function dispatch(content: string) {
    if (!content || sending) return;
    setSending(true);
    setText("");
    setMessages((prev) => [
      ...prev.map((message) => ({ ...message, actions: undefined })),
      { role: "user", content },
    ]);
    try {
      const reply = await api.chat(user.token, thread, content);
      const extra: Message[] = [
        { role: "assistant", content: reply.reply, details: reply, actions: reply.pending_actions },
      ];
      if (reply.needs_human) {
        extra.push({ role: "assistant", content: "已转接人工坐席，请等待处理。" });
      }
      setMessages((prev) => [...prev, ...extra]);
    } catch (err) {
      toast(`调用失败：${err instanceof Error ? err.message : String(err)}`);
      setMessages((prev) => [...prev, { role: "assistant", content: "刚才没连上服务，请稍后再试。" }]);
    } finally {
      setSending(false);
    }
  }

  async function send(event: React.FormEvent) {
    event.preventDefault();
    await dispatch(text.trim());
  }

  async function toggleAfterSales() {
    const next = !showAfterSales;
    setShowAfterSales(next);
    if (next && !afterSales) {
      try {
        setAfterSales(await api.myAfterSales(user.token));
      } catch (err) {
        toast(`售后加载失败：${err instanceof Error ? err.message : String(err)}`);
      }
    }
  }

  async function handleWrite(message: Message, approved: boolean) {
    if (sending) return;
    setSending(true);
    setMessages((prev) => [
      ...prev.map((item) => ({ ...item, actions: undefined })),
      { role: "user", content: approved ? "确认退款" : "取消退款" },
    ]);
    try {
      const reply = await api.confirmWrite(user.token, thread, approved);
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: reply.reply, details: reply, actions: reply.pending_actions },
      ]);
    } catch (err) {
      toast(`确认失败：${err instanceof Error ? err.message : String(err)}`);
    } finally {
      setSending(false);
    }
  }

  return (
    <main id="chat-view" className="card">
      <div className="messages" ref={listRef} aria-live="polite">
        {messages.length === 0 && <p className="muted">直接问订单、物流或售后。</p>}
        {messages.map((message, index) => (
          <div className={`msg ${message.role}`} key={index}>
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
            {message.actions && message.actions.length > 0 && (
              <div className="actions">
                <button
                  onClick={() =>
                    message.actions!.some((action) => action.type === "refund")
                      ? handleWrite(message, true)
                      : dispatch("确认执行")
                  }
                  disabled={sending}
                >
                  {message.actions!.some((action) => action.type === "refund") ? "确认退款" : "确认执行"}
                </button>
                <button
                  className="ghost"
                  onClick={() =>
                    message.actions!.some((action) => action.type === "refund")
                      ? handleWrite(message, false)
                      : dispatch("取消")
                  }
                  disabled={sending}
                >
                  取消
                </button>
              </div>
            )}
            {message.details && <Details reply={message.details} />}
          </div>
        ))}
      </div>
      <form id="composer" className="composer" onSubmit={send}>
        <input
          id="message-input"
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="例如：CS2024001 到哪了"
          autoComplete="off"
        />
        <button type="submit" disabled={sending}>
          发送
        </button>
      </form>
      <button className="after-sales-toggle" onClick={toggleAfterSales}>
        {showAfterSales ? "收起售后进度" : "我的售后进度"}
      </button>
      {showAfterSales && (
        <div className="after-sales-body">
          {afterSales === null && <p className="muted">加载中…</p>}
          {afterSales && afterSales.length === 0 && <p className="muted">还没有售后请求。</p>}
          {afterSales && afterSales.length > 0 && (
            <table>
              <thead>
                <tr>
                  <th>请求编号</th>
                  <th>订单</th>
                  <th>类型</th>
                  <th>状态</th>
                  <th>创建时间</th>
                </tr>
              </thead>
              <tbody>
                {afterSales.slice(0, 50).map((row) => (
                  <tr key={row.requestNo}>
                    <td>{row.requestNo}</td>
                    <td>{row.orderNo}</td>
                    <td>{row.type}</td>
                    <td>{row.status}</td>
                    <td>{row.createdAt || ""}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}
    </main>
  );
}

function AgentWorkbench({ user, toast }: { user: api.User; toast: (t: string) => void }) {
  const [tab, setTab] = useState<"approval" | "handoff" | "audit">("approval");
  const [pending, setPending] = useState<api.AfterSale[]>([]);
  const [handoffRows, setHandoffRows] = useState<api.Handoff[]>([]);
  const [auditRows, setAuditRows] = useState<api.AuditRow[]>([]);
  const [selected, setSelected] = useState("");
  const [approved, setApproved] = useState(true);
  const [note, setNote] = useState("");
  const [manualThread, setManualThread] = useState("");

  useEffect(() => {
    if (tab === "approval") {
      api
        .pendingAfterSales(user.token)
        .then((rows) => {
          setPending(rows);
          setSelected(rows[0]?.requestNo || "");
        })
        .catch((err) => toast(`待办加载失败：${err.message}`));
    }
    if (tab === "handoff") {
      api
        .handoffs(user.token)
        .then((rows) => {
          setHandoffRows(rows);
          setSelected(rows[0]?.thread_id || "");
        })
        .catch((err) => toast(`转接待办加载失败：${err.message}`));
    }
    if (tab === "audit") {
      api
        .audit(user.token)
        .then(setAuditRows)
        .catch((err) => toast(`审计加载失败：${err.message}`));
    }
  }, [tab, user.token, toast]);

  async function submitReview() {
    if (!selected) return;
    if (!approved && !note.trim()) {
      toast("驳回需要填写备注");
      return;
    }
    try {
      await api.review(user.token, selected, approved, note);
      toast("已提交");
      setNote("");
      setPending(await api.pendingAfterSales(user.token));
    } catch (err) {
      toast(`提交失败：${err instanceof Error ? err.message : String(err)}`);
    }
  }

  async function submitResume() {
    const thread = selected || manualThread.trim();
    if (!thread) {
      toast("请选择或填写会话 ID");
      return;
    }
    try {
      await api.resume(user.token, thread, approved, note);
      toast("已恢复");
      setNote("");
      setHandoffRows(await api.handoffs(user.token));
    } catch (err) {
      toast(`恢复失败：${err instanceof Error ? err.message : String(err)}`);
    }
  }

  return (
    <main id="agent-view" className="card">
      <div className="kicker">坐席侧</div>
      <h1>工作台</h1>
      <div className="tabs" role="tablist">
        {(["approval", "handoff", "audit"] as const).map((key) => (
          <button
            key={key}
            role="tab"
            className={`tab ${tab === key ? "active" : ""}`}
            onClick={() => setTab(key)}
          >
            {key === "approval" ? "售后审批" : key === "handoff" ? "转接待办" : "审计"}
          </button>
        ))}
      </div>

      {tab === "approval" && (
        <section className="tab-panel">
          {pending.length === 0 && <p className="muted">暂无待审批的售后申请。</p>}
          {pending.length > 0 && (
            <>
              <label>
                待办
                <select value={selected} onChange={(e) => setSelected(e.target.value)}>
                  {pending.map((row) => (
                    <option key={row.requestNo} value={row.requestNo}>
                      {row.requestNo} · {row.orderNo} · {row.type}
                    </option>
                  ))}
                </select>
              </label>
              <div className="row">
                <label>
                  <input type="radio" checked={approved} onChange={() => setApproved(true)} /> 通过
                </label>
                <label>
                  <input type="radio" checked={!approved} onChange={() => setApproved(false)} /> 驳回
                </label>
              </div>
              <input value={note} onChange={(e) => setNote(e.target.value)} placeholder="备注（驳回时必填）" />
              <button onClick={submitReview}>提交</button>
            </>
          )}
        </section>
      )}

      {tab === "handoff" && (
        <section className="tab-panel">
          {handoffRows.length === 0 && <p className="muted">暂无转接待办；可手动输入会话 ID。</p>}
          {handoffRows.length > 0 ? (
            <label>
              待恢复会话
              <select value={selected} onChange={(e) => setSelected(e.target.value)}>
                {handoffRows.map((row) => (
                  <option key={row.thread_id} value={row.thread_id}>
                    {row.thread_id} · {row.reason === "turn_limit" ? "轮次上限" : "投诉"}
                  </option>
                ))}
              </select>
            </label>
          ) : (
            <input value={manualThread} onChange={(e) => setManualThread(e.target.value)} placeholder="会话 ID" />
          )}
          <div className="row">
            <label>
              <input type="radio" checked={approved} onChange={() => setApproved(true)} /> 通过
            </label>
            <label>
              <input type="radio" checked={!approved} onChange={() => setApproved(false)} /> 驳回
            </label>
          </div>
          <input value={note} onChange={(e) => setNote(e.target.value)} placeholder="备注" />
          <button onClick={submitResume}>恢复会话</button>
        </section>
      )}

      {tab === "audit" && (
        <section className="tab-panel">
          {auditRows.length === 0 && <p className="muted">暂无审计记录。</p>}
          {auditRows.length > 0 && (
            <table>
              <thead>
                <tr>
                  <th>时间</th>
                  <th>操作者</th>
                  <th>动作</th>
                  <th>资源</th>
                  <th>结果</th>
                </tr>
              </thead>
              <tbody>
                {auditRows.map((row, index) => (
                  <tr key={index}>
                    <td>{row.ts || ""}</td>
                    <td>{row.actor || ""}</td>
                    <td>{row.action || ""}</td>
                    <td>{row.resourceId || ""}</td>
                    <td>{row.result || ""}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </section>
      )}
    </main>
  );
}

export default function App() {
  const [user, setUser] = useState<api.User | null>(() => {
    const raw = localStorage.getItem("cs_user");
    return raw ? (JSON.parse(raw) as api.User) : null;
  });
  const [toastText, setToastText] = useState("");

  const toast = useCallback((text: string) => {
    setToastText(text);
    window.setTimeout(() => setToastText(""), 2200);
  }, []);

  function handleLogin(next: api.User) {
    localStorage.setItem("cs_user", JSON.stringify(next));
    setUser(next);
  }

  function logout() {
    localStorage.removeItem("cs_user");
    setUser(null);
  }

  return (
    <div className="shell">
      <header className="topbar">
        <div className="who">
          {user ? (
            <>
              <strong>{user.displayName || user.username}</strong> · {roleLabel(user.role)}
            </>
          ) : (
            ""
          )}
        </div>
        {user && (
          <button className="ghost" onClick={logout}>
            退出
          </button>
        )}
      </header>
      {!user && <Login onLogin={handleLogin} />}
      {user && roleLabel(user.role) === "坐席" && <AgentWorkbench user={user} toast={toast} />}
      {user && roleLabel(user.role) !== "坐席" && (
        <BuyerChat user={user} onLogout={logout} toast={toast} />
      )}
      <Toast text={toastText} />
    </div>
  );
}
