export type TokenKind = "access" | "customer" | "analyst";
type Stored = { token: string; expires_at: string };

const mem: Partial<Record<string, unknown>> = {};
const isBrowser = () => typeof window !== "undefined";
const key = (k: string) => `vera.${k}`;

function read<T>(k: string): T | null {
  if (k in mem) return (mem[k] as T) ?? null;
  if (!isBrowser()) return null;
  try {
    const raw = window.sessionStorage.getItem(key(k));
    const v = raw ? (JSON.parse(raw) as T) : null;
    mem[k] = v;
    return v;
  } catch {
    return null;
  }
}
function write(k: string, v: unknown) {
  mem[k] = v;
  if (!isBrowser()) return;
  if (v === null) window.sessionStorage.removeItem(key(k));
  else window.sessionStorage.setItem(key(k), JSON.stringify(v));
}

export const session = {
  setToken(kind: TokenKind, t: Stored | null) {
    write(`tok.${kind}`, t);
  },
  getToken(kind: TokenKind): { token: string; expired: boolean } | null {
    const t = read<Stored>(`tok.${kind}`);
    if (!t) return null;
    return { token: t.token, expired: new Date(t.expires_at).getTime() <= Date.now() };
  },
  setMeta(name: string, v: unknown) {
    write(`meta.${name}`, v);
  },
  getMeta<T>(name: string): T | null {
    return read<T>(`meta.${name}`);
  },
  clearAll() {
    for (const k of ["tok.access", "tok.customer", "tok.analyst", "meta.user", "meta.customer"]) write(k, null);
  },
};
