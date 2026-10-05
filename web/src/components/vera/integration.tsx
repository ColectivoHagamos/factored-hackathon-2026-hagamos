import type { LucideIcon } from "lucide-react";
import { CircleCheck, FileText, History, Inbox, MessageSquareText, MessagesSquare, Nfc, Settings, SlidersHorizontal, User } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { IconBox, STROKE } from "@/components/vera/ui";
import { VAvatar } from "@/components/vera/brand";
import { useT } from "@/i18n/useT";
import { cn } from "@/lib/utils";
const SYSTEMS: { k: string; icon: LucideIcon }[] = [
  { k: "id", icon: User },
  { k: "tx", icon: History },
  { k: "card", icon: Nfc },
  { k: "case", icon: FileText },
  { k: "queue", icon: Inbox },
  { k: "audit", icon: CircleCheck },
  { k: "model", icon: SlidersHorizontal },
  { k: "chan", icon: MessagesSquare },
];

function SystemCard({
  k,
  icon: Icon,
  active,
  onSelect,
}: {
  k: string;
  icon?: LucideIcon;
  active: boolean;
  onSelect: (k: string) => void;
}) {
  const { t } = useT();
  return (
    <li>
      <button
        type="button"
        onClick={() => onSelect(k)}
        aria-pressed={active}
        className={cn(
          "flex w-full items-start gap-2.5 rounded-2xl border p-3 text-left backdrop-blur-sm transition-[border-color,background-color,box-shadow] duration-200",
          active
            ? "border-primary/50 bg-primary-light shadow-[0_0_0_3px_color-mix(in_srgb,var(--primary)_12%,transparent)]"
            : "border-primary-dark/8 bg-surface/70 hover:border-primary/35 hover:bg-primary-light/60",
        )}
      >
        {Icon && (
          <Icon
            className={cn("mt-0.5 size-4 shrink-0 transition-colors", active ? "text-primary" : "text-primary-dark")}
            strokeWidth={STROKE}
            aria-hidden
          />
        )}
        <div className="min-w-0">
          <p className="text-sm font-semibold leading-snug text-primary-dark">{t(`int.s.${k}.t`)}</p>
          <p className="mt-0.5 text-xs leading-snug text-muted-foreground">{t(`int.s.${k}.d`)}</p>
        </div>
      </button>
    </li>
  );
}

function Core({ pulse }: { pulse: boolean }) {
  const { t } = useT();
  return (
    <div className="relative mx-auto grid size-[230px] shrink-0 place-items-center sm:size-[260px]">
      <svg viewBox="0 0 260 260" aria-hidden className="absolute inset-0 size-full">
        <path
          className={cn("fill-primary-light transition-opacity duration-500", pulse && "opacity-80")}
          d="M130 8c62 0 118 44 122 112 4 70-52 132-124 132C58 252 8 198 8 128 8 62 66 8 130 8Z"
        />
        <path
          className={cn("fill-primary/15 transition-opacity duration-500", pulse && "opacity-90")}
          d="M134 34c50 2 92 42 92 96 0 56-44 98-98 98-52 0-94-40-94-94 0-56 46-102 100-100Z"
        />
        <path
          className={cn("fill-primary/20 transition-opacity duration-500", pulse && "opacity-100")}
          d="M130 62c38 0 68 30 68 68s-30 70-70 68c-36-2-66-32-64-70 2-36 30-66 66-66Z"
        />
      </svg>
      <div className="relative flex flex-col items-center text-center">
        <VAvatar size="lg" />
        <p className="mt-3 text-sm font-bold text-primary-dark">{t("int.core")}</p>
        <p className="mt-1 max-w-[150px] text-[11px] leading-snug text-primary-dark/75">{t("int.coreSub")}</p>
      </div>
    </div>
  );
}


