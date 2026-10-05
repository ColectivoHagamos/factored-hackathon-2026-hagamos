import { createFileRoute, Link } from "@tanstack/react-router";
import { ArrowLeft, ChartNoAxesColumn, ChevronDown, RefreshCw, X } from "lucide-react";
import { StageTag, STAGE, STROKE, type StageKey } from "@/components/vera/ui";
import { fixedText, translateSummary } from "@/lib/analyst-text";
import { useCallback, useEffect, useState, type ReactNode } from "react";
import { api } from "@/api/client";
import type { Handoff, QueueItem } from "@/api/types";
import { Leaves, SiteHeader } from "@/components/vera/brand";
import { ErrorNote, Loading, useRequire } from "@/components/vera/common";
import { dateLong, dateShort, money, timeShort } from "@/lib/format";
import { session } from "@/lib/session";
import { useT } from "@/i18n/useT";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/analista")({
  head: () => ({
    meta: [
      { title: "Consola del analista · VERA" },
      { name: "description", content: "Cola de casos y transferencias que VERA entrega para revisión humana." },
      { property: "og:title", content: "Consola del analista · VERA" },
      { property: "og:description", content: "Cola de casos y transferencias que VERA entrega para revisión humana." },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary" },
    ],
  }),
  component: Analista,
});

const SECTIONS = ["declared_by_customer", "actions", "legal_clock", "network_clock", "risk_signals", "open_questions"] as const;
const HEAD = ["summary", "claim_type", "reason", "verified_facts", "charges", "suggested_queue", "stage"];

function useLabels() {
  const { t, lang } = useT();
  const has = (k: string) => t(k) !== k;
  const human = (k: string) => k.replaceAll("_", " ");
  return {
    key: (k: string) => (has(`hk.${k}`) ? t(`hk.${k}`) : human(k)),
    val: (v: string) => fixedText(v, lang) ?? (has(`hv.${v}`) ? t(`hv.${v}`) : /^[a-z]+(_[a-z]+)+$/.test(v) ? human(v) : v),
  };
}

function Value({ v }: { v: unknown }) {
  const { locale } = useT();
  const L = useLabels();
  if (v === null || v === undefined || (Array.isArray(v) && v.length === 0)) return <span className="text-muted-foreground">—</span>;
  if (typeof v === "string") {
    if (/^\d{4}-\d{2}-\d{2}/.test(v)) return <>{dateLong(v, locale)}</>;
    return <>{L.val(v)}</>;
  }
  if (typeof v === "boolean") return <>{L.val(String(v))}</>;
  if (typeof v === "number") return <>{v}</>;
  if (Array.isArray(v)) {
    return (
      <ul className="space-y-2">
        {v.map((x, i) => (
          <li key={i} className={cn(typeof x === "object" && x !== null ? "rounded-xl border bg-background p-3" : "flex gap-2")}>
            {(typeof x !== "object" || x === null) && <span aria-hidden className="mt-2 size-1 shrink-0 rounded-full bg-primary-dark" />}
            <span className="min-w-0"><Value v={x} /></span>
          </li>
        ))}
      </ul>
    );
  }
  const o = v as Record<string, unknown>;
  if (typeof o.amount === "string" && typeof o.currency === "string") {
    const { amount, currency, ...rest } = o;
    return (
      <div>
        <p className="font-bold tabular-nums text-primary-dark">{money(amount as string, currency as string)}</p>
        {Object.keys(rest).length > 0 && <KV o={rest} />}
      </div>
    );
  }
  return <KV o={o} />;
}

function KV({ o }: { o: Record<string, unknown> }) {
  const L = useLabels();
  return (
    <dl className="grid gap-x-4 gap-y-1.5 text-sm sm:grid-cols-[minmax(9rem,auto)_1fr]">
      {Object.entries(o).map(([k, val]) => (
        <div key={k} className="contents">
          <dt className="text-muted-foreground">{L.key(k)}</dt>
          <dd className="min-w-0 break-words font-medium"><Value v={val} /></dd>
        </div>
      ))}
    </dl>
  );
}

