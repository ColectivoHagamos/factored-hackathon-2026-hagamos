import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useState, type FormEvent } from "react";
import { api } from "@/api/client";
import { Leaves, SiteHeader } from "@/components/vera/brand";
import { session } from "@/lib/session";
import { useT } from "@/i18n/useT";
import { errorKey } from "@/components/vera/common";

export const Route = createFileRoute("/login")({
  validateSearch: (s: Record<string, unknown>): { expired?: 1 } => (s.expired ? { expired: 1 } : {}),
  head: () => ({
    meta: [
      { title: "Acceso · VERA" },
      { name: "description", content: "Acceso a la demo de VERA para clientes de LATAM Bank y su equipo." },
      { property: "og:title", content: "Acceso · VERA" },
      { property: "og:description", content: "Acceso a la demo de VERA para clientes de LATAM Bank y su equipo." },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary" },
    ],
  }),
  component: Login,
});

function Login() {
  const { t } = useT();
  const { expired } = Route.useSearch();
  const navigate = useNavigate();
  const [user, setUser] = useState("");
  const [pass, setPass] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setErr(null);
    try {
      const r = await api.login({ username: user, password: pass });
      session.clearAll();
      session.setToken("access", { token: r.token, expires_at: r.expires_at });
      session.setMeta("user", r.display_name);
      navigate({ to: "/clientes" });
    } catch (e) {
      const k = errorKey(e);
      setErr(k === "err.401" ? t("login.error") : t(k));
    } finally {
      setBusy(false);
    }
  }

  const input = "vera-field mt-2 w-full px-4 py-3 text-sm font-medium";
  return (
    <div className="relative min-h-screen overflow-hidden">
      <Leaves className="absolute -right-24 -top-16 w-[520px]" />
      <Leaves corner="bl" className="absolute -bottom-32 -left-32 w-[420px] opacity-70" />
      <SiteHeader />
      <main className="relative z-10 mx-auto flex max-w-md flex-col px-5 pb-16 pt-10">
        <div className="card-soft p-8">
          <h1 className="text-2xl font-extrabold text-primary-dark">{t("login.title")}</h1>
          <p className="mt-2 text-sm text-muted-foreground">{t("login.sub")}</p>
          {expired && <p role="status" className="mt-5 rounded-xl bg-primary-light px-4 py-3 text-sm font-medium text-primary-dark">{t("login.expired")}</p>}
          <form onSubmit={submit} className="mt-6 space-y-4">
            <label className="block text-sm font-semibold">
              {t("login.user")}
              <input className={input} value={user} onChange={(e) => setUser(e.target.value)} autoComplete="username" required />
            </label>
            <label className="block text-sm font-semibold">
              {t("login.pass")}
              <input className={input} type="password" value={pass} onChange={(e) => setPass(e.target.value)} autoComplete="current-password" required />
            </label>
            {err && <p role="alert" className="rounded-xl bg-danger-soft px-4 py-3 text-sm font-medium text-danger">{err}</p>}
            <button disabled={busy} className="w-full rounded-full bg-primary-dark py-3.5 text-sm font-semibold text-primary-foreground transition-opacity disabled:opacity-60">
              {busy ? t("login.loading") : t("login.submit")}
            </button>
          </form>
        </div>
      </main>
    </div>
  );
}
