import { Link } from "@tanstack/react-router";
import type { ReactNode } from "react";
import { useT, type UiLang } from "@/i18n/useT";
import { cn } from "@/lib/utils";

export function Logo({ variant = "green", className }: { variant?: "green" | "white"; className?: string }) {
  return (
    <img
      src={variant === "white" ? "/brand/vera-white.png" : "/brand/vera-green.png"}
      alt="VERA"
      className={cn("h-7 w-auto select-none", className)}
      draggable={false}
    />
  );
}

export function HagamosLogo({ className }: { className?: string }) {
  return <img src="/brand/hagamos.png" alt="Colectivo HAGAMOS" className={cn("h-6 w-auto", className)} />;
}

export function VAvatar({ size = "md", className }: { size?: "sm" | "md" | "lg"; className?: string }) {
  const box = size === "sm" ? "size-7 rounded-[9px]" : size === "lg" ? "size-14 rounded-[18px]" : "size-8 rounded-[10px]";
  return (
    <span aria-hidden className={cn("grid shrink-0 place-items-center bg-primary-dark", box, className)}>
      <svg viewBox="0 0 70 46" className="w-[60%]">
        <path d="M2 0h15c4 0 7 2 9 5l18 32c1 2 1 4 0 5-3 3-6 4-9 4s-7-2-9-5L.5 3C0 1.6.8 0 2 0Z" className="fill-primary-light" opacity="0.5" />
        <path d="M68 0H53c-4 0-7 2-10 6l-6 8c-1 1-1 3 0 4l8 15c1 1 3 1 4 0L69 3c1-1.5 0-3-1-3Z" className="fill-primary-light" opacity="0.85" />
        <path d="M13 12h9l22 25c1 2 1 4 0 5-3 3-6 4-9 4s-7-2-9-5Z" className="fill-primary-light" opacity="0.6" />
      </svg>
    </span>
  );
}

export const isoUrl = "/brand/v-green.png";


export function LangSwitch({ tone = "light" }: { tone?: "light" | "dark" }) {
  const { lang, setLang, t } = useT();
  const opts: UiLang[] = ["es", "en", "pt"];
  return (
    <div
      role="group"
      aria-label={t("lang.label")}
      className={cn(
        "inline-flex rounded-full p-1 text-xs font-semibold",
        tone === "light" ? "bg-muted" : "bg-primary-foreground/10",
      )}
    >
      {opts.map((o) => (
        <button
          key={o}
          type="button"
          aria-pressed={lang === o}
          onClick={() => setLang(o)}
          className={cn(
            "rounded-full px-2.5 py-1 uppercase transition-colors",
            lang === o
              ? tone === "light"
                ? "bg-surface text-primary-dark shadow-sm"
                : "bg-primary-foreground text-primary-dark"
              : tone === "light"
                ? "text-muted-foreground hover:text-foreground"
                : "text-primary-foreground/70 hover:text-primary-foreground",
          )}
        >
          {o}
        </button>
      ))}
    </div>
  );
}

export function Leaves({ className, corner = "tr" }: { className?: string; corner?: "tr" | "bl" | "br" }) {
  const rot = corner === "bl" ? "rotate-180" : corner === "br" ? "-scale-x-100 rotate-180" : "";
  return (
    <svg viewBox="0 0 600 600" aria-hidden className={cn("pointer-events-none", rot, className)} style={{ maskImage: "radial-gradient(circle at 100% 0%, #000 45%, transparent 72%)", WebkitMaskImage: "radial-gradient(circle at 100% 0%, #000 45%, transparent 72%)" }}>
      <path className="fill-primary-light" d="M600 0v600C420 560 300 470 260 340 220 210 300 80 600 0Z" />
      <path className="fill-primary/25" d="M600 60v420c-120-30-210-110-230-210C350 170 430 90 600 60Z" />
      <path className="fill-primary-dark/20" d="M600 250v350H330c40-170 130-290 270-350Z" />
      <path className="fill-primary/15" d="M420 0h180v170C520 140 450 80 420 0Z" />
    </svg>
  );
}

export function SiteHeader({ right, nav }: { right?: ReactNode; nav?: ReactNode }) {
  return (
    <header className="relative z-20 mx-auto flex w-full max-w-7xl items-center justify-between gap-4 px-5 py-5 sm:px-8">
      <Link to="/" aria-label="VERA" className="shrink-0">
        <Logo className="h-7 sm:h-8" />
      </Link>
      {nav}
      <div className="flex items-center gap-3">
        <LangSwitch />
        {right}
      </div>
    </header>
  );
}
