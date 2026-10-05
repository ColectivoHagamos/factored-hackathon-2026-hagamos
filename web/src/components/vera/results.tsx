import { useT } from "@/i18n/useT";

// Sealed held-out evaluation (docs/evaluation/heldout.md): VERA's learned classifier against the keyword baseline,
// per 100 runs; the fourth counts runs sent to the wrong queue (0 against 45 of 897).
const METRICS = [
  { k: "r1", value: "45", baseline: "18" },
  { k: "r2", value: "4", baseline: "70" },
  { k: "r3", value: "7", baseline: "60" },
  { k: "r4", value: "0", baseline: "5" },
] as const;

export function ResultsSection() {
  const { t } = useT();
  return (
    <section id="resultados" className="mx-auto max-w-7xl scroll-mt-10 px-5 py-20 sm:px-8" aria-labelledby="results-h">
      <div className="grid gap-6 lg:grid-cols-2 lg:items-end">
        <div>
          <p className="eyebrow">{t("home.results.eyebrow")}</p>
          <h2 id="results-h" className="mt-4 text-3xl font-extrabold text-primary-dark sm:text-4xl">{t("home.results.title")}</h2>
        </div>
        <p className="max-w-md text-muted-foreground lg:justify-self-end">{t("home.results.sub")}</p>
      </div>
      <dl className="mt-12 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {METRICS.map(({ k, value, baseline }) => (
          <div key={k} className="card-soft flex flex-col p-6">
            <dt className="order-2 mt-3 text-sm leading-relaxed text-foreground">{t(`home.results.${k}`)}</dt>
            <dd className="order-1 flex items-baseline gap-2">
              <span className="text-5xl font-extrabold tabular-nums text-primary-dark">{value}</span>
              <span className="text-sm font-semibold text-primary">{t("home.results.per100")}</span>
            </dd>
            <dd className="order-3 mt-auto pt-4 text-xs text-muted-foreground">{t("home.results.baseline", { n: baseline })}</dd>
          </div>
        ))}
      </dl>
      <p className="mt-8 max-w-3xl text-sm leading-relaxed text-muted-foreground">{t("home.results.note")}</p>
    </section>
  );
}
