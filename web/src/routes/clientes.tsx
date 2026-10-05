import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { ArrowRight, ChartNoAxesColumn, Search } from "lucide-react";
import { CLIENT_ICONS, IconBox, STROKE } from "@/components/vera/ui";
import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "@/api/client";
import type { DemoCustomer } from "@/api/types";
import { Leaves, SiteHeader } from "@/components/vera/brand";
import { ErrorNote, Loading, useRequire } from "@/components/vera/common";
import { session } from "@/lib/session";
import { useT } from "@/i18n/useT";
import { hasScenario, scenarioLabel, shortAlias, visibleScenarios } from "@/lib/scenarios";

export const Route = createFileRoute("/clientes")({
  head: () => ({
    meta: [
      { title: "Clientes de demostración · VERA" },
      { name: "description", content: "Elige un cliente ficticio para probar VERA." },
      { property: "og:title", content: "Clientes de demostración · VERA" },
      { property: "og:description", content: "Elige un cliente ficticio para probar VERA." },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary" },
    ],
  }),
  component: Clientes,
});

const REC: { tag: string; country?: string }[] = [{ tag: "A1", country: "CO" }, { tag: "A3" }, { tag: "A6" }, { tag: "A10" }];
const ANY = [
  { k: "human", body: { msg: "human" } },
  { k: "scam", body: { intent: "scam_transfer" } },
  { k: "inject", body: { msg: "inject" } },
] as const;

