import { createFileRoute, Link } from "@tanstack/react-router";
import {
  ArrowRight, ChartNoAxesColumn, ChevronRight, CircleCheck, CircleQuestionMark, FileText, History, Lightbulb,
  MessageSquareText, Search, TriangleAlert, User,
} from "lucide-react";
import { IconBox, STROKE } from "@/components/vera/ui";
import { HagamosLogo, Leaves, Logo, SiteHeader, VAvatar } from "@/components/vera/brand";
import { useT } from "@/i18n/useT";
import { IntegrationSection } from "@/components/vera/integration";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "VERA · Menos incertidumbre. Más confianza." },
      { name: "description", content: "VERA, la asistente de inteligencia artificial de LATAM Bank que verifica, explica y registra disputas de tarjeta." },
      { property: "og:title", content: "VERA · Menos incertidumbre. Más confianza." },
      { property: "og:description", content: "Asistente de IA de LATAM Bank para disputas de tarjeta: verifica, explica, registra y acompaña." },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary" },
    ],
  }),
  component: Home,
});

function PhoneMock() {
  const { t } = useT();
  return (
    <div className="relative z-10 mx-auto aspect-[9/19.5] w-[min(240px,65vw)] shrink-0 rounded-[48px] bg-primary-dark p-[9px] shadow-lift lg:w-[270px]">
      <div className="relative flex h-full flex-col overflow-hidden rounded-[40px] bg-surface">
        <span aria-hidden className="absolute left-1/2 top-2.5 h-[22px] w-[34%] -translate-x-1/2 rounded-full bg-primary-dark" />
        <div className="flex items-center justify-between px-6 pt-3 text-[10px] font-semibold text-foreground">
          <span>9:41</span>
          <span aria-hidden className="tracking-tight">•••</span>
        </div>
        <div className="flex items-center justify-between px-4 pb-3 pt-4">
          <Logo className="h-[18px]" />
          <span className="grid size-7 place-items-center rounded-[9px] border border-primary-dark/8 bg-surface/70"><User className="size-3.5 text-primary-dark" strokeWidth={STROKE} /></span>
        </div>
        <div className="flex-1 space-y-2.5 px-3 text-[10.5px] leading-snug">
          <div className="ml-auto max-w-[85%] rounded-2xl rounded-br-md bg-primary-dark px-3 py-2 text-primary-foreground">{t("home.phone.user")}</div>
          <div className="flex gap-1.5">
            <VAvatar size="sm" />
            <div className="rounded-2xl rounded-tl-md border bg-background px-3 py-2">{t("home.phone.vera")}</div>
          </div>
          <div className="ml-8 rounded-2xl border bg-background px-3 py-2">
            <div className="flex items-center gap-1.5">
              <Search className="size-3.5 shrink-0 text-primary" strokeWidth={STROKE} />
              <span className="flex-1 font-semibold text-primary">{t("home.phone.analyzing")}</span>
            </div>
            <div className="mt-1.5 h-1 overflow-hidden rounded-full bg-muted">
              <div className="progress-run h-full rounded-full bg-primary-dark" />
            </div>
          </div>
          <div className="flex gap-1.5">
            <VAvatar size="sm" />
            <div className="rounded-2xl rounded-tl-md border bg-background px-3 py-2">{t("home.phone.result")}</div>
          </div>
        </div>
        <div className="m-3 flex items-center gap-2 rounded-full border bg-background py-1 pl-3 pr-1 text-[10px] text-muted-foreground">
          <span className="flex-1">…</span>
          <span className="grid size-6 place-items-center rounded-full bg-primary-dark"><ArrowRight className="size-3 text-primary-foreground" strokeWidth={STROKE} /></span>
        </div>
      </div>
    </div>
  );
}

function Float({ icon: Icon, text }: { icon: typeof Search; text: string }) {
  return (
    <div className="glass flex items-center gap-2.5 p-3 text-xs font-medium text-foreground sm:text-sm lg:h-[88px] lg:w-[190px] lg:gap-3 lg:p-4">
      <IconBox icon={Icon} />
      <span className="min-w-0 leading-snug">{text}</span>
    </div>
  );
}

