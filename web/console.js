"use strict";

const $ = (id) => document.getElementById(id);
let token = null;

// The access of the jury and the team, from the login of the chat page, when the deployment requires one.
function access() {
  try {
    return sessionStorage.getItem("vera.access");
  } catch {
    return null;
  }
}

async function analystToken() {
  if (!token) {
    const headers = access() ? { Authorization: `Bearer ${access()}` } : {};
    const response = await fetch("/v1/demo-analyst-session", { method: "POST", headers });
    if (response.status === 401) throw new Error("Inicie sesión en la página del chat para abrir la consola.");
    token = (await response.json()).token;
  }
  return token;
}

function el(tag, text, className) {
  const node = document.createElement(tag);
  if (text !== undefined && text !== null) node.textContent = String(text);
  if (className) node.className = className;
  return node;
}

function section(title, ...children) {
  const card = el("section", null, "card spaced");
  card.appendChild(el("h2", title));
  children.forEach((child) => card.appendChild(child));
  return card;
}

function pairs(entries) {
  const list = el("dl", null, "kv");
  for (const [key, value] of entries) {
    list.appendChild(el("dt", key));
    list.appendChild(el("dd", value ?? "—"));
  }
  return list;
}

function table(headers, rows) {
  const node = el("table");
  const head = node.createTHead().insertRow();
  headers.forEach((header) => head.appendChild(el("th", header)));
  const body = node.createTBody();
  rows.forEach((row) => {
    const tr = body.insertRow();
    row.forEach((cell) => tr.appendChild(el("td", cell ?? "—")));
  });
  return node;
}

function tags(values, className) {
  const box = el("div");
  (values.length ? values : ["none"]).forEach((value) => box.appendChild(el("span", value, `tag ${className || ""}`)));
  return box;
}

function render(h) {
  const target = $("handoff");
  target.innerHTML = "";
  target.appendChild(
    section(
      `Case ${h.case_id}`,
      pairs([
        ["Summary", h.summary],
        ["Queue", h.suggested_queue + (h.requires_pt_analyst ? " · Portuguese-speaking analyst" : "")],
        ["Customer", `${h.account_country} · ${h.segment} · ${h.variant}`],
        ["Claim", `${h.claim_type} · reason ${h.reason} · response level ${h.response_level}`],
        ["Fraud alert", h.fraud_alert ? "sent (POL-16)" : "no"],
        ["Goodwill candidate", h.goodwill_candidate.flagged ? `yes: ${h.goodwill_candidate.reason}` : "no"],
        ["Policy", `master policy v${h.policy_version}`],
      ]),
    ),
  );
  const facts = h.verified_facts;
  target.appendChild(
    section(
      "Verified facts (from tools only)",
      table(
        ["#", "When", "Merchant", "Place", "Amount", "Status", "Card"],
        facts.charges.map((c) => [c.n, c.occurred_at.replace("T", " "), c.merchant, [c.city, c.country].filter(Boolean).join(", "), `${c.currency} ${c.amount}`, c.status, c.card]),
      ),
      pairs([
        ["Total exposure", facts.total_exposure.map((m) => `${m.currency} ${m.amount}`).join(" + ") || "none"],
        ["USD equivalent (threshold only)", facts.total_exposure_usd],
        ["Fraud score band", facts.fraud_score_band],
      ]),
    ),
  );
  const declared = h.declared_by_customer;
  target.appendChild(
    section("Declared by the customer (not verified)", pairs([["Channel", declared.channel], ["Has the card", declared.has_card], ["Was in the country", declared.was_in_country]])),
  );
  const legal = h.legal_clock;
  target.appendChild(
    section(
      `Legal clock · ${legal.route} · ${legal.deadline_verified ? "deadline verified" : "no verified deadline"}`,
      table(["Rule", "Result", "Status", "Detail"], legal.rules_evaluated.map((r) => [r.id, r.result, r.status, r.detail || (r.in_force_from ? `law from ${r.in_force_from}` : "")])),
      table(["Party", "Obligation", "Due", "Unit"], legal.obligations.map((o) => [o.party, o.what, o.due || "no date", o.unit])),
      pairs([["Venues", legal.venues.join(" · ")]]),
    ),
  );
  if (h.network_clock) {
    const n = h.network_clock;
    target.appendChild(section("Network clock (contractual, analyst only)", pairs([["Network", n.network], ["Suggested code", n.suggested_code], ["Due", n.due], ["Level", n.level], ["Note", n.note]])));
  }
  target.appendChild(section("Risk signals", tags(h.risk_signals, "warn")));
  target.appendChild(section("Actions read back", table(["Action", "Result", "Read back"], h.actions.map((a) => [a.action, a.result, a.read_back ? "yes" : "no"]))));
  if (h.open_questions.length) target.appendChild(section("Open questions", tags(h.open_questions)));
}

