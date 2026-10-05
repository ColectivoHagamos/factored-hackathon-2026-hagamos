import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { FileText, MessageSquareText, Search, TriangleAlert } from "lucide-react";
import { IconBox, STROKE } from "@/components/vera/ui";
import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "@/api/client";
import type { Me, Movement } from "@/api/types";
import { Leaves, SiteHeader, VAvatar } from "@/components/vera/brand";
import { ErrorNote, Loading, useRequire } from "@/components/vera/common";
import { dateLong, money, timeShort } from "@/lib/format";
import { disputeMessage } from "@/lib/dispute";
import { useT } from "@/i18n/useT";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/banca")({
  head: () => ({
    meta: [
      { title: "Mi banca · LATAM Bank" },
      { name: "description", content: "Tarjetas y movimientos del cliente de demostración." },
      { property: "og:title", content: "Mi banca · LATAM Bank" },
      { property: "og:description", content: "Tarjetas y movimientos del cliente de demostración." },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary" },
    ],
  }),
  component: Banca,
});

const STATUS_STYLE: Record<Movement["status"], string> = {
  approved: "",
  pending: "text-warning",
  declined: "text-danger",
  reversed: "text-muted-foreground",
};

function Banca() {
  const ready = useRequire("customer");
  const { t, locale } = useT();
  const navigate = useNavigate();
  const [me, setMe] = useState<Me | null>(null);
  const [movs, setMovs] = useState<Movement[] | null>(null);
  const [err, setErr] = useState<unknown>(null);
  const [q, setQ] = useState("");
  const [filter, setFilter] = useState<"all" | Movement["status"]>("all");

  const groups = useMemo(() => {
    const term = q.trim().toLowerCase();
    const map = new Map<string, Movement[]>();
    for (const m of movs ?? []) {
      if (filter !== "all" && m.status !== filter) continue;
      if (term && ![m.merchant, m.city, m.card, m.kind === "bank_adjustment" ? t("bank.adjustment") : ""].some((x) => x?.toLowerCase().includes(term))) continue;
      const d = new Date(m.occurred_at);
      const key = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
      map.set(key, [...(map.get(key) ?? []), m]);
    }
    return [...map.entries()].sort((a, b) => b[0].localeCompare(a[0]));
  }, [movs, q, filter, t]);

  function dayLabel(key: string) {
    const [y, mo, da] = key.split("-").map(Number);
    const d = new Date(y!, mo! - 1, da!);
    const today = new Date(); today.setHours(0, 0, 0, 0);
    const diff = Math.round((today.getTime() - d.getTime()) / 86400000);
    return diff === 0 ? t("bank.today") : diff === 1 ? t("bank.yesterday") : dateLong(d.toISOString(), locale);
  }

  const load = useCallback(() => {
    setErr(null);
    Promise.all([api.me(), api.movements()])
      .then(([m, mv]) => {
        setMe(m);
        setMovs(mv);
      })
      .catch(setErr);
  }, []);
  useEffect(() => {
    if (ready) load();
  }, [ready, load]);

  return (
    <div className="relative min-h-screen overflow-hidden">
      <Leaves className="absolute -right-32 -top-24 w-[440px] opacity-70" />
      <SiteHeader
        right={
          <Link to="/clientes" className="hidden rounded-full border border-primary-dark/20 px-4 py-2 text-sm font-semibold text-primary-dark hover:bg-primary-light sm:inline-flex">
            {t("bank.change")}
          </Link>
        }
      />
      <main className="relative z-10 mx-auto max-w-6xl px-5 pb-28 pt-4 sm:px-8">
        {err ? <ErrorNote error={err} onRetry={load} /> : null}
        {!me || !movs ? (
          !err && <Loading />
        ) : (
          <>
            <div className="flex flex-wrap items-end justify-between gap-6">
              <div>
                <p className="text-sm font-medium text-muted-foreground">{me.alias.split(" · ")[0]} · {t(`country.${me.country}`)}</p>
                <h1 className="mt-1 text-3xl font-extrabold text-primary-dark sm:text-4xl">{t("bank.hello", { name: me.first_name })}</h1>
                <p className="mt-2 max-w-xl text-muted-foreground">{t("bank.sub")}</p>
              </div>
              <Link to="/chat" className="inline-flex items-center gap-3 rounded-full bg-primary-dark py-2 pl-2 pr-6 text-sm font-semibold text-primary-foreground shadow-soft transition-transform hover:-translate-y-0.5">
                <span className="grid size-9 place-items-center rounded-[12px] bg-primary-foreground/15"><MessageSquareText className="size-5" strokeWidth={STROKE} /></span>
                {t("bank.talk")}
              </Link>
            </div>

            <section className="mt-10" aria-labelledby="cards-h">
              <h2 id="cards-h" className="text-lg font-bold text-foreground">{t("bank.cards")}</h2>
              <ul className="-mx-5 mt-4 flex snap-x scroll-px-5 gap-4 overflow-x-auto px-5 pb-2 sm:mx-0 sm:grid sm:grid-cols-2 sm:overflow-visible sm:px-0 lg:grid-cols-3">
                {me.cards.map((c) => {
                  const on = c.status === "active";
                  return (
                    <li key={c.masked} className="w-[82%] shrink-0 snap-start sm:w-auto">
                      <div className={cn("relative flex aspect-[1.586] flex-col overflow-hidden rounded-[22px] p-5 shadow-soft", on ? "bg-primary-dark text-primary-foreground" : "bg-muted text-muted-foreground")}>
                        <Leaves className={cn("absolute -bottom-24 -right-20 w-64", on ? "opacity-25" : "opacity-40 grayscale")} />
                        <div className="relative flex items-start justify-between">
                          <span className="text-sm font-semibold">LATAM Bank</span>
                          {!on && <span className="text-xs font-semibold text-foreground">{t("bank.blocked")}</span>}
                        </div>
                        <span aria-hidden className={cn("relative mt-4 h-7 w-10 rounded-md", on ? "bg-primary-foreground/25" : "bg-border")} />
                        <div className="relative mt-auto">
                          <p className="text-lg font-semibold tabular-nums tracking-[0.2em]">{c.masked}</p>
                          <p className="mt-1 flex justify-between text-xs opacity-80">
                            <span>{t(c.type === "credit" ? "bank.credit" : "bank.debit")}</span>
                            {!on && <span>{t("bank.blockedNote")}</span>}
                          </p>
                        </div>
                      </div>
                    </li>
                  );
                })}
              </ul>
            </section>

            <section className="mt-12" aria-labelledby="mov-h">
              <div className="flex items-baseline justify-between">
                <h2 id="mov-h" className="text-lg font-bold text-foreground">{t("bank.movements")}</h2>
                <span className="text-sm text-muted-foreground">{t("bank.range")}</span>
              </div>
              <div className="mt-4 flex flex-wrap items-center gap-2">
                <span className="text-sm font-medium text-muted-foreground">{t("bank.shortcuts")}</span>
                <Link to="/chat" search={{ intent: "improper_charge" }} className="inline-flex items-center gap-1.5 rounded-full border bg-surface px-3.5 py-2 text-xs font-semibold text-primary-dark hover:bg-primary-light">
                  <FileText className="size-4" strokeWidth={STROKE} aria-hidden /> {t("bank.sc.improper")}
                </Link>
                <Link to="/chat" search={{ intent: "lost_card" }} className="inline-flex items-center gap-1.5 rounded-full border bg-surface px-3.5 py-2 text-xs font-semibold text-primary-dark hover:bg-primary-light">
                  <TriangleAlert className="size-4" strokeWidth={STROKE} aria-hidden /> {t("bank.sc.lost")}
                </Link>
              </div>
              <div className="mt-4 flex flex-col gap-3 sm:flex-row sm:items-center">
                <label className="vera-field flex h-11 min-w-0 flex-1 items-center gap-2 px-4">
                  <Search className="size-4 shrink-0 text-muted-foreground" strokeWidth={STROKE} aria-hidden />
                  <span className="sr-only">{t("bank.search")}</span>
                  <input type="search" value={q} onChange={(e) => setQ(e.target.value)} placeholder={t("bank.search")} className="min-w-0 flex-1 bg-transparent text-sm outline-none placeholder:text-muted-foreground" />
                </label>
                <div role="group" aria-label={t("bank.filterLabel")} className="flex gap-2 overflow-x-auto">
                  {(["all", "approved", "pending", "declined", "reversed"] as const).map((k) => (
                    <button key={k} type="button" aria-pressed={filter === k} onClick={() => setFilter(k)} className={cn("shrink-0 rounded-full px-3.5 py-2 text-xs font-semibold transition-colors", filter === k ? "bg-primary-dark text-primary-foreground" : "border bg-surface text-muted-foreground hover:text-foreground")}>
                      {k === "all" ? t("bank.all") : t(`status.${k}`)}
                    </button>
                  ))}
                </div>
              </div>
              {movs.length === 0 ? (
                <p className="mt-6 text-muted-foreground">{t("bank.empty")}</p>
              ) : groups.length === 0 ? (
                <p className="mt-6 text-muted-foreground">{t("bank.noResults")}</p>
              ) : (
                <div className="card-soft mt-6 overflow-hidden">
                  {groups.map(([day, items]) => (
                    <section key={day} aria-label={dayLabel(day)}>
                      <h3 className="border-b bg-muted/50 px-4 py-2 text-xs font-semibold text-muted-foreground sm:px-5">{dayLabel(day)}</h3>
                      <ul className="divide-y border-b last:border-b-0">
                        {items.map((m, i) => {
                          const adj = m.kind === "bank_adjustment";
                          return (
                            <li key={i} className="grid grid-cols-[auto_minmax(0,1fr)_auto] items-center gap-x-4 gap-y-1 px-4 py-3.5 sm:px-5">
                              {adj ? <IconBox icon={FileText} /> : <IconBox><span className="text-sm font-semibold">{(m.merchant ?? "?").charAt(0).toUpperCase()}</span></IconBox>}
                              <div className="min-w-0">
                                <p className="truncate text-sm font-semibold">{adj ? t("bank.adjustment") : m.merchant}</p>
                                <p className="truncate text-xs text-muted-foreground">
                                  {timeShort(m.occurred_at, locale)}
                                  {m.city ? ` · ${m.city}` : !adj && m.country ? ` · ${t("bank.online")} (${m.country})` : ""}
                                  {m.card ? ` · ${m.card}` : ""}
                                </p>
                              </div>
                              <div className="text-right">
                                <p className="text-sm font-bold tabular-nums">{money(m.amount, m.currency)}</p>
                                {m.status !== "approved" && <p className={cn("mt-0.5 text-[11px] font-semibold", STATUS_STYLE[m.status])}>{t(`status.${m.status}`)}</p>}
                              </div>
                              {!adj && (
                                <button
                                  type="button"
                                  onClick={() => navigate({ to: "/chat", search: { msg: disputeMessage(m, me.language), intent: m.kind === "bank_adjustment" ? "improper_charge" : "unrecognized_charge" } })}
                                  className="col-start-2 col-end-4 justify-self-end text-xs font-semibold text-primary underline-offset-2 hover:underline"
                                >
                                  {t("bank.dispute")}
                                </button>
                              )}
                            </li>
                          );
                        })}
                      </ul>
                    </section>
                  ))}
                </div>
              )}
            </section>
          </>
        )}
      </main>
      {ready && me && (
        <Link to="/chat" aria-label={t("bank.talk")} className="fixed bottom-5 right-5 z-30 flex items-center gap-2 rounded-full bg-surface py-2 pl-2 pr-4 text-sm font-semibold text-primary-dark shadow-lift sm:hidden">
          <VAvatar size="sm" /> {t("bank.talk")}
        </Link>
      )}
    </div>
  );
}
