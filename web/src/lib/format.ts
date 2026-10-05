const MONEY_LOCALE: Record<string, string> = { COP: "es-CO", ARS: "es-AR", MXN: "es-MX", BRL: "pt-BR", USD: "es-CO" };
export function money(amount: string, currency: string) {
  const n = Number(amount);
  const dec = Number.isInteger(n) && currency !== "USD" ? 0 : 2;
  const num = Number.isFinite(n)
    ? new Intl.NumberFormat(MONEY_LOCALE[currency] ?? "es-CO", { minimumFractionDigits: dec, maximumFractionDigits: dec }).format(n)
    : amount;
  return `${currency} ${num}`;
}
// A date without a time ("2026-07-03", a legal deadline) is a calendar day: read it as local, never as midnight UTC,
// which a browser west of Greenwich shows as the day before.
export const toDate = (value: Date | string) =>
  value instanceof Date ? value : /^\d{4}-\d{2}-\d{2}$/.test(value) ? new Date(`${value}T00:00:00`) : new Date(value);
export const dateShort = (iso: string, locale: string) =>
  toDate(iso).toLocaleDateString(locale, { day: "numeric", month: "short", year: "numeric" });
export const dateLong = (iso: string, locale: string) =>
  toDate(iso).toLocaleDateString(locale, { day: "numeric", month: "long", year: "numeric" });
export const timeShort = (d: Date | string, locale: string) =>
  toDate(d).toLocaleTimeString(locale, { hour: "2-digit", minute: "2-digit" });
