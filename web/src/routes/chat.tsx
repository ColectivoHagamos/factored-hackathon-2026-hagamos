import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import {
  CircleCheck, CircleQuestionMark, FileText, House, Plus, Search, Menu, SendHorizontal, User, X, Lightbulb,
} from "lucide-react";
import { IconBox, STAGES as STAGE_KEYS, STAGE, StageIcon, StageTag, STROKE } from "@/components/vera/ui";
import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";
import { api } from "@/api/client";
import type { Charge, DemoCustomer, GlassRule, MessageBody, Option, PendingConfirmation, Stage } from "@/api/types";
import { LangSwitch, Leaves, Logo, VAvatar } from "@/components/vera/brand";
import { ErrorNote, useRequire } from "@/components/vera/common";
import { dateLong, money, timeShort } from "@/lib/format";
import { humanMessage } from "@/lib/dispute";
import { session } from "@/lib/session";
import { useT } from "@/i18n/useT";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/chat")({
  validateSearch: (s: Record<string, unknown>): { msg?: string; intent?: "unrecognized_charge" | "improper_charge" | "lost_card" | "scam_transfer" } => ({
    ...(typeof s.msg === "string" && s.msg ? { msg: s.msg } : {}),
    ...(s.intent === "unrecognized_charge" || s.intent === "improper_charge" || s.intent === "lost_card" || s.intent === "scam_transfer"
      ? { intent: s.intent }
      : {}),
  }),
  head: () => ({
    meta: [
      { title: "Conversa con VERA · LATAM Bank" },
      { name: "description", content: "Resuelve tu disputa de tarjeta conversando con VERA." },
      { property: "og:title", content: "Conversa con VERA · LATAM Bank" },
      { property: "og:description", content: "Resuelve tu disputa de tarjeta conversando con VERA." },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary" },
    ],
  }),
  component: Chat,
});

type Msg = {
  id: number;
  role: "user" | "vera";
  text: string;
  at: Date;
  options?: Option[];
  multiple?: boolean;
  pending?: PendingConfirmation | null;
};

const STAGES = STAGE_KEYS.map((key) => ({ key: key as Stage }));
const YESNO = new Set(["yes", "no", "not_sure"]);

