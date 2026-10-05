import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import es from "./es.json";
import en from "./en.json";
import pt from "./pt.json";

export type UiLang = "es" | "en" | "pt";
const DICTS: Record<UiLang, Record<string, string>> = { es, en, pt };
export const LOCALES: Record<UiLang, string> = { es: "es-CO", en: "en-US", pt: "pt-BR" };
const STORAGE = "vera.lang";

type Ctx = { lang: UiLang; setLang: (l: UiLang) => void };
const I18nCtx = createContext<Ctx>({ lang: "es", setLang: () => {} });

export function I18nProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<UiLang>("es");
  useEffect(() => {
    const s = window.localStorage.getItem(STORAGE);
    if (s === "es" || s === "en" || s === "pt") setLangState(s);
  }, []);
  useEffect(() => {
    document.documentElement.lang = lang;
  }, [lang]);
  const setLang = useCallback((l: UiLang) => {
    setLangState(l);
    window.localStorage.setItem(STORAGE, l);
  }, []);
  return <I18nCtx.Provider value={{ lang, setLang }}>{children}</I18nCtx.Provider>;
}

export function useT() {
  const { lang, setLang } = useContext(I18nCtx);
  const t = useCallback(
    (k: string, vars?: Record<string, string | number>) => {
      let s = DICTS[lang][k] ?? DICTS.es[k] ?? k;
      if (vars) for (const [n, v] of Object.entries(vars)) s = s.replaceAll(`{${n}}`, String(v));
      return s;
    },
    [lang],
  );
  return useMemo(() => ({ t, lang, setLang, locale: LOCALES[lang] }), [t, lang, setLang]);
}
