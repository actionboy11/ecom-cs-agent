const JAVA = (import.meta.env.VITE_JAVA_BASE as string) || "http://localhost:8080";
const AGENT = (import.meta.env.VITE_AGENT_BASE as string) || "http://localhost:8000";

export type User = {
  token: string;
  role: string;
  displayName: string;
  userId: number;
  username: string;
};

export type PendingAction = {
  type?: string;
  intent?: string;
  order_no?: string | null;
  reason?: string;
  label?: string;
};

export type ChatReply = {
  reply: string;
  intent?: string;
  order_no?: string | null;
  tool_result?: { tool?: string; error?: string; data?: Record<string, unknown> };
  policy_refs?: string[];
  chain?: string;
  latency_ms?: number;
  needs_human?: boolean;
  pending_actions?: PendingAction[];
  tool_trace?: { step?: number; tool?: string; args?: Record<string, unknown>; result?: string; error?: string }[];
  fallback_reason?: string | null;
  ui_action?: {
    type?: string;
    action?: string;
    order_no?: string | null;
    message?: string;
    fields?: string[];
  } | null;
  history_request?: {
    type?: string;
    page?: number;
    page_size?: number;
    created_from?: string | null;
    created_to?: string | null;
    total?: number | null;
    has_more?: boolean | null;
  } | null;
  candidates?: {
    orderNo?: string;
    item?: string;
    amount?: number;
    status?: string;
    createdAt?: string;
    deliveredAt?: string;
    score?: number;
    reasons?: string[];
  }[];
};

export type AfterSale = {
  requestNo: string;
  orderNo: string;
  type: string;
  status: string;
  reason?: string;
  createdAt?: string;
};

export type Handoff = {
  thread_id: string;
  user_id: number;
  reason?: string;
  turn_count?: number;
};

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

async function request<T>(
  base: string,
  path: string,
  options: { method?: string; body?: unknown; token?: string } = {},
): Promise<T> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (options.token) headers.Authorization = `Bearer ${options.token}`;
  const res = await fetch(base + path, {
    method: options.method || "GET",
    headers,
    body: options.body ? JSON.stringify(options.body) : undefined,
  });
  let data: unknown = null;
  try {
    data = await res.json();
  } catch {
    data = null;
  }
  if (!res.ok) {
    const payload = data as { message?: string; detail?: string } | null;
    throw new ApiError(payload?.message || payload?.detail || `HTTP ${res.status}`, res.status);
  }
  return data as T;
}

export function login(username: string, password: string): Promise<User> {
  return request<User>(JAVA, "/api/auth/login", {
    method: "POST",
    body: { username, password },
  });
}

export function history(token: string, thread: string): Promise<{ role: string; content: string }[]> {
  return request(AGENT, `/api/v1/threads/${encodeURIComponent(thread)}/messages`, { token });
}

export function chat(token: string, thread: string, message: string): Promise<ChatReply> {
  return request<ChatReply>(AGENT, "/api/v1/chat", {
    method: "POST",
    token,
    body: { thread_id: thread, message },
  });
}

export function myAfterSales(token: string): Promise<AfterSale[]> {
  return request<AfterSale[]>(JAVA, "/api/after-sales", { token });
}

export function pendingAfterSales(token: string): Promise<AfterSale[]> {
  return request<AfterSale[]>(JAVA, "/api/after-sales?status=PENDING", { token });
}

export function review(token: string, requestNo: string, approved: boolean, note: string) {
  return request(JAVA, `/api/after-sales/${encodeURIComponent(requestNo)}/review`, {
    method: "POST",
    token,
    body: { approved, note },
  });
}

export function confirmWrite(
  token: string,
  thread: string,
  approved: boolean,
  note = "",
): Promise<ChatReply> {
  return request<ChatReply>(AGENT, `/api/v1/threads/${encodeURIComponent(thread)}/confirm`, {
    method: "POST",
    token,
    body: { approved, note },
  });
}

export function handoffs(token: string): Promise<Handoff[]> {
  return request<Handoff[]>(AGENT, "/api/v1/handoffs", { token });
}

export function resume(token: string, thread: string, approved: boolean, note: string) {
  return request(AGENT, `/api/v1/threads/${encodeURIComponent(thread)}/resume`, {
    method: "POST",
    token,
    body: { approved, note },
  });
}

export type AuditRow = {
  ts?: string;
  actor?: string;
  action?: string;
  resourceId?: string;
  result?: string;
};

export function audit(token: string): Promise<AuditRow[]> {
  return request<AuditRow[]>(JAVA, "/api/audit?limit=20", { token });
}


export type OrderPage = {
  items: {
    orderNo: string;
    sku?: string;
    item: string;
    amount?: number;
    status: string;
    createdAt?: string;
    deliveredAt?: string | null;
    tags?: string | null;
  }[];
  total: number;
  page: number;
  pageSize: number;
  hasMore: boolean;
};

export function orderPage(
  token: string,
  params: {
    page?: number;
    page_size?: number;
    created_from?: string | null;
    created_to?: string | null;
    product?: string;
    status?: string;
  },
): Promise<OrderPage> {
  const query = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") query.set(key, String(value));
  });
  return request<OrderPage>(JAVA, `/api/orders/page?${query.toString()}`, { token });
}

export function updateAddress(
  token: string,
  orderNo: string,
  payload: { receiver: string; phone: string; address: string },
) {
  return request(JAVA, `/api/orders/${encodeURIComponent(orderNo)}/address`, {
    method: "POST",
    token,
    body: payload,
  });
}

export function createInvoice(
  token: string,
  orderNo: string,
  payload: { title: string; taxId: string; email?: string },
) {
  return request(JAVA, `/api/orders/${encodeURIComponent(orderNo)}/invoice`, {
    method: "POST",
    token,
    body: payload,
  });
}


export function createAfterSales(
  token: string,
  payload: { orderNo: string; type: "RETURN" | "EXCHANGE" | "REFUND"; reason: string },
) {
  return request(JAVA, "/api/after-sales", { method: "POST", token, body: payload });
}