function Chat() {
  const ready = useRequire("customer");
  const { t, locale } = useT();
  const navigate = useNavigate();
  const { msg: initialMsg, intent } = Route.useSearch();
  const customer = session.getMeta<DemoCustomer>("customer");
  const custLang = customer?.language ?? "es";

  const [convId, setConvId] = useState<string | null>(null);
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<unknown>(null);
  const [stage, setStage] = useState<Stage>("received");
  const [charge, setCharge] = useState<Charge | null>(null);
  const [caseId, setCaseId] = useState<string | null>(null);
  const [glass, setGlass] = useState<GlassRule[]>([]);
  const [text, setText] = useState("");
  const [picked, setPicked] = useState<number[]>([]);
  const [panel, setPanel] = useState(false);
  const [help, setHelp] = useState(false);
  const [confirmNew, setConfirmNew] = useState(false);
  const started = useRef(false);
  const idRef = useRef(0);
  const endRef = useRef<HTMLDivElement>(null);

  const push = (m: Omit<Msg, "id" | "at">) => setMsgs((p) => [...p, { ...m, id: ++idRef.current, at: new Date() }]);

  const send = useCallback(
    async (body: MessageBody, display: string, cid = convId) => {
      if (!cid) return;
      push({ role: "user", text: display });
      setBusy(true);
      setErr(null);
      setPicked([]);
      try {
        const r = await api.sendMessage(cid, body);
        push({ role: "vera", text: r.reply, options: r.options, multiple: r.multiple_choice, pending: r.pending_confirmation });
        setStage(r.stage);
        if (r.charge) setCharge(r.charge);
        if (r.case_id) setCaseId(r.case_id);
        if (r.glass_box?.length) setGlass(r.glass_box);
      } catch (e) {
        setErr(e);
      } finally {
        setBusy(false);
      }
    },
    [convId],
  );

  const start = useCallback(async () => {
    setMsgs([]);
    setStage("received");
    setCharge(null);
    setCaseId(null);
    setGlass([]);
    setErr(null);
    setBusy(true);
    try {
      const r = await api.startConversation(custLang);
      setConvId(r.conversation_id);
      push({ role: "vera", text: r.greeting, options: r.options });
      setBusy(false);
      return r.conversation_id;
    } catch (e) {
      setErr(e);
      setBusy(false);
      return null;
    }
  }, [custLang]);

  useEffect(() => {
    if (!ready || started.current) return;
    started.current = true;
    start().then((cid) => {
      if (cid && initialMsg) {
        navigate({ to: "/chat", search: {}, replace: true });
        // A movement opens the chat with its text and the button the customer pressed: the button is the claim.
        send(intent ? { text: initialMsg, intent } : { text: initialMsg }, initialMsg, cid);
      } else if (cid && intent) {
        navigate({ to: "/chat", search: {}, replace: true });
        send({ selected_option: intent }, t(intent === "lost_card" ? "bank.sc.lost" : intent === "scam_transfer" ? "clients.any.scam" : "bank.sc.improper"), cid);
      }
    });
  }, [ready, start, send, initialMsg, intent, navigate, t]);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [msgs, busy]);

  const last = msgs[msgs.length - 1];
  const interactive = !busy && last?.role === "vera";

  function choose(o: Option) {
    send(o.answer ? { selected_option: o.answer } : { selected_option: o.n }, o.label);
  }
  function submit(e: FormEvent) {
    e.preventDefault();
    const v = text.trim();
    if (!v || busy) return;
    setText("");
    send({ text: v }, v);
  }

  const sidebarItem = "flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-[13px] font-medium text-muted-foreground transition-colors hover:bg-muted hover:text-foreground";

  const disputePanel = (
    <div className="space-y-4">
      <section className="rounded-[18px] border bg-surface p-5" aria-labelledby="disp-h">
        <h2 id="disp-h" className="text-sm font-bold text-foreground">{t("chat.dispute")}</h2>
        <ol className="mt-4">
          {STAGES.map(({ key }, i) => {
            const cur = STAGES.findIndex((s) => s.key === stage);
            const done = i < cur || (key === "resolved" && stage === "resolved");
            const active = i === cur;
            return (
              <li key={key} className="relative flex gap-3 pb-5 last:pb-0">
                {i < STAGES.length - 1 && <span aria-hidden className="absolute left-5 top-11 h-[calc(100%-2.75rem)] border-l border-dashed border-primary-dark/25" />}
                <StageIcon stage={key} reached={done || active} />
                <div aria-current={active ? "step" : undefined} className="min-w-0 pt-0.5">
                  <p className={cn("text-sm font-semibold", active || done ? "text-foreground" : "text-muted-foreground")}>{i + 1}. {t(`stage.${key}.t`)}</p>
                  <p className="text-xs text-muted-foreground">{t(`stage.${key}.d`)}</p>
                  {active && <div className="mt-1.5"><StageTag stage={key} label={t(STAGE[key].tagKey)} /></div>}
                </div>
              </li>
            );
          })}
        </ol>
      </section>

      {caseId && (
        <section className="bubble-in rounded-[20px] bg-primary-dark p-5 text-primary-foreground">
          <p className="text-xs font-medium opacity-75">{t("chat.case")}</p>
          <p className="mt-1 flex items-center gap-2 text-xl font-bold tracking-wide">
            <CircleCheck className="size-5 text-lime" strokeWidth={STROKE} aria-hidden /> {caseId}
          </p>
        </section>
      )}

      {charge && (
        <section className="bubble-in rounded-[18px] border bg-surface p-5" aria-labelledby="charge-h">
          <h2 id="charge-h" className="text-sm font-bold text-foreground">{t("chat.charge")}</h2>
          <p className="mt-3 text-2xl font-bold tabular-nums text-foreground">{money(charge.amount, charge.currency)}</p>
          <dl className="mt-3 grid grid-cols-[auto_1fr] gap-x-4 gap-y-1.5 text-sm">
            <dt className="text-xs text-muted-foreground">{t("chat.f.merchant")}</dt><dd className="font-medium">{charge.merchant ?? "—"}{charge.city ? ` · ${charge.city}` : ""}</dd>
            <dt className="text-xs text-muted-foreground">{t("chat.f.date")}</dt><dd className="font-medium">{dateLong(charge.occurred_at, locale)}</dd>
            {charge.card && <><dt className="text-xs text-muted-foreground">{t("chat.f.card")}</dt><dd className="font-medium tabular-nums">{charge.card}</dd></>}
          </dl>
        </section>
      )}

      {glass.length > 0 && (
        <section className="bubble-in rounded-[20px] border border-primary/20 bg-primary-light/60 p-5" aria-labelledby="why-h">
          <h2 id="why-h" className="flex items-center gap-2 text-sm font-bold text-primary-dark">
            <Lightbulb className="size-4" strokeWidth={STROKE} aria-hidden /> {t("chat.why")}
          </h2>
          <p className="text-xs text-muted-foreground">{t("chat.whySub")}</p>
          <ul className="mt-3 space-y-3">
            {glass.map((g) => (
              <li key={g.rule_id} className="rounded-xl bg-surface p-3 text-sm">
                <p className="font-semibold text-foreground">{g.source}</p>
                <p className="mt-1 text-xs text-muted-foreground">
                  <span className="font-semibold tabular-nums">{g.rule_id}</span> · {t("chat.deadline")}: {g.deadline ? dateLong(g.deadline, locale) : t("chat.noDeadline")}
                </p>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );

  return (
    <div className="relative h-dvh overflow-hidden bg-muted lg:p-8">
      <Leaves corner="bl" className="absolute -bottom-48 -left-48 hidden w-[620px] lg:block" />
      <Leaves className="absolute -right-48 -top-48 hidden w-[620px] opacity-70 lg:block" />
      <div className="relative mx-auto flex h-full max-w-[1400px] flex-col overflow-hidden bg-background lg:rounded-[28px] lg:shadow-soft">
      <header className="hidden items-center justify-between px-6 pb-3 pt-5 lg:flex">
        <Link to="/" aria-label="VERA"><Logo className="h-7" /></Link>
        <div className="flex items-center gap-4">
          <LangSwitch />
          {customer && (
            <span className="flex items-center gap-2 text-sm font-medium">
              <span className="grid size-8 place-items-center rounded-[10px] bg-primary-light text-xs font-semibold text-primary-dark">{customer.first_name[0]}</span>
              {customer.display_name}
            </span>
          )}
        </div>
      </header>
      <div className="flex min-h-0 flex-1 lg:gap-4 lg:px-4 lg:pb-4">
      <aside className="hidden w-52 shrink-0 flex-col lg:flex">
        <button type="button" onClick={() => setConfirmNew(true)} className="mt-1 flex items-center gap-2 rounded-xl bg-primary-dark px-4 py-3 text-sm font-semibold text-primary-foreground">
          <Plus className="size-4" strokeWidth={STROKE} /> {t("chat.new")}
        </button>
        <nav className="mt-6 space-y-1">
          <Link to="/banca" className={sidebarItem}><House className="size-4" strokeWidth={STROKE} /> {t("chat.movements")}</Link>
          <button type="button" onClick={() => setPanel(true)} className={cn(sidebarItem, "xl:hidden")}><FileText className="size-4" strokeWidth={STROKE} /> {t("chat.disputes")}</button>
          <button type="button" aria-expanded={help} onClick={() => setHelp((h) => !h)} className={sidebarItem}><CircleQuestionMark className="size-4" strokeWidth={STROKE} /> {t("chat.help")}</button>
          {help && <p className="bubble-in rounded-xl bg-muted p-3 text-xs leading-relaxed text-muted-foreground">{t("chat.helpBody")}</p>}
        </nav>
      </aside>

      <main className="flex min-w-0 flex-1 flex-col bg-background lg:rounded-[20px] lg:border lg:bg-surface">
        <header className="flex items-center justify-between gap-3 bg-background px-4 pb-2 pt-4 lg:hidden">
          <Link to="/banca" aria-label={t("chat.movements")}><Logo className="h-6" /></Link>
          <div className="flex items-center gap-2">
            <LangSwitch />
            <button type="button" onClick={() => setPanel(true)} aria-label={t("chat.menu")} className="grid size-9 place-items-center rounded-full"><Menu className="size-5" strokeWidth={STROKE} /></button>
          </div>
        </header>
        <div className="hidden items-center justify-end px-6 pt-3 lg:flex xl:hidden">
          <button type="button" onClick={() => setPanel(true)} className="rounded-full bg-primary-light px-3.5 py-1.5 text-xs font-semibold text-primary-dark">{t("chat.showDispute")}</button>
        </div>

        <div className="flex-1 overflow-y-auto">
          <div className="mx-auto max-w-3xl space-y-5 px-4 py-4 sm:px-6 lg:py-6" role="log" aria-live="polite" aria-relevant="additions">
            {customer && (
              <div className="hidden pb-2 lg:block">
                <h1 className="text-xl font-bold text-foreground">{t("bank.hello", { name: customer.first_name })}</h1>
                <p className="mt-1 max-w-xs text-[13px] leading-relaxed text-muted-foreground">{t("chat.intro")}</p>
              </div>
            )}
            {msgs.length === 0 && busy && <p className="text-sm text-muted-foreground">{t("chat.starting")}</p>}
            {msgs.map((m) => {
              const isLast = m.id === last?.id;
              return m.role === "user" ? (
                <div key={m.id} className="bubble-in flex flex-col items-end">
                  <div className="flex max-w-[85%] items-end gap-2 sm:max-w-md">
                    <p className="min-w-0 whitespace-pre-line break-words rounded-[18px] rounded-br-md bg-primary-dark px-4 py-3 text-[13px] leading-relaxed shadow-soft text-primary-foreground">{m.text}</p>
                    <span className="hidden size-8 shrink-0 place-items-center rounded-[10px] border border-primary-dark/8 bg-surface/70 sm:grid" aria-label={t("chat.you")}><User className="size-4 text-primary-dark" strokeWidth={STROKE} /></span>
                  </div>
                  <time className="mt-1 text-[11px] text-muted-foreground sm:mr-10">{timeShort(m.at, locale)}</time>
                </div>
              ) : (
                <div key={m.id} className="bubble-in flex gap-3">
                  <VAvatar />
                  <div className="min-w-0 max-w-[90%] sm:max-w-lg">
                    <div className="rounded-[18px] rounded-tl-md border border-border/70 bg-background px-4 py-3 text-[13px] leading-relaxed text-foreground">
                      <p className="whitespace-pre-line break-words">{m.text}</p>

                      {m.pending && (
                        <div className="mt-4 rounded-xl border border-primary/30 bg-primary-light p-4">
                          <p className="text-sm font-bold text-primary-dark">{t(`chat.pending.${m.pending.action}`)}</p>
                          <p className="mt-1 text-sm text-foreground">{m.pending.summary}</p>
                          <p className="mt-2 text-xs text-muted-foreground">{t("chat.pending.expires", { time: timeShort(m.pending.expires_at, locale) })}</p>
                          {isLast && interactive && (
                            <div className="mt-3 flex gap-2">
                              <button type="button" onClick={() => send({ selected_option: "yes" }, t("chat.yes"))} className="rounded-full bg-primary-dark px-5 py-2 text-sm font-semibold text-primary-foreground">{t("chat.yes")}</button>
                              <button type="button" onClick={() => send({ selected_option: "no" }, t("chat.no"))} className="rounded-full border border-primary-dark/30 px-5 py-2 text-sm font-semibold text-primary-dark">{t("chat.no")}</button>
                            </div>
                          )}
                        </div>
                      )}

                      {!m.pending && m.options && m.options.length > 0 && isLast && interactive && (
                        m.multiple ? (
                          <fieldset className="mt-4 space-y-2">
                            {m.options.map((o) => (
                              <label key={o.n} className={cn("flex cursor-pointer items-center gap-3 rounded-xl border px-3 py-2.5 transition-colors", picked.includes(o.n) ? "border-primary bg-primary-light" : "bg-background hover:bg-muted")}>
                                <input type="checkbox" className="size-4 accent-[var(--primary)]" checked={picked.includes(o.n)} onChange={() => setPicked((p) => (p.includes(o.n) ? p.filter((x) => x !== o.n) : [...p, o.n]))} />
                                <span className="grid size-6 shrink-0 place-items-center rounded-lg bg-primary-light text-xs font-bold text-primary-dark">{o.n}</span>
                                <span className="text-sm">{o.label}</span>
                              </label>
                            ))}
                            <div className="flex flex-wrap gap-2 pt-1">
                              <button type="button" disabled={!picked.length} onClick={() => { const v = [...picked].sort((a, b) => a - b).join(", "); send({ text: v }, v); }} className="rounded-full bg-primary-dark px-4 py-2 text-sm font-semibold text-primary-foreground disabled:opacity-50">{t("chat.confirmSel")}</button>
                              <button type="button" onClick={() => send({ text: "todos" }, t("chat.allOk"))} className="rounded-full border border-primary-dark/30 px-4 py-2 text-sm font-semibold text-primary-dark">{t("chat.allOk")}</button>
                            </div>
                          </fieldset>
                        ) : m.options.every((o) => o.answer && YESNO.has(o.answer)) ? (
                          <div className="mt-4 flex flex-wrap gap-2">
                            {m.options.map((o) => (
                              <button key={o.n} type="button" onClick={() => choose(o)} className={cn("rounded-full px-5 py-2 text-sm font-semibold", o.answer === "yes" ? "bg-primary-dark text-primary-foreground" : "border border-primary-dark/30 text-primary-dark hover:bg-primary-light")}>{o.label}</button>
                            ))}
                          </div>
                        ) : (
                          <ul className="mt-4 space-y-2">
                            {m.options.map((o) => (
                              <li key={o.n}>
                                <button type="button" onClick={() => choose(o)} className="flex w-full items-center gap-3 rounded-[10px] bg-muted/70 px-3 py-2.5 text-left text-[13px] transition-colors hover:bg-primary-light">
                                  <span className="grid size-6 shrink-0 place-items-center rounded-full bg-surface text-xs font-semibold text-foreground">{o.n}</span>
                                  {o.label}
                                </button>
                              </li>
                            ))}
                          </ul>
                        )
                      )}
                    </div>
                    <time className="mt-1 block text-[11px] text-muted-foreground">{timeShort(m.at, locale)}</time>
                  </div>
                </div>
              );
            })}

            {busy && msgs.length > 0 && (
              <div className="bubble-in flex gap-3" role="status">
                <VAvatar />
                <div className="w-full max-w-sm rounded-[18px] rounded-tl-md border border-border/70 bg-background px-4 py-3">
                  <p className="text-sm font-semibold text-foreground">{t("chat.reviewing")}</p>
                  <div className="mt-3 flex items-center gap-3 rounded-xl bg-background p-3">
                    <IconBox icon={Search} state="active" />
                    <div className="flex-1">
                      <p className="text-xs font-semibold text-primary">{t(stage === "result" || stage === "resolved" ? "chat.step3" : stage === "verification" ? "chat.step2" : "chat.step1")}</p>
                      <div className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-muted"><div className="progress-run h-full rounded-full bg-primary-dark" /></div>
                    </div>
                  </div>
                </div>
              </div>
            )}
            {err ? <ErrorNote error={err} onRetry={convId ? undefined : () => { void start(); }} /> : null}
            <div ref={endRef} />
          </div>
        </div>

        <div className="bg-transparent px-4 pb-4 pt-2 sm:px-6">
          <div className="mx-auto max-w-3xl">
            <div className="mb-2 flex justify-start">
              <button type="button" disabled={busy || !convId} onClick={() => send({ text: humanMessage(custLang) }, humanMessage(custLang))} className="inline-flex items-center gap-2 rounded-full border border-primary-dark/20 bg-surface px-3.5 py-1.5 text-xs font-semibold text-primary-dark hover:bg-primary-light disabled:opacity-50">
                <User className="size-4" strokeWidth={STROKE} /> {t("chat.human")}
              </button>
            </div>
            <form onSubmit={submit} className="flex items-center gap-2">
              <div className="flex min-w-0 flex-1 items-center gap-2 rounded-full border bg-background py-1.5 pl-5 pr-1.5 focus-within:border-transparent focus-within:ring-2 focus-within:ring-lime">
              <label htmlFor="chat-input" className="sr-only">{t("chat.placeholder")}</label>
              <input id="chat-input" value={text} onChange={(e) => setText(e.target.value)} placeholder={t("chat.placeholder")} className="min-w-0 flex-1 bg-transparent py-2 text-sm outline-none placeholder:text-muted-foreground focus-visible:rounded-none focus-visible:shadow-none focus-visible:outline-none" autoComplete="off" />
              <button type="submit" disabled={busy || !text.trim() || !convId} aria-label={t("chat.send")} className="grid size-10 shrink-0 place-items-center rounded-full bg-primary-dark text-primary-foreground transition-opacity disabled:opacity-40">
                <SendHorizontal className="size-4" strokeWidth={STROKE} />
              </button>
              </div>
            </form>
            <p className="mt-2 text-center text-[11px] text-muted-foreground">{t("chat.disclaimer")}</p>
          </div>
        </div>
      </main>

      <aside className="hidden w-72 min-w-72 max-w-72 shrink-0 overflow-y-auto xl:block">{disputePanel}</aside>
      </div>
      </div>

      {confirmNew && (
        <div className="fixed inset-0 z-50 grid place-items-center p-5" role="alertdialog" aria-modal="true" aria-labelledby="new-h">
          <button type="button" aria-label={t("chat.cancel")} className="absolute inset-0 bg-primary-dark/40" onClick={() => setConfirmNew(false)} />
          <div className="bubble-in relative w-full max-w-sm rounded-[22px] bg-surface p-6 shadow-lift">
            <p id="new-h" className="text-sm font-semibold text-foreground">{t("chat.newConfirm")}</p>
            <div className="mt-5 flex flex-wrap justify-end gap-2">
              <button type="button" autoFocus onClick={() => setConfirmNew(false)} className="rounded-full border px-4 py-2 text-sm font-semibold text-foreground">{t("chat.cancel")}</button>
              <button type="button" onClick={() => { setConfirmNew(false); start(); }} className="rounded-full bg-primary-dark px-4 py-2 text-sm font-semibold text-primary-foreground">{t("chat.newConfirmYes")}</button>
            </div>
          </div>
        </div>
      )}

      {panel && (
        <div className="fixed inset-0 z-40 xl:hidden" role="dialog" aria-modal="true" aria-label={t("chat.dispute")}>
          <button type="button" aria-label={t("chat.close")} className="absolute inset-0 bg-primary-dark/40" onClick={() => setPanel(false)} />
          <div className="bubble-in absolute inset-x-0 bottom-0 max-h-[85dvh] overflow-y-auto rounded-t-[28px] bg-background p-5 sm:inset-y-0 sm:left-auto sm:right-0 sm:max-h-none sm:w-96 sm:rounded-none">
            <div className="mb-3 flex justify-end">
              <button type="button" onClick={() => setPanel(false)} aria-label={t("chat.close")} className="grid size-9 place-items-center rounded-full bg-muted"><X className="size-4" /></button>
            </div>
            <nav className="mb-4 space-y-1 lg:hidden">
              <button type="button" onClick={() => { setPanel(false); setConfirmNew(true); }} className={sidebarItem}><Plus className="size-4" strokeWidth={STROKE} /> {t("chat.new")}</button>
              <Link to="/banca" className={sidebarItem}><House className="size-4" strokeWidth={STROKE} /> {t("chat.movements")}</Link>
            </nav>
            {disputePanel}
          </div>
        </div>
      )}
    </div>
  );
}
