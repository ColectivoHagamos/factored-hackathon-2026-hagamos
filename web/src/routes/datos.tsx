import { createFileRoute, Link } from "@tanstack/react-router";
import { ArrowLeft, Database, EyeOff, FileLock2, KeyRound, ServerCog, ShieldCheck } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { api } from "@/api/client";
import type { Count, DataOverview } from "@/api/types";
import { Leaves, SiteHeader } from "@/components/vera/brand";
import { ErrorNote, Loading, useRequire } from "@/components/vera/common";
import { IconBox, STROKE } from "@/components/vera/ui";
import { useT } from "@/i18n/useT";
import { dateLong } from "@/lib/format";

export const Route = createFileRoute("/datos")({
  head: () => ({
    meta: [
      { title: "Datos y seguridad · VERA" },
      { name: "description", content: "De dónde vienen los datos de la demo de VERA y cómo se protegen." },
    ],
  }),
  component: Datos,
});

const PROTECTIONS: { k: string; icon: LucideIcon }[] = [
  { k: "login", icon: KeyRound },
  { k: "pseudo", icon: FileLock2 },
  { k: "removed", icon: EyeOff },
  { k: "leak", icon: ShieldCheck },
  { k: "model", icon: ServerCog },
  { k: "repo", icon: Database },
];