function Clientes() {
  const ready = useRequire("access");
  const { t } = useT();
  const navigate = useNavigate();
  const [list, setList] = useState<DemoCustomer[] | null>(null);
  const [err, setErr] = useState<unknown>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [q, setQ] = useState("");
  const [country, setCountry] = useState("");
  const [scenario, setScenario] = useState("");
  const countries = useMemo(() => [...new Set((list ?? []).map((c) => c.country))].sort(), [list]);
  const scenarios = useMemo(
    () => [...new Set((list ?? []).flatMap((c) => visibleScenarios(c.scenarios)))].sort((a, b) => scenarioLabel(t, a).localeCompare(scenarioLabel(t, b))),
    [list, t],
  );
  const recommended = useMemo(
    () => REC.flatMap((r) => {
      const c = list?.find((x) => hasScenario(x.scenarios, r.tag) && (!r.country || x.country === r.country));
      return c ? [{ c, tag: r.tag }] : [];
    }),
    [list],
  );
  const filtered = useMemo(() => {
    const n = q.trim().toLowerCase();
    return (list ?? []).filter((c) =>
      (!country || c.country === country) &&
      (!scenario || c.scenarios.includes(scenario)) &&
      (!n || [c.display_name, c.alias, c.country, t(`country.${c.country}`), ...c.scenarios.map((s) => scenarioLabel(t, s))].some((x) => x.toLowerCase().includes(n))),
    );
  }, [list, q, country, scenario, t]);

  const load = useCallback(() => {
    setErr(null);
    api.demoCustomers().then(setList).catch(setErr);
  }, []);
  useEffect(() => {
    if (ready) load();
  }, [ready, load]);

  async function choose(c: DemoCustomer, any?: (typeof ANY)[number]) {
    setBusy(any ? any.k : c.customer_ref);
    try {
      const s = await api.demoSession(c.customer_ref);
      session.setToken("customer", s);
      session.setMeta("customer", c);
      if (!any) navigate({ to: "/banca" });
      else if ("intent" in any.body) navigate({ to: "/chat", search: { intent: any.body.intent } });
      else navigate({ to: "/chat", search: { msg: t(`clients.any.${any.k}`) } });
    } catch (e) {
      setErr(e);
      setBusy(null);
    }
  }

  return (
    <div className="min-h-screen overflow-hidden">
      <SiteHeader
        right={
          <Link to="/analista" className="hidden items-center gap-2 rounded-full border border-primary-dark/20 px-4 py-2 text-sm font-semibold text-primary-dark hover:bg-primary-light sm:inline-flex">
            <ChartNoAxesColumn className="size-4" strokeWidth={STROKE} /> {t("clients.analyst")}
          </Link>
        }
      />
      <div className="relative isolate overflow-hidden bg-primary-dark text-primary-foreground">
        <Leaves className="absolute -right-40 -top-48 -z-10 w-[500px] opacity-40 sm:-right-20" />
        <div className="mx-auto max-w-6xl px-5 py-9 sm:px-8 sm:py-11">
          <p className="text-xs font-bold uppercase text-accent">{t("clients.eyebrow")}</p>
          <h1 className="mt-3 max-w-2xl text-3xl font-extrabold sm:text-4xl">{t("clients.title")}</h1>
          <p className="mt-3 max-w-2xl text-sm leading-relaxed text-primary-foreground/85 sm:text-base">{t("clients.sub")}</p>
          <p className="mt-4 text-xs font-medium text-primary-foreground/70">{t("clients.note")}</p>
        </div>
      </div>
      <main className="mx-auto max-w-6xl px-5 pb-20 pt-8 sm:px-8">
        {err ? <ErrorNote error={err} onRetry={load} /> : null}
        {!ready || (!list && !err) ? (
          <Loading />
        ) : (
          <>
            {recommended.length > 0 && (
              <section aria-labelledby="rec-h">
                <h2 id="rec-h" className="border-l-[3px] border-l-primary pl-3 text-lg font-bold text-primary-dark">{t("clients.rec.title")}</h2>
                <ul className="mt-4 grid gap-3 lg:grid-cols-2">
                  {recommended.map(({ c, tag }) => (
                    <li key={tag}>
                      <button type="button" onClick={() => choose(c)} disabled={!!busy} className="card-soft group flex h-full w-full items-center gap-3 border-l-[3px] border-l-primary p-4 text-left transition hover:-translate-y-0.5 hover:border-primary/60 hover:shadow-lift disabled:opacity-70">
                        <IconBox icon={CLIENT_ICONS[tag]} state="active" />
                        <span className="min-w-0 flex-1">
                          <span className="block truncate font-bold text-foreground">{c.display_name} <span className="font-medium text-muted-foreground">· {shortAlias(c.alias)}</span></span>
                          <span className="block text-sm text-primary">{busy === c.customer_ref ? t("common.loading") : t(`clients.rec.${tag}`)}</span>
                        </span>
                        <ArrowRight className="size-4 shrink-0 text-primary transition-transform group-hover:translate-x-1" strokeWidth={STROKE} aria-hidden />
                      </button>
                    </li>
                  ))}
                </ul>
              </section>
            )}
            {list && list.length > 0 && (
              <section className="mt-8" aria-labelledby="any-h">
                <h2 id="any-h" className="text-sm font-semibold text-foreground">{t("clients.any.title")}</h2>
                <ul className="mt-3 divide-y border-y border-primary/15 bg-primary-light/45">
                  {ANY.map((a) => (
                    <li key={a.k}>
                      <button type="button" disabled={!!busy} onClick={() => choose(list[0], a)} className="flex w-full items-center gap-3 px-4 py-3 text-left text-sm hover:bg-primary-light disabled:opacity-70">
                        <IconBox icon={CLIENT_ICONS[a.k]} />
                        <span className="min-w-0 flex-1">
                          <span className="block font-medium">«{t(`clients.any.${a.k}`)}»</span>
                          {a.k === "inject" && <span className="block text-xs text-muted-foreground">{t("clients.any.injectNote")}</span>}
                        </span>
                        <ArrowRight className="size-4 shrink-0 text-primary" strokeWidth={STROKE} aria-hidden />
                      </button>
                    </li>
                  ))}
                </ul>
              </section>
            )}
            <h2 className="mt-12 border-l-[3px] border-l-primary pl-3 text-lg font-bold text-primary-dark">{t("clients.all")}</h2>
            <div className="mt-4 grid gap-3 lg:grid-cols-[minmax(0,1fr)_minmax(150px,auto)_minmax(160px,auto)]">
              <label className="vera-field relative flex h-11 min-w-0 items-center">
                <span className="sr-only">{t("clients.search")}</span>
                <Search className="pointer-events-none absolute left-4 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" aria-hidden />
                <input type="search" value={q} onChange={(e) => setQ(e.target.value)} placeholder={t("clients.search")} className="h-full w-full min-w-0 bg-transparent pl-11 pr-4 text-sm outline-none focus-visible:outline-none focus-visible:shadow-none" />
              </label>
              <select aria-label={t("clients.allCountries")} value={country} onChange={(e) => setCountry(e.target.value)} className="vera-field vera-select h-11 w-full min-w-0 px-4 text-sm font-medium">
                <option value="">{t("clients.allCountries")}</option>
                {countries.map((c) => <option key={c} value={c}>{t(`country.${c}`)}</option>)}
              </select>
              <select aria-label={t("clients.allScenarios")} value={scenario} onChange={(e) => setScenario(e.target.value)} className="vera-field vera-select h-11 w-full min-w-0 px-4 text-sm font-medium">
                <option value="">{t("clients.allScenarios")}</option>
                {scenarios.map((s) => <option key={s} value={s}>{scenarioLabel(t, s)}</option>)}
              </select>
            </div>
            {filtered.length === 0 ? <p className="mt-8 text-sm text-muted-foreground">{t("clients.empty")}</p> : (
          <ul className="mt-6 grid gap-5 lg:grid-cols-2">
            {filtered.map((c) => (
              <li key={c.customer_ref}>
                <button
                  type="button"
                  onClick={() => choose(c)}
                  disabled={!!busy}
                  className="card-soft group flex h-full w-full flex-col p-6 text-left transition hover:-translate-y-0.5 hover:border-primary/60 hover:shadow-lift disabled:opacity-70"
                >
                  <div className="flex items-start justify-between gap-4">
                    <div className="flex items-center gap-4">
                      <IconBox state="active" className="text-primary-dark"><span className="text-sm font-semibold">{c.first_name[0]}</span></IconBox>
                      <div>
                        <p className="text-lg font-bold text-foreground">{c.display_name}</p>
                        <p className="text-sm font-medium text-muted-foreground">{shortAlias(c.alias)}</p>
                      </div>
                    </div>
                    <span className="text-right text-sm font-semibold text-primary">{t(`country.${c.country}`)}</span>
                  </div>
                  <dl className="mt-5 grid grid-cols-2 gap-3 text-sm">
                    <div><dt className="text-xs text-muted-foreground">{t("clients.segment")}</dt><dd className="font-semibold capitalize">{c.segment}</dd></div>
                    <div><dt className="text-xs text-muted-foreground">{t("clients.language")}</dt><dd className="font-semibold">{t(`lang.${c.language}`)}</dd></div>
                  </dl>
                  <div className="mt-4 flex flex-wrap items-center gap-2">
                    <span className="text-xs text-muted-foreground">{t("clients.scenarios")}:</span>
                    <span className="text-xs font-semibold text-foreground">{visibleScenarios(c.scenarios).map((s) => scenarioLabel(t, s)).join(" · ")}</span>
                  </div>
                  <span className="mt-auto inline-flex items-center gap-2 pt-6 text-sm font-semibold text-primary">
                    {busy === c.customer_ref ? t("common.loading") : t("clients.enter", { name: c.first_name })}
                    <ArrowRight className="size-4 transition-transform group-hover:translate-x-1" strokeWidth={STROKE} />
                  </span>
                </button>
              </li>
            ))}
          </ul>
            )}
          </>
        )}
        <Link to="/analista" className="mt-8 inline-flex items-center gap-2 text-sm font-semibold text-primary-dark sm:hidden">
          <ChartNoAxesColumn className="size-4" strokeWidth={STROKE} /> {t("clients.analyst")}
        </Link>
      </main>
    </div>
  );
}
