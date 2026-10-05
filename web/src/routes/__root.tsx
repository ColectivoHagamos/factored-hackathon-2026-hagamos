import { HeadContent, Link, Outlet, createRootRoute, useRouter, type ErrorComponentProps } from "@tanstack/react-router";

import { I18nProvider, useT } from "@/i18n/useT";

function NotFoundComponent() {
  return <I18nProvider><NotFoundBody /></I18nProvider>;
}

function NotFoundBody() {
  const { t } = useT();
  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-4">
      <div className="max-w-md text-center">
        <h1 className="text-7xl font-extrabold text-primary-dark">404</h1>
        <h2 className="mt-4 text-xl font-semibold text-foreground">{t("err.notFound")}</h2>
        <div className="mt-6">
          <Link to="/" className="inline-flex items-center justify-center rounded-full bg-primary-dark px-5 py-2.5 text-sm font-semibold text-primary-foreground">
            {t("err.home")}
          </Link>
        </div>
      </div>
    </div>
  );
}

function ErrorComponent(props: ErrorComponentProps) {
  return <I18nProvider><ErrorBody {...props} /></I18nProvider>;
}

function ErrorBody({ error, reset }: ErrorComponentProps) {
  const { t } = useT();
  console.error(error);
  const router = useRouter();
  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-4">
      <div className="max-w-md text-center">
        <h1 className="text-xl font-bold text-foreground">{t("err.title")}</h1>
        <p className="mt-2 text-sm text-muted-foreground">{t("err.body")}</p>
        <button
          onClick={() => {
            router.invalidate();
            reset();
          }}
          className="mt-6 inline-flex rounded-full bg-primary-dark px-5 py-2.5 text-sm font-semibold text-primary-foreground"
        >
          {t("err.retry")}
        </button>
      </div>
    </div>
  );
}

export const Route = createRootRoute({
  head: () => ({
    meta: [
      { title: "VERA · Inteligencia que genera confianza" },
      { name: "description", content: "VERA, la asistente de LATAM Bank para disputas de tarjeta." },
      { property: "og:type", content: "website" },
    ],
  }),
  component: RootComponent,
  notFoundComponent: NotFoundComponent,
  errorComponent: ErrorComponent,
});

function RootComponent() {
  return (
    <I18nProvider>
      <HeadContent />
      <Outlet />
    </I18nProvider>
  );
}
