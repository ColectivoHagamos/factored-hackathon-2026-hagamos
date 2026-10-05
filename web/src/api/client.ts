import { session, type TokenKind } from "@/lib/session";
import { ApiError } from "./errors";
import type {
  ApiErrorCode, DemoCustomer, Handoff, Lang, LoginRequest, LoginResponse, Me, MessageBody,
  MessageResponse, Movement, QueueItem, SessionResponse, StartResponse,
} from "./types";

export { ApiError };

function token(kind: TokenKind): string {
  const t = session.getToken(kind);
  if (!t || t.expired) throw new ApiError(401, "unauthorized", "Session expired");
  return t.token;
}

async function http<T>(method: "GET" | "POST", path: string, auth?: string, body?: unknown): Promise<T> {
  let res: Response;
  try {
    res = await fetch(path, {
      method,
      headers: {
        Accept: "application/json",
        ...(body !== undefined ? { "Content-Type": "application/json" } : {}),
        ...(auth ? { Authorization: `Bearer ${auth}` } : {}),
      },
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });
  } catch {
    throw new ApiError(503, "provider_unavailable", "Network error");
  }
  if (!res.ok) {
    let code: ApiErrorCode = "unknown";
    let message = res.statusText;
    try {
      const j = (await res.json()) as { code?: ApiErrorCode; message?: string };
      code = j.code ?? code;
      message = j.message ?? message;
    } catch { void 0; }
    if (res.status === 401) code = "unauthorized";
    if (res.status === 429) code = "rate_limited";
    throw new ApiError(res.status, code, message);
  }
  return (await res.json()) as T;
}

export const api = {
  login: (req: LoginRequest): Promise<LoginResponse> => http("POST", "/v1/auth/login", undefined, req),
  demoCustomers: (): Promise<DemoCustomer[]> => http("GET", "/v1/demo-customers", token("access")),
  demoSession: (ref: string): Promise<SessionResponse> =>
    http("POST", "/v1/demo-session", token("access"), { demo_customer: ref }),
  me: (): Promise<Me> => http("GET", "/v1/me", token("customer")),
  movements: (): Promise<Movement[]> => http("GET", "/v1/me/movements", token("customer")),
  startConversation: (preferred_language?: Lang): Promise<StartResponse> =>
    http("POST", "/v1/conversations", token("customer"), preferred_language ? { preferred_language } : {}),
  sendMessage: (id: string, body: MessageBody): Promise<MessageResponse> =>
    http("POST", `/v1/conversations/${encodeURIComponent(id)}/messages`, token("customer"), body),
  analystSession: (): Promise<SessionResponse> => http("POST", "/v1/demo-analyst-session", token("access")),
  queue: (): Promise<QueueItem[]> => http("GET", "/v1/queue", token("analyst")),
  caseHandoff: (id: string): Promise<Handoff> =>
    http("GET", `/v1/cases/${encodeURIComponent(id)}/handoff`, token("analyst")),
  transfer: (id: string): Promise<Handoff> => http("GET", `/v1/transfers/${encodeURIComponent(id)}`, token("analyst")),
};
