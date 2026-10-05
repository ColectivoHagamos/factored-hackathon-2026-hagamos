"use strict";

// The customer session by default; the access of the jury and the team for the demo customers.
const api = (path, options = {}, token = state.token) =>
  fetch(`/v1${path}`, {
    ...options,
    headers: { "Content-Type": "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}) },
  }).then(async (response) => {
    const body = await response.json();
    if (!response.ok) throw Object.assign(new Error(body.message || response.statusText), { status: response.status });
    return body;
  });

const stored = (key) => {
  try {
    return sessionStorage.getItem(key);
  } catch {
    return null;
  }
};
const state = { token: null, access: stored("vera.access"), conversation: null, busy: false, customers: [] };
const $ = (id) => document.getElementById(id);

function bubble(text, who) {
  const div = document.createElement("div");
  div.className = `bubble ${who}`;
  div.textContent = text;
  $("chat").appendChild(div);
  $("chat").scrollTop = $("chat").scrollHeight;
  return div;
}

function setBusy(busy) {
  state.busy = busy;
  $("message").disabled = busy || !state.conversation;
  $("send").disabled = busy || !state.conversation;
}

function showOptions(container, options, multiple) {
  if (!options.length) return;
  const box = document.createElement("div");
  box.className = "options";
  const choices = options.filter((option) => !option.answer);
  // Several charges in a sweep are answered at once: checkboxes and one button.
  if (multiple) {
    for (const option of choices) {
      const label = document.createElement("label");
      label.innerHTML = `<input type="checkbox" value="${option.n}"> `;
      label.append(`${option.n}. ${option.label}`);
      box.appendChild(label);
    }
    const send = document.createElement("button");
    send.textContent = "Enviar selección";
    send.onclick = () => {
      const picked = [...box.querySelectorAll("input:checked")].map((input) => input.value);
      box.remove();
      sendMessage(picked.length ? { text: picked.join(" y ") } : { text: "todos" }, picked.join(", ") || "todos");
    };
    box.appendChild(send);
  } else {
    for (const option of options) {
      const button = document.createElement("button");
      button.type = "button";
      button.textContent = option.answer ? option.label : `${option.n}. ${option.label}`;
      button.onclick = () => {
        box.remove();
        sendMessage({ selected_option: option.answer || option.n }, button.textContent);
      };
      box.appendChild(button);
    }
  }
  container.appendChild(box);
}

function showGlass(entries) {
  for (const entry of entries) {
    const li = document.createElement("li");
    li.innerHTML = `<span class="rule"></span> · <span class="source"></span><span class="deadline"></span>`;
    li.querySelector(".rule").textContent = entry.rule_id;
    li.querySelector(".source").textContent = entry.source;
    li.querySelector(".deadline").textContent = entry.deadline ? ` · fecha límite ${entry.deadline}` : "";
    $("rules").appendChild(li);
  }
}

async function sendMessage(body, shown) {
  if (state.busy) return;
  bubble(shown, "customer");
  setBusy(true);
  // A language model takes a second or two to read a message: the customer sees that VERA is on it.
  const typing = bubble("VERA está escribiendo…", "vera");
  typing.classList.add("typing");
  try {
    const reply = await api(`/conversations/${state.conversation}/messages`, { method: "POST", body: JSON.stringify(body) });
    typing.remove();
    // Only the latest question can be answered; older buttons would answer a step that already passed.
    document.querySelectorAll("#chat .options").forEach((box) => box.remove());
    const div = bubble(reply.reply, "vera");
    if (reply.pending_confirmation) {
      const pending = document.createElement("div");
      pending.className = "pending";
      pending.textContent = "Acción pendiente de su confirmación; nada se hace sin ella.";
      div.appendChild(pending);
    }
    showOptions(div, reply.options, reply.multiple_choice);
    showGlass(reply.glass_box);
    const caseId = (reply.reply.match(/DSP-\d{6}/) || [])[0];
    if (caseId) {
      $("case").innerHTML = `<p class="note">Caso <strong>${caseId}</strong> registrado. Si pasa a un analista, el detalle queda en la <a href="console.html?case=${caseId}">consola del analista</a>.</p>`;
    }
  } catch (error) {
    typing.remove();
    bubble(`No se pudo enviar: ${error.message}`, "vera").classList.add("error");
  } finally {
    setBusy(false);
    $("message").focus();
  }
}

async function start() {
  $("chat").innerHTML = "";
  $("rules").innerHTML = "";
  $("case").innerHTML = "";
  try {
    const body = JSON.stringify({ demo_customer: $("customer").value });
    const session = await api("/demo-session", { method: "POST", body }, state.access);
    state.token = session.token;
    const language = $("language").value;
    const conversation = await api("/conversations", {
      method: "POST",
      body: JSON.stringify(language ? { preferred_language: language } : {}),
    });
    state.conversation = conversation.conversation_id;
    showOptions(bubble(conversation.greeting, "vera"), conversation.options || [], false);
    setBusy(false);
  } catch (error) {
    if (error.status === 401) return askForAccess();
    bubble(`No se pudo empezar: ${error.message}`, "vera").classList.add("error");
  }
}

function askForAccess() {
  $("login").hidden = false;
  $("setup").hidden = true;
  $("username").focus();
}

async function logIn(event) {
  event.preventDefault();
  try {
    const body = JSON.stringify({ username: $("username").value.trim(), password: $("password").value });
    const access = await api("/auth/login", { method: "POST", body }, null);
    state.access = access.token;
    try {
      sessionStorage.setItem("vera.access", access.token);
    } catch {
      // Without storage the access lasts until the page is reloaded.
    }
    $("password").value = "";
    $("login-error").hidden = true;
    $("login").hidden = true;
    $("setup").hidden = false;
    await loadCustomers();
  } catch {
    $("login-error").hidden = false;
  }
}

async function loadCustomers() {
  let customers;
  try {
    customers = await api("/demo-customers", {}, state.access);
  } catch (error) {
    if (error.status === 401) return askForAccess();
    throw error;
  }
  state.customers = customers;
  $("customer").innerHTML = "";
  for (const customer of customers) {
    const option = document.createElement("option");
    option.value = customer.customer_ref;
    const scenarios = customer.scenarios.map((tag) => tag.split("_")[0]).filter((tag) => /^A\d+$/.test(tag));
    const tags = scenarios.length ? ` · ${[...new Set(scenarios)].join(", ")}` : "";
    option.textContent = `${customer.display_name} · ${customer.alias}${tags}`;
    $("customer").appendChild(option);
  }
  matchLanguage();
}

// A customer of the Portuguese scenario starts in Portuguese; the select still lets the tester choose.
function matchLanguage() {
  const customer = state.customers.find((c) => c.customer_ref === $("customer").value);
  if (customer) $("language").value = customer.language === "pt" ? "pt" : "";
}

$("start").onclick = start;
$("customer").onchange = matchLanguage;
$("login-form").onsubmit = logIn;
$("composer").onsubmit = (event) => {
  event.preventDefault();
  const text = $("message").value.trim();
  if (!text) return;
  $("message").value = "";
  sendMessage({ text }, text);
};
loadCustomers();