export function IntegrationSection() {
  const { t } = useT();
  const ref = useRef<HTMLDivElement>(null);
  const [seen, setSeen] = useState(false);
  const [selected, setSelected] = useState<string | null>(null);
  useEffect(() => {
    const el = ref.current;
    if (!el || typeof IntersectionObserver === "undefined") return setSeen(true);
    const o = new IntersectionObserver(([e]) => { if (e.isIntersecting) { setSeen(true); o.disconnect(); } }, { threshold: 0.2 });
    o.observe(el);
    return () => o.disconnect();
  }, []);
  const ideas: { icon: LucideIcon; k: string }[] = [
    { icon: Settings, k: "i1" },
    { icon: MessageSquareText, k: "i2" },
    { icon: FileText, k: "i3" },
  ];
  const left = SYSTEMS.slice(0, 4);
  const right = SYSTEMS.slice(4);
  const select = (k: string) => setSelected((cur) => (cur === k ? null : k));

  return (
    <section id="integracion" className="mx-auto max-w-7xl scroll-mt-10 px-5 py-20 sm:px-8">
      <div className="grid gap-6 lg:grid-cols-2 lg:items-end">
        <div>
          <p className="eyebrow">{t("int.eyebrow")}</p>
          <h2 className="mt-4 text-3xl font-extrabold text-primary-dark sm:text-4xl">{t("int.title")}</h2>
        </div>
        <p className="max-w-xl leading-relaxed text-muted-foreground lg:justify-self-end">{t("int.sub")}</p>
      </div>

      <ul className="mt-10 grid gap-4 md:grid-cols-3">
        {ideas.map(({ icon, k }) => (
          <li key={k} className="card-soft flex gap-4 p-6">
            <IconBox icon={icon} />
            <div>
              <h3 className="font-bold text-primary-dark">{t(`int.${k}.t`)}</h3>
              <p className="mt-2 text-sm leading-relaxed text-muted-foreground">{t(`int.${k}.d`)}</p>
            </div>
          </li>
        ))}
      </ul>

      <figure
        ref={ref}
        role="group"
        aria-labelledby="int-d-title"
        aria-describedby="int-d-desc"
        className={cn(
          "relative mt-12 overflow-hidden rounded-[28px] bg-background p-5 ring-1 ring-primary-dark/5 sm:p-8 motion-safe:transition-[opacity,transform] motion-safe:duration-700",
          seen ? "opacity-100 translate-y-0" : "motion-safe:translate-y-3 motion-safe:opacity-0",
        )}
      >
        <h3 id="int-d-title" className="sr-only">{t("int.dTitle")}</h3>
        <p id="int-d-desc" className="sr-only">{t("int.dDesc")}</p>
        <p className="sr-only">{t("int.listTitle")}</p>

        <div className="hidden items-center gap-6 lg:grid lg:grid-cols-[minmax(0,1fr)_auto_minmax(0,1fr)]">
          <ul className="grid gap-3">
            {left.map((s) => <SystemCard key={s.k} {...s} active={selected === s.k} onSelect={select} />)}
          </ul>
          <Core pulse={selected != null} />
          <ul className="grid gap-3">
            {right.map((s) => <SystemCard key={s.k} {...s} active={selected === s.k} onSelect={select} />)}
          </ul>
        </div>

        <div className="lg:hidden">
          <Core pulse={selected != null} />
          <ul className="mt-6 grid grid-cols-2 gap-3">
            {SYSTEMS.map((s) => <SystemCard key={s.k} {...s} active={selected === s.k} onSelect={select} />)}
          </ul>
        </div>

        <p
          aria-live="polite"
          className={cn(
            "mt-6 text-center text-sm font-medium text-primary-dark transition-opacity duration-300",
            selected ? "opacity-100" : "opacity-0",
          )}
        >
          {selected ? t(`int.s.${selected}.d`) : " "}
        </p>
      </figure>

      <p className="mt-5 max-w-3xl text-xs leading-relaxed text-muted-foreground">{t("int.note")}</p>
    </section>
  );
}