function Home() {
  const { t } = useT();
  const steps = [
    { icon: MessageSquareText, k: "s1" },
    { icon: Search, k: "s2" },
    { icon: FileText, k: "s3" },
    { icon: Lightbulb, k: "s4" },
    { icon: CircleCheck, k: "s5" },
  ];
  const benefits = [
    { icon: User, k: "b1" },
    { icon: History, k: "b2" },
    { icon: FileText, k: "b3" },
    { icon: CircleQuestionMark, k: "b4" },
  ];
  const cases = [
    { icon: Search, k: "c1" },
    { icon: FileText, k: "c2" },
    { icon: TriangleAlert, k: "c3" },
    { icon: User, k: "c4" },
    { icon: History, k: "c5" },
  ];
  const navLinks = [
    ["#que-es", "nav.what"],
    ["#como-funciona", "nav.how"],
    ["#beneficios", "nav.benefits"],
    ["#integracion", "nav.integration"],
    ["#casos", "nav.cases"],
  ];

  return (
    <div className="min-h-screen overflow-x-hidden bg-background">
      <section className="relative overflow-hidden">
        <Leaves className="absolute -right-24 -top-10 w-[420px] opacity-90 sm:w-[560px] lg:w-[680px]" />
        <SiteHeader
          nav={
            <nav className="hidden items-center gap-7 text-sm font-medium text-muted-foreground lg:flex" aria-label={t("nav.sections")}>
              {navLinks.map(([h, k]) => (
                <a key={h} href={h} className="transition-colors hover:text-primary-dark">{t(k)}</a>
              ))}
            </nav>
          }
          right={
            <Link to="/login" className="hidden items-center gap-2 rounded-full bg-primary-dark px-5 py-2.5 text-sm font-semibold text-primary-foreground transition-transform hover:-translate-y-0.5 sm:inline-flex">
              {t("home.cta")} <ArrowRight className="size-4" strokeWidth={STROKE} />
            </Link>
          }
        />
        <div className="relative z-10 mx-auto grid max-w-7xl items-center gap-12 px-5 pb-20 pt-8 sm:px-8 lg:grid-cols-[1.05fr_1fr] lg:pt-14 xl:grid-cols-[minmax(0,1fr)_640px]">
          <div>
            <p className="eyebrow">{t("home.eyebrow")}</p>
            <h1 className="mt-5 text-4xl font-extrabold leading-[1.05] text-primary-dark sm:text-5xl lg:text-6xl">
              {t("home.title1")}
              <br />
              <span className="text-primary">{t("home.title2")}</span>
            </h1>
            <p className="mt-6 max-w-xl text-base leading-relaxed text-muted-foreground sm:text-lg">{t("home.sub")}</p>
            <div className="mt-9 flex flex-wrap items-center gap-4">
              <Link to="/login" className="inline-flex items-center gap-2 rounded-full bg-primary-dark px-7 py-3.5 text-sm font-semibold text-primary-foreground shadow-soft transition-transform hover:-translate-y-0.5">
                {t("home.cta")} <ArrowRight className="size-4" strokeWidth={STROKE} />
              </Link>
              <a href="#como-funciona" className="inline-flex items-center gap-2 rounded-full px-4 py-3.5 text-sm font-semibold text-primary-dark hover:bg-primary-light">
                {t("home.how.cta")}
              </a>
            </div>
          </div>
          <div className="relative">
            <div className="hidden items-center justify-center xl:flex">
              <div className="relative z-0 -mr-[8px] flex flex-col gap-6">
                <Float icon={Search} text={t("home.float1")} />
                <Float icon={FileText} text={t("home.float2")} />
              </div>
              <PhoneMock />
              <div className="relative z-0 -ml-[8px] flex flex-col gap-6">
                <Float icon={Lightbulb} text={t("home.float3")} />
                <Float icon={User} text={t("home.float4")} />
              </div>
            </div>
            <div className="xl:hidden">
              <PhoneMock />
              <div className="mx-auto mt-6 grid max-w-[400px] grid-cols-2 gap-3 lg:max-w-[396px] lg:gap-4">
                <Float icon={Search} text={t("home.float1")} />
                <Float icon={FileText} text={t("home.float2")} />
                <Float icon={Lightbulb} text={t("home.float3")} />
                <Float icon={User} text={t("home.float4")} />
              </div>
            </div>
          </div>
        </div>
      </section>

      <section id="que-es" className="mx-auto grid max-w-7xl scroll-mt-10 gap-10 px-5 py-20 sm:px-8 lg:grid-cols-[1fr_1.15fr] lg:items-center">
        <div>
          <p className="eyebrow max-w-xs leading-relaxed">{t("home.what.eyebrow")}</p>
          <h2 className="mt-4 text-3xl font-extrabold text-primary-dark sm:text-4xl">{t("home.what.title")}</h2>
          <p className="mt-6 leading-relaxed text-muted-foreground">{t("home.what.p1")}</p>
          <p className="mt-4 leading-relaxed text-muted-foreground">{t("home.what.p2")}</p>
        </div>
        <div className="relative overflow-hidden rounded-[28px] bg-primary-light p-8 sm:p-12">
          <Leaves corner="bl" className="absolute -bottom-20 -left-20 w-80 opacity-70" />
          <div className="relative grid gap-4 sm:grid-cols-[1fr_0.9fr] sm:items-end">
            <div className="card-soft space-y-3 p-5">
              <div className="flex items-center gap-2 text-sm font-bold text-primary-dark"><VAvatar size="sm" /> VERA</div>
              {["home.c1", "home.c2", "home.c3", "home.c4"].map((k, i) => (
                <div key={k} className="flex items-center gap-3 rounded-xl border bg-background px-3 py-2.5 text-sm font-medium">
                  <span className="w-4 text-xs font-semibold tabular-nums text-primary">{i + 1}</span>
                  {t(k)}
                </div>
              ))}
            </div>
            <div className="glass p-6">
              <IconBox icon={ChartNoAxesColumn} />
              <p className="mt-4 text-xl font-semibold leading-snug text-primary-dark">{t("home.what.card")}</p>
            </div>
          </div>
        </div>
      </section>

      <section id="como-funciona" className="relative scroll-mt-0 overflow-hidden bg-primary-dark py-20 text-primary-foreground">
        <Leaves className="absolute -right-32 -top-32 w-[460px] opacity-10" />
        <div className="relative mx-auto max-w-7xl px-5 sm:px-8">
          <div className="grid gap-6 lg:grid-cols-2 lg:items-end">
            <div>
              <p className="eyebrow !text-primary-light">{t("home.how.eyebrow")}</p>
              <h2 className="mt-4 text-3xl font-extrabold sm:text-4xl">
                {t("home.how.title1")}
                <br />
                <span className="font-semibold text-primary-light">{t("home.how.title2")}</span>
              </h2>
            </div>
            <p className="max-w-md text-primary-foreground/75 lg:justify-self-end">{t("home.how.sub")}</p>
          </div>
          <ol className="mt-12 grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
            {steps.map(({ icon: Icon, k }, i) => (
              <li key={k} className="relative rounded-2xl bg-surface p-5 text-foreground">
                <div className="flex items-center gap-3">
                  <IconBox icon={Icon} />
                  <span className="font-bold text-primary-dark">{i + 1}. {t(`home.how.${k}.t`)}</span>
                </div>
                <p className="mt-3 text-sm leading-relaxed text-muted-foreground">{t(`home.how.${k}.d`)}</p>
              </li>
            ))}
          </ol>
        </div>
      </section>

      <section id="beneficios" className="mx-auto max-w-7xl scroll-mt-10 px-5 py-20 sm:px-8">
        <div className="grid gap-6 lg:grid-cols-2 lg:items-end">
          <div>
            <p className="eyebrow">{t("home.benefits.eyebrow")}</p>
            <h2 className="mt-4 text-3xl font-extrabold text-primary-dark sm:text-4xl">
              {t("home.benefits.title1")}
              <br />
              <span className="font-semibold text-primary">{t("home.benefits.title2")}</span>
            </h2>
          </div>
          <p className="max-w-md text-muted-foreground lg:justify-self-end">{t("home.benefits.sub")}</p>
        </div>
        <div className="mt-12 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {benefits.map(({ icon: Icon, k }) => (
            <div key={k} className="card-soft flex gap-4 p-6">
              <IconBox icon={Icon} />
              <div>
                <h3 className="font-bold text-primary-dark">{t(`home.${k}.t`)}</h3>
                <p className="mt-2 text-sm leading-relaxed text-muted-foreground">{t(`home.${k}.d`)}</p>
              </div>
            </div>
          ))}
        </div>
      </section>

      <IntegrationSection />

      <section id="casos" className="grid scroll-mt-10 lg:grid-cols-2">
        <div className="bg-primary-light px-5 py-16 sm:px-12">
          <p className="eyebrow">{t("home.cases.eyebrow")}</p>
          <h2 className="mt-4 text-3xl font-extrabold text-primary-dark">
            {t("home.cases.title1")}
            <br />
            <span className="font-semibold text-primary">{t("home.cases.title2")}</span>
          </h2>
          <ul className="mt-8 max-w-md space-y-3">
            {cases.map(({ icon: Icon, k }) => (
              <li key={k}>
                {/* Each use case opens the demo, where a walkthrough shows it with a real customer. */}
                <Link to="/login" className="flex items-center gap-3 rounded-2xl bg-surface px-4 py-3.5 text-sm font-medium shadow-soft transition hover:-translate-y-0.5 hover:shadow-lift">
                  <IconBox icon={Icon} />
                  <span className="flex-1">{t(`home.${k}`)}</span>
                  <ChevronRight className="size-4 text-muted-foreground" strokeWidth={STROKE} aria-hidden />
                </Link>
              </li>
            ))}
          </ul>
        </div>
        <div className="relative overflow-hidden bg-primary-dark px-5 py-16 text-primary-foreground sm:px-12">
          <Leaves className="absolute -right-28 -top-28 w-96 opacity-15" />
          <div className="relative max-w-md">
            <p className="eyebrow !text-primary-light">{t("home.final.eyebrow")}</p>
            <h2 className="mt-4 text-3xl font-extrabold">{t("home.final.title")}</h2>
            <p className="mt-5 leading-relaxed text-primary-foreground/80">{t("home.final.body")}</p>
            <Link to="/login" className="mt-8 inline-flex items-center gap-2 rounded-full bg-surface px-7 py-3.5 text-sm font-semibold text-primary-dark transition-transform hover:-translate-y-0.5">
              {t("home.cta")} <ArrowRight className="size-4" strokeWidth={STROKE} />
            </Link>
          </div>
        </div>
      </section>

      <footer className="mx-auto flex max-w-7xl flex-col items-center justify-between gap-4 px-5 py-10 text-sm text-muted-foreground sm:flex-row sm:px-8">
        <div className="flex items-center gap-4">
          <HagamosLogo className="h-7" />
          <span>{t("footer.credit")}</span>
        </div>
        <span className="font-semibold text-primary-dark">{t("footer.tagline")}</span>
      </footer>
    </div>
  );
}
