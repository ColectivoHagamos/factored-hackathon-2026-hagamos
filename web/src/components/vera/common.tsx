import { useNavigate } from "@tanstack/react-router";
import { TriangleAlert } from "lucide-react";
import { useEffect, useState } from "react";
import { ApiError } from "@/api/client";
import { session, type TokenKind } from "@/lib/session";
import { useT } from "@/i18n/useT";

export function useRequire(kind: TokenKind) {
  const navigate = useNavigate();
  const [ready, setReady] = useState(false);
  useEffect(() => {
    const access = session.getToken("access");
    if (!access || access.expired) {
      navigate({ to: "/login", search: { expired: access?.expired ? 1 : undefined }, replace: true });
      return;
    }
    if (kind !== "access") {
      const t = session.getToken(kind);
      if (!t || t.expired) {
        navigate({ to: kind === "analyst" ? "/analista" : "/clientes", replace: true });
        if (kind === "analyst") setReady(true);
        return;
      }
    }
    setReady(true);
  }, [kind, navigate]);
  return ready;
}

export function errorKey(e: unknown): "err.401" | "err.429" | "err.503" | "err.generic" {
  if (e instanceof ApiError) {
    if (e.status === 401 || e.code === "unauthorized") return "err.401";
    if (e.status === 429 || e.code === "rate_limited") return "err.429";
    if (e.status === 503 || e.code === "provider_unavailable") return "err.503";
  }
  return "err.generic";
}

export function ErrorNote({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const { t } = useT();
  const navigate = useNavigate();
  const k = errorKey(error);
  return (
    <div role="alert" className="flex flex-wrap items-center gap-3 rounded-2xl border border-warning/20 bg-warning-soft px-4 py-3 text-sm text-foreground">
      <TriangleAlert className="size-4 shrink-0 text-warning" aria-hidden />
      <span className="flex-1 font-medium">{t(k)}</span>
      {k === "err.401" ? (
        <button
          type="button"
          onClick={() => {
            session.setToken("customer", null);
            navigate({ to: "/clientes" });
          }}
          className="rounded-full bg-primary-dark px-3 py-1.5 text-xs font-semibold text-primary-foreground"
        >
          {t("err.401.action")}
        </button>
      ) : onRetry ? (
        <button type="button" onClick={onRetry} className="rounded-full border border-primary-dark/30 px-3 py-1.5 text-xs font-semibold text-primary-dark">
          {t("err.retry")}
        </button>
      ) : null}
    </div>
  );
}

export function Loading({ rows = 4 }: { rows?: number }) {
  const { t } = useT();
  return (
    <div className="mt-6 space-y-3" role="status" aria-live="polite">
      <span className="sr-only">{t("common.loading")}</span>
      <div className="skeleton h-6 w-48" />
      {Array.from({ length: rows }, (_, i) => (
        <div key={i} className="flex items-center gap-4 rounded-[18px] border bg-surface p-4">
          <div className="skeleton size-10 shrink-0 rounded-full" />
          <div className="flex-1 space-y-2">
            <div className="skeleton h-3.5 w-2/5" />
            <div className="skeleton h-3 w-3/5" />
          </div>
          <div className="skeleton h-4 w-20" />
        </div>
      ))}
    </div>
  );
}