function renderTransfer(t) {
  const target = $("handoff");
  target.innerHTML = "";
  target.appendChild(
    section(
      `Transfer ${t.transfer_id}`,
      pairs([
        ["Summary", t.summary],
        ["Reason", `${t.reason} · ${t.rules_applied.join(", ") || "no rule recorded"}`],
        ["Queue", t.suggested_queue + (t.requires_pt_analyst ? " · Portuguese-speaking analyst" : "")],
        ["Customer", `${t.account_country} · ${t.segment} · ${t.variant}`],
        ["Claim", t.claim_type || "not stated"],
        ["Case", t.case_id || "none registered"],
        ["Pending action, never run", t.pending_action_not_run || "none"],
        ["Fraud alert", t.fraud_alert ? "due (POL-16)" : "no"],
        ["Trace", t.trace_id],
        ["Policy", `master policy v${t.policy_version}`],
      ]),
    ),
  );
  target.appendChild(
    section(
      "Charges known (from tools only)",
      table(
        ["#", "When", "Merchant", "Place", "Amount", "Status", "Card", "Fraud score"],
        t.charges.map((c) => [c.n, c.occurred_at.replace("T", " "), c.merchant, [c.city, c.country].filter(Boolean).join(", "), `${c.currency} ${c.amount}`, c.status, c.card, c.fraud_score_band]),
      ),
    ),
  );
  const declared = t.declared_by_customer;
  target.appendChild(
    section(
      "Declared by the customer (not verified)",
      pairs([["Channel", declared.channel], ["Has the card", declared.has_card], ["Made the payment", declared.authorized_payment], ["When, in their words", declared.date_text], ["Contacted by", declared.contacted_by]]),
    ),
  );
  target.appendChild(section("Risk signals", tags(t.risk_signals, "warn")));
  target.appendChild(section("Actions read back", table(["Action", "Result", "Read back"], t.actions.map((a) => [a.action, a.result, a.read_back ? "yes" : "no"]))));
  if (t.open_questions.length) target.appendChild(section("Open questions", tags(t.open_questions)));
}

async function analystGet(path) {
  const response = await fetch(path, { headers: { Authorization: `Bearer ${await analystToken()}` } });
  if (!response.ok) throw new Error(response.status === 404 ? "Nothing with that id yet" : response.statusText);
  return response.json();
}

async function open(reference) {
  $("handoff").innerHTML = "";
  try {
    if (reference.startsWith("TRF-")) renderTransfer(await analystGet(`/v1/transfers/${encodeURIComponent(reference)}`));
    else render(await analystGet(`/v1/cases/${encodeURIComponent(reference)}/handoff`));
  } catch (error) {
    $("handoff").appendChild(el("p", error.message, "error"));
  }
}

async function loadQueue() {
  const target = $("queue");
  try {
    const items = await analystGet("/v1/queue");
    target.innerHTML = "";
    if (!items.length) {
      target.appendChild(el("p", "Nothing is waiting.", "note"));
      return;
    }
    const rows = items.map((item) => [item.created_at.replace("T", " ").slice(0, 16), item.reference, item.queue + (item.requires_pt_analyst ? " · PT" : ""), item.summary]);
    const node = table(["When", "Reference", "Queue", "Summary", ""], rows);
    node.querySelectorAll("tbody tr").forEach((tr, index) => {
      const button = el("button", "Open", "secondary");
      button.type = "button";
      button.onclick = () => {
        $("case").value = items[index].reference;
        open(items[index].reference);
      };
      tr.appendChild(el("td")).appendChild(button);
    });
    target.appendChild(node);
  } catch (error) {
    target.innerHTML = "";
    target.appendChild(el("p", error.message, "error"));
  }
}

$("lookup").onsubmit = (event) => {
  event.preventDefault();
  open($("case").value.trim().toUpperCase());
};
$("refresh").onclick = loadQueue;
loadQueue();

const fromUrl = new URLSearchParams(location.search).get("case");
if (fromUrl) {
  $("case").value = fromUrl;
  $("lookup").requestSubmit();
}