function Datos() {
  const ready = useRequire("access");
  const { t, locale } = useT();
  const [data, setData] = useState<DataOverview | null>(null);
  const [err, setErr] = useState<unknown>(null);
  const number = (n: number) => n.toLocaleString(locale);

  const load = useCallback(() => {
    setErr(null);
    api.dataOverview().then(setData).catch(setErr);
  }, []);
  useEffect(() => {
    if (ready) load();
  }, [ready, load]);

  const subset = data?.subset;
  return (
    <div className="min-h-screen overflow-hidden">
      <SiteHeader
        right={
          <Link to="/clientes" className="hidden items-center gap-2 rounded-full border border-primary-dark/20 px-4 py-2 text-sm font-semibold text-primary-dark hover:bg-primary-light sm:inline-flex">
            <ArrowLeft className="size-4" strokeWidth={STROKE} /> {t("analyst.back")}
          </Link>
        }
      />
      <div className="relative isolate overflow-hidden bg-primary-dark text-primary-foreground">
        <Leaves className="absolute -right-40 -top-48 -z-10 w-[500px] opacity-40 sm:-right-20" />
        <div className="mx-auto max-w-6xl px-5 py-9 sm:px-8 sm:py-11">
          <p className="text-xs font-bold uppercase text-accent">{t("data.eyebrow")}</p>
          <h1 className="mt-3 max-w-3xl text-3xl font-extrabold sm:text-4xl">{t("data.title")}</h1>
          <p className="mt-3 max-w-3xl text-sm leading-relaxed text-primary-foreground/85 sm:text-base">{t("data.sub")}</p>
        </div>
      </div>
      <main className="mx-auto max-w-6xl px-5 pb-20 pt-8 sm:px-8">
        {err ? <ErrorNote error={err} onRetry={load} /> : null}
        {!ready || (!data && !err) ? (
          <Loading />
        ) : data && subset ? (
          <>
            <section aria-labelledby="subset-h">
              <h2 id="subset-h" className="border-l-[3px] border-l-primary pl-3 text-lg font-bold text-primary-dark">{t("data.subset.title")}</h2>
              <p className="mt-2 max-w-3xl text-sm text-muted-foreground">{t("data.subset.sub")}</p>
              <ul className="mt-5 grid grid-cols-2 gap-3 lg:grid-cols-4">
                {(
                  [
                    ["customers", subset.customers],
                    ["cards", subset.cards],
                    ["movements", subset.movements],
                    ["disputes", subset.earlier_disputes],
                  ] as const
                ).map(([k, n]) => (
                  <li key={k} className="card-soft p-4">
                    <p className="text-3xl font-extrabold text-primary-dark">{number(n)}</p>
                    <p className="mt-1 text-sm text-muted-foreground">{t(`data.subset.${k}`)}</p>
                  </li>
                ))}
              </ul>
              {subset.first_movement && subset.last_movement && (
                <p className="mt-3 text-sm text-muted-foreground">
                  {t("data.subset.period", { from: dateLong(subset.first_movement, locale), to: dateLong(subset.last_movement, locale) })}
                </p>
              )}
              <div className="mt-6 grid gap-4 lg:grid-cols-3">
                <Bars title={t("data.subset.byCountry")} rows={subset.customers_by_country} label={(l) => t(`country.${l}`)} number={number} />
                <Bars title={t("data.subset.byCardStatus")} rows={subset.cards_by_status} label={(l) => t(`data.card.${l}`)} number={number} />
                <Bars title={t("data.subset.byMovementStatus")} rows={subset.movements_by_status} label={(l) => t(`status.${l}`)} number={number} />
              </div>
            </section>

            <section className="mt-12" aria-labelledby="source-h">
              <h2 id="source-h" className="border-l-[3px] border-l-primary pl-3 text-lg font-bold text-primary-dark">{t("data.source.title")}</h2>
              <p className="mt-2 max-w-3xl text-sm text-muted-foreground">{t("data.source.sub")}</p>
              <div className="card-soft mt-4 overflow-x-auto">
                <table className="w-full min-w-[520px] text-sm">
                  <thead>
                    <tr className="border-b border-primary/15 text-left text-xs uppercase text-muted-foreground">
                      <th className="px-4 py-3 font-semibold">{t("data.source.table")}</th>
                      <th className="px-4 py-3 text-right font-semibold">{t("data.source.rows")}</th>
                      <th className="px-4 py-3 text-right font-semibold">{t("data.source.valid")}</th>
                      <th className="px-4 py-3 text-right font-semibold">{t("data.source.quarantined")}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.source_tables.map((row) => (
                      <tr key={row.name} className="border-b border-primary/10 last:border-0">
                        <td className="px-4 py-3 font-medium text-foreground">{t(`data.table.${row.name}`)}</td>
                        <td className="px-4 py-3 text-right tabular-nums">{number(row.rows_in)}</td>
                        <td className="px-4 py-3 text-right tabular-nums">{number(row.rows_valid)}</td>
                        <td className="px-4 py-3 text-right tabular-nums">{number(row.rows_quarantined)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {data.source_manifest && (
                <p className="mt-3 break-all text-xs text-muted-foreground">
                  {t("data.source.manifest")}: <code className="text-foreground">{data.source_manifest}</code>
                </p>
              )}
            </section>

            <section className="mt-12" aria-labelledby="protect-h">
              <h2 id="protect-h" className="border-l-[3px] border-l-primary pl-3 text-lg font-bold text-primary-dark">{t("data.protect.title")}</h2>
              <ul className="mt-4 grid gap-3 md:grid-cols-2 lg:grid-cols-3">
                {PROTECTIONS.map(({ k, icon }) => (
                  <li key={k} className="card-soft flex gap-3 p-4">
                    <IconBox icon={icon} state="active" />
                    <span className="min-w-0">
                      <span className="block font-bold text-foreground">{t(`data.protect.${k}.t`)}</span>
                      <span className="mt-1 block text-sm leading-relaxed text-muted-foreground">{t(`data.protect.${k}.d`)}</span>
                    </span>
                  </li>
                ))}
              </ul>
            </section>
          </>
        ) : null}
      </main>
    </div>
  );
}

function Bars({ title, rows, label, number }: { title: string; rows: Count[]; label: (l: string) => string; number: (n: number) => string }) {
  const max = Math.max(1, ...rows.map((r) => r.count));
  return (
    <figure className="card-soft p-4">
      <figcaption className="text-sm font-semibold text-foreground">{title}</figcaption>
      <ul className="mt-3 space-y-2.5">
        {rows.map((r) => (
          <li key={r.label} title={`${label(r.label)}: ${number(r.count)}`}>
            <div className="flex items-baseline justify-between gap-3 text-sm">
              <span className="text-muted-foreground">{label(r.label)}</span>
              <span className="font-semibold tabular-nums text-foreground">{number(r.count)}</span>
            </div>
            <div className="mt-1 h-2 rounded-full bg-primary-light">
              <div className="h-2 rounded-full bg-primary" style={{ width: `${(r.count / max) * 100}%` }} />
            </div>
          </li>
        ))}
      </ul>
    </figure>
  );
}
