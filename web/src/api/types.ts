export type Lang = "es" | "pt";
export type Country = "CO" | "MX" | "AR";

export type LoginRequest = { username: string; password: string };
export type LoginResponse = { token: string; expires_at: string; display_name: string; role: "tester" };

export type DemoCustomer = {
  customer_ref: string;
  display_name: string;
  first_name: string;
  alias: string;
  country: Country;
  segment: string;
  scenarios: string[];
  language: Lang;
};

export type SessionResponse = { token: string; expires_at: string };

export type Card = { masked: string; type: "credit" | "debit"; status: "active" | "blocked" };
export type Me = {
  display_name: string;
  first_name: string;
  alias: string;
  country: Country;
  segment: string;
  language: Lang;
  cards: Card[];
};

export type Movement = {
  occurred_at: string;
  kind: "purchase" | "bank_adjustment";
  merchant: string | null;
  city: string | null;
  country: string | null;
  amount: string;
  currency: "COP" | "ARS" | "USD";
  status: "approved" | "pending" | "declined" | "reversed";
  card: string | null;
};

export type OptionAnswer =
  | "yes" | "no" | "not_sure" | "unrecognized_charge" | "improper_charge"
  | "lost_card" | "scam_transfer" | "human_request";
export type Option = { n: number; label: string; answer?: OptionAnswer | null };
export type StartResponse = { conversation_id: string; greeting: string; options: Option[] };

/** The reasons a customer can press in the bank's app; sent with the text that names the charge. */
export type Intent = "unrecognized_charge" | "improper_charge" | "lost_card" | "scam_transfer" | "human_request";
export type MessageBody = { text: string; intent?: Intent } | { selected_option: number | OptionAnswer };

export type Stage = "received" | "analysis" | "verification" | "result" | "resolved";
export type PendingConfirmation = {
  action: "block_card" | "register_dispute";
  summary: string;
  expires_at: string;
};
export type GlassRule = { rule_id: string; source: string; deadline: string | null };
export type Charge = {
  merchant: string | null;
  city: string | null;
  amount: string;
  currency: string;
  occurred_at: string;
  status: string;
  card: string | null;
};
export type MessageResponse = {
  reply: string;
  options: Option[];
  multiple_choice: boolean;
  pending_confirmation: PendingConfirmation | null;
  glass_box: GlassRule[];
  stage: Stage;
  charge: Charge | null;
  case_id: string | null;
};

export type QueueItem = {
  kind: "case" | "transfer";
  reference: string;
  created_at: string;
  queue: "fraud" | "complaints";
  summary: string;
  requires_pt_analyst: boolean;
  trace_id: string;
};

export type Handoff = Record<string, unknown>;

export type ApiErrorCode =
  | "unauthorized" | "not_found" | "confirmation_expired" | "rate_limited" | "provider_unavailable" | "unknown";