function Id({ v }: { v: string }) {
  return <span title={v} className="block max-w-[11rem] truncate whitespace-nowrap font-semibold tabular-nums">{v}</span>;
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <details className="group border-t py-3">
      <summary className="flex cursor-pointer list-none items-center justify-between gap-3 py-1 [&::-webkit-details-marker]:hidden">
        <span className="eyebrow">{title}</span>
        <ChevronDown className="size-4 text-primary-dark transition-transform group-open:rotate-180" strokeWidth={STROKE} aria-hidden />
      </summary>
      <div className="mt-3 text-sm leading-relaxed text-foreground">{children}</div>
    </details>
  );
}

type Charge = Record<string, unknown> & { amount: string; currency: string };

function Detail({ d, kind }: { d: Record<string, unknown>; kind: QueueItem["kind"] }) {
  const { t, lang, locale } = useT();
  const L = useLabels();
  const vf = (d.verified_facts ?? {}) as Record<string, unknown>;
  const charges = ((vf.charges ?? d.charges ?? []) as Charge[]).slice().sort((a, b) => String(a.occurred_at).localeCompare(String(b.occurred_at)));
  const exposure = (vf.total_exposure ?? []) as { amount: string; currency: string }[];
  const usd = typeof vf.total_exposure_usd === "string" ? new Intl.NumberFormat("es-CO", { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(Number(vf.total_exposure_usd)) : null;
  const legal = (d.legal_clock ?? null) as { obligations?: { due?: string }[] } | null;
  const due = legal?.obligations?.find((o) => o.due)?.due;
  const stage = (typeof d.stage === "string" && d.stage in STAGE ? d.stage : "received") as StageKey;
  const queue = (d.suggested_queue as string) ?? "";
  const technical = Object.fromEntries(Object.entries(d).filter(([k]) => !HEAD.includes(k) && !(SECTIONS as readonly string[]).includes(k)));
  const vfRest = Object.fromEntries(Object.entries(vf).filter(([k]) => !["charges", "total_exposure", "total_exposure_usd"].includes(k)));
  Object.assign(technical, vfRest);

  return (
    <div className="mt-5">
      <div className="rounded-[18px] border bg-background p-5">
        <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
          <p className="font-bold text-foreground">
            {kind === "case" ? L.val(String(d.claim_type ?? "")) : L.val(String(d.reason ?? ""))}
          </p>
          <StageTag stage={stage} label={t(STAGE[stage].tagKey)} />
        </div>
        {typeof d.summary === "string" && <p className="mt-1 text-sm text-muted-foreground">{translateSummary(d.summary, lang)}</p>}
        <dl className="mt-4 grid gap-4 text-sm sm:grid-cols-3">
          {exposure.length > 0 && (
            <div>
              <dt className="text-xs text-muted-foreground">{t("hk.total_exposure")}</dt>
              <dd className="mt-0.5 text-lg font-bold tabular-nums text-primary-dark">{exposure.map((e) => money(e.amount, e.currency)).join(" + ")}</dd>
              {usd && exposure.some((e) => e.currency !== "USD") && <dd className="text-xs tabular-nums text-muted-foreground">≈ USD {usd}</dd>}
            </div>
          )}
          <div>
            <dt className="text-xs text-muted-foreground">{t("analyst.col.queue")}</dt>
            <dd className="mt-0.5 font-medium">{queue ? t(`analyst.queue.${queue}`) : "—"}</dd>
          </div>
          {due && (
            <div>
              <dt className="text-xs text-muted-foreground">{t("analyst.legalDue")}</dt>
              <dd className="mt-0.5 font-medium">{dateLong(due, locale)}</dd>
            </div>
          )}
        </dl>
      </div>

      {charges.length > 0 && (
        <div className="mt-5 overflow-x-auto">
          <table className="w-full min-w-[560px] text-left text-sm">
            <thead className="text-xs text-muted-foreground">
              <tr className="border-b">
                <th className="py-2 pr-3 font-medium">{t("hk.occurred_at")}</th>
                <th className="py-2 pr-3 font-medium">{t("hk.merchant")}</th>
                <th className="py-2 pr-3 font-medium">{t("analyst.place")}</th>
                <th className="py-2 pr-3 text-right font-medium">{t("hk.amount")}</th>
                <th className="py-2 pr-3 font-medium">{t("hk.status")}</th>
                <th className="py-2 pr-3 font-medium">{t("hk.card")}</th>
                <th className="py-2 font-medium">{t("hk.is_known_merchant")}</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {charges.map((c, i) => (
                <tr key={i}>
                  <td className="whitespace-nowrap py-2.5 pr-3">{dateShort(String(c.occurred_at), locale)}</td>
                  <td className="py-2.5 pr-3 font-medium">{String(c.merchant ?? "—")}<span className="block text-xs text-muted-foreground">{L.val(String(c.merchant_category ?? ""))}</span></td>
                  <td className="py-2.5 pr-3">{[c.city, c.country].filter(Boolean).join(", ")}</td>
                  <td className="whitespace-nowrap py-2.5 pr-3 text-right font-semibold tabular-nums">{money(c.amount, c.currency)}</td>
                  <td className="py-2.5 pr-3">{L.val(String(c.status ?? ""))}</td>
                  <td className="whitespace-nowrap py-2.5 pr-3 tabular-nums">{String(c.card ?? "—")}</td>
                  <td className="py-2.5">{L.val(String(c.is_known_merchant))}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <div className="mt-5">
        {SECTIONS.filter((k) => d[k] !== undefined).map((k) => (
          <Section key={k} title={L.key(k)}><Value v={d[k]} /></Section>
        ))}
        <Section title={t("sec.technical")}><KV o={technical} /></Section>
      </div>
    </div>
  );
}

function Analista() {
  const accessReady = useRequire("access");
  const { t, locale, lang } = useT();
  const [hasSession, setHasSession] = useState(false);
  const [queue, setQueue] = useState<QueueItem[] | null>(null);
  const [err, setErr] = useState<unknown>(null);
  const [entering, setEntering] = useState(false);
  const [sel, setSel] = useState<QueueItem | null>(null);
  const [detail, setDetail] = useState<Handoff | null>(null);
  const [detailErr, setDetailErr] = useState<unknown>(null);

  useEffect(() => {
    const t0 = session.getToken("analyst");
    if (accessReady && t0 && !t0.expired) setHasSession(true);
  }, [accessReady]);

  const loadQueue = useCallback(() => {
    setErr(null);
    setQueue(null);
    api.queue().then(setQueue).catch(setErr);
  }, []);
  useEffect(() => {
    if (hasSession) loadQueue();
  }, [hasSession, loadQueue]);

  async function enter() {
    setEntering(true);
    setErr(null);
    try {
      session.setToken("analyst", await api.analystSession());
      setHasSession(true);
    } catch (e) {
      setErr(e);
    } finally {
      setEntering(false);
    }
  }

  async function open(q: QueueItem) {
    setSel(q);
    setDetail(null);
    setDetailErr(null);
    try {
      setDetail(q.kind === "case" ? await api.caseHandoff(q.reference) : await api.transfer(q.reference));
    } catch (e) {
      setDetailErr(e);
    }
  }


  return (
    <div className="relative min-h-screen overflow-hidden">
      <Leaves className="absolute -right-32 -top-24 w-[420px] opacity-60" />
      <SiteHeader
        right={
          <Link to="/clientes" className="hidden items-center gap-2 rounded-full border border-primary-dark/20 px-4 py-2 text-sm font-semibold text-primary-dark hover:bg-primary-light sm:inline-flex">
            <ArrowLeft className="size-4" strokeWidth={STROKE} /> {t("analyst.back")}
          </Link>
        }
      />
      <main className="relative z-10 mx-auto max-w-7xl px-5 pb-20 pt-4 sm:px-8">
        <p className="eyebrow">{t("analyst.eyebrow")}</p>
        <h1 className="mt-3 text-3xl font-extrabold text-primary-dark sm:text-4xl">{t("analyst.title")}</h1>
        <p className="mt-2 text-muted-foreground">{t("analyst.sub")}</p>

        <div className="mt-6">{err ? <ErrorNote error={err} onRetry={hasSession ? loadQueue : enter} /> : null}</div>

        {!accessReady ? (
          <Loading />
        ) : !hasSession ? (
          <button type="button" onClick={enter} disabled={entering} className="mt-6 inline-flex items-center gap-2 rounded-full bg-primary-dark px-6 py-3 text-sm font-semibold text-primary-foreground disabled:opacity-60">
            <ChartNoAxesColumn className="size-4" strokeWidth={STROKE} /> {entering ? t("common.loading") : t("analyst.enter")}
          </button>
        ) : (
          <div className={cn("mt-6 grid gap-6", sel && "2xl:grid-cols-[minmax(0,1fr)_minmax(0,1.1fr)]")}>
            <section className="card-soft overflow-hidden" aria-labelledby="q-h">
              <div className="flex items-center justify-between border-b px-5 py-4">
                <h2 id="q-h" className="font-bold">{t("analyst.queue")}</h2>
                <button type="button" onClick={loadQueue} className="inline-flex items-center gap-1.5 text-xs font-semibold text-primary"><RefreshCw className="size-4" strokeWidth={STROKE} /> {t("analyst.refresh")}</button>
              </div>
              {!queue ? (
                !err && <Loading />
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-sm">
                    <thead className="bg-muted/60 text-xs text-muted-foreground">
                      <tr>
                        <th className="px-5 py-3 font-semibold">{t("analyst.col.kind")}</th>
                        <th className="px-3 py-3 font-semibold">{t("analyst.col.ref")}</th>
                        <th className="px-3 py-3 font-semibold">{t("analyst.col.time")}</th>
                        <th className="px-3 py-3 font-semibold">{t("analyst.col.queue")}</th>
                        <th className="px-3 py-3 font-semibold">{t("analyst.col.summary")}</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y">
                      {queue.map((q) => (
                        <tr key={q.reference} className={cn("cursor-pointer transition-colors hover:bg-primary-light/50", sel?.reference === q.reference && "bg-primary-light")} onClick={() => open(q)}>
                          <td className="px-5 py-3.5 font-medium">{t(`analyst.kind.${q.kind}`)}</td>
                          <td className="px-3 py-3.5">
                            <button type="button" onClick={(e) => { e.stopPropagation(); open(q); }} className="text-primary-dark"><Id v={q.reference} /></button>
                          </td>
                          <td className="whitespace-nowrap px-3 py-3.5 text-muted-foreground">{dateShort(q.created_at, locale)} · {timeShort(q.created_at, locale)}</td>
                          <td className="px-3 py-3.5">
                            <span className="font-medium text-foreground">{t(`analyst.queue.${q.queue}`)}</span>
                          </td>
                          <td className="px-3 py-3.5">
                            <p className="min-w-[12rem] break-words">{translateSummary(q.summary, lang)}</p>
                            {q.requires_pt_analyst && <span className="mt-1 block text-xs font-medium text-primary">{t("analyst.pt")}</span>}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </section>

            {sel && (
              <section className="card-soft bubble-in p-6" aria-labelledby="d-h">
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <p className="text-xs font-semibold text-muted-foreground">{t(`analyst.kind.${sel.kind}`)} · {t(`analyst.queue.${sel.queue}`)}</p>
                    <h2 id="d-h" className="text-xl font-bold tabular-nums text-primary-dark">{sel.reference}</h2>
                  </div>
                  <button type="button" onClick={() => setSel(null)} aria-label={t("chat.close")} className="grid size-9 place-items-center rounded-[12px] border border-primary-dark/8 bg-surface/70"><X className="size-4" strokeWidth={STROKE} /></button>
                </div>
                {detailErr ? <div className="mt-4"><ErrorNote error={detailErr} onRetry={() => open(sel)} /></div> : null}
                {!detail ? (
                  !detailErr && <Loading />
                ) : (
                  <Detail d={detail} kind={sel.kind} />
                )}
              </section>
            )}
          </div>
        )}
      </main>
    </div>
  );
}
