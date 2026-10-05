import type { UiLang } from "@/i18n/useT";

type Pair = [string, string];

const CLAIM: Record<string, Pair> = {
  "unrecognized charge": ["Cargo no reconocido", "Cobrança não reconhecida"],
  "improper charge": ["Cobro indebido", "Cobrança indevida"],
  "scam transfer": ["Transferencia por engaño", "Transferência por golpe"],
  "human request": ["Pidió una persona", "Pediu uma pessoa"],
};
const REASON: Record<string, Pair> = {
  fraud: ["fraude", "fraude"],
  "not received": ["no recibido", "não recebido"],
  "not as described": ["no corresponde a lo descrito", "não corresponde ao descrito"],
  "incorrect amount": ["monto incorrecto", "valor incorreto"],
  duplicate: ["cobro duplicado", "cobrança duplicada"],
  "cancelled recurring": ["suscripción ya cancelada", "assinatura já cancelada"],
  "bank charge": ["cargo del banco", "tarifa do banco"],
  "recognized by customer": ["reconocido por el cliente", "reconhecido pelo cliente"],
};
const TREASON: Record<string, Pair> = {
  "person requested": ["Pidió una persona", "Pediu uma pessoa"],
  coercion: ["Posible coacción", "Possível coação"],
  "not understood": ["No se entendió el caso", "O caso não foi entendido"],
  regulator: ["Menciona al regulador", "Menciona o regulador"],
  "scam transfer": ["Transferencia por engaño", "Transferência por golpe"],
  "tool failure": ["No se pudieron leer los registros", "Não foi possível ler os registros"],
  "turn limit": ["Límite de turnos", "Limite de turnos"],
  "lost card": ["Tarjeta perdida o robada", "Cartão perdido ou roubado"],
};
const PENDING: Record<string, Pair> = {
  "block card": ["bloqueo de tarjeta pendiente, no ejecutado", "bloqueio do cartão pendente, não executado"],
};

const FIXED: Record<string, Pair> = {
  "CO-payment-reversal": ["Reversión del pago (Decreto 587)", "Reversão do pagamento (Decreto 587)"],
  "CO-bank-complaint": ["Reclamo ante el banco", "Reclamação ao banco"],
  "MX-clarification": ["Aclaración (LTOSF, art. 23)", "Esclarecimento (LTOSF, art. 23)"],
  "AR-statement-challenge": ["Impugnación del resumen (Ley 25.065)", "Contestação da fatura (Lei 25.065)"],
  "AR-bank-complaint": ["Reclamo ante el banco", "Reclamação ao banco"],
  "SFC (jurisdictional route)": ["SFC (vía jurisdiccional)", "SFC (via jurisdicional)"],
  "bank specialized unit (UNE)": ["Unidad Especializada del banco (UNE)", "Unidade especializada do banco (UNE)"],
  "acknowledge the challenge": ["acusar recibo de la impugnación", "acusar o recebimento da contestação"],
  "answer the complaint": ["responder el reclamo", "responder à reclamação"],
  "challenge the statement": ["impugnar el resumen", "contestar a fatura"],
  "correct the error or explain the statement with evidence": ["corregir el error o explicar el resumen con pruebas", "corrigir o erro ou explicar a fatura com provas"],
  "deliver the opinion": ["entregar el dictamen", "entregar o parecer"],
  "file the clarification request": ["presentar la solicitud de aclaración", "apresentar o pedido de esclarecimento"],
  "refund the amounts": ["devolver los montos", "devolver os valores"],
  "resolve the complaint": ["resolver el reclamo", "resolver a reclamação"],
  "resolve the objection with reasons": ["resolver la objeción con fundamentos", "resolver a objeção com fundamentos"],
  "say whether the explanation is satisfactory": ["indicar si la explicación es satisfactoria", "indicar se a explicação é satisfatória"],
  "Visa (assumed from the BIN)": ["Visa (deducida del BIN)", "Visa (deduzida do BIN)"],
  "contractual network rule, not law; verify with the network rules through the issuer": [
    "Regla contractual de la red, no es ley; verificar con las reglas de la red a través del emisor",
    "Regra contratual da bandeira, não é lei; verificar com as regras da bandeira por meio do emissor",
  ],
  "literal text pending verification: informed without a date": ["Texto oficial pendiente de verificación: se informa sin fecha", "Texto oficial pendente de verificação: informado sem data"],
  "When did the customer last see the card?": ["¿Cuándo vio el cliente su tarjeta por última vez?", "Quando o cliente viu o cartão pela última vez?"],
  "Is the customer safe to talk now, and through which channel?": ["¿El cliente puede hablar con seguridad ahora, y por qué canal?", "O cliente pode falar com segurança agora, e por qual canal?"],
  "What happened, and which charge or account does the customer mean?": ["¿Qué pasó y a qué cargo o cuenta se refiere el cliente?", "O que aconteceu e a qual cobrança ou conta o cliente se refere?"],
  "What has the customer filed, or wants to file, with the regulator?": ["¿Qué presentó o quiere presentar el cliente ante el regulador?", "O que o cliente apresentou ou quer apresentar ao regulador?"],
  "How much was transferred, and to which account or person?": ["¿Cuánto se transfirió y a qué cuenta o persona?", "Quanto foi transferido e para qual conta ou pessoa?"],
  "The bank records could not be read: which charge does the customer mean?": ["No se pudieron leer los registros del banco: ¿a qué cargo se refiere el cliente?", "Não foi possível ler os registros do banco: a qual cobrança o cliente se refere?"],
  "What does the customer still need? The conversation did not converge.": ["¿Qué necesita todavía el cliente? La conversación no llegó a un cierre.", "Do que o cliente ainda precisa? A conversa não chegou a um fechamento."],
  "When was the transfer made?": ["¿Cuándo se hizo la transferencia?", "Quando a transferência foi feita?"],
  "How did the third party contact the customer?": ["¿Cómo contactó el tercero al cliente?", "Como o terceiro contatou o cliente?"],
  Food: ["Alimentación", "Alimentação"],
  Transport: ["Transporte", "Transporte"],
  Services: ["Servicios", "Serviços"],
  Other: ["Otros", "Outros"],
  Entertainment: ["Entretenimiento", "Entretenimento"],
  Health: ["Salud", "Saúde"],
};

const cap = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);
function pick(table: Record<string, Pair>, key: string, lang: UiLang, en = key) {
  const p = table[key];
  if (!p) return null;
  return lang === "es" ? p[0] : lang === "pt" ? p[1] : en;
}

export function fixedText(v: string, lang: UiLang): string | null {
  return pick(FIXED, v, lang);
}

const nCharges = (n: string, lang: UiLang, known: boolean) => {
  const one = n === "1";
  if (lang === "pt") return `${n} ${one ? "cobrança" : "cobranças"}${known ? (one ? " identificada" : " identificadas") : ""}`;
  if (lang === "en") return `${n} ${one ? "charge" : "charges"}${known ? " identified" : ""}`;
  return `${n} ${one ? "cargo" : "cargos"}${known ? (one ? " identificado" : " identificados") : ""}`;
};

/** The parts of a queue summary, as the API sends them in each queue item (codes, not words). */
export type SummaryParts = {
  kind: "case" | "transfer";
  claim_type?: string | null;
  reason: string;
  charge_count: number;
  pending_action?: string | null;
};

const words = (code: string) => code.replaceAll("_", " ");

/** The summary in the language of the console, or null when a part is not in the tables yet. */
export function describe(parts: SummaryParts, lang: UiLang): string | null {
  const count = String(parts.charge_count);
  if (parts.kind === "case") {
    const claim = words(parts.claim_type ?? "");
    const type = pick(CLAIM, claim, lang, cap(claim));
    const reason = pick(REASON, words(parts.reason), lang, words(parts.reason));
    if (!type || !reason) return null;
    const word = lang === "en" ? "reason" : "motivo";
    return `${type} · ${nCharges(count, lang, false)} · ${word}: ${reason}`;
  }
  const reason = pick(TREASON, words(parts.reason), lang, cap(words(parts.reason)));
  const claim = parts.claim_type && parts.claim_type !== parts.reason ? pick(CLAIM, words(parts.claim_type), lang, words(parts.claim_type)) : "";
  const pending = parts.pending_action ? pick(PENDING, words(parts.pending_action), lang, `${words(parts.pending_action)} pending, not run`) : "";
  if (!reason || claim === null || pending === null) return null;
  return [reason + (claim ? `: ${claim}` : ""), nCharges(count, lang, true), pending].filter(Boolean).join(" · ");
}

/** A queue item in the console's language: from its parts when the API sends them, else from its English summary. */
export function queueSummary(item: Partial<SummaryParts> & { kind: "case" | "transfer"; summary: string }, lang: UiLang): string {
  if (typeof item.reason === "string" && typeof item.charge_count === "number") {
    const described = describe(item as SummaryParts, lang);
    if (described) return described;
  }
  return translateSummary(item.summary, lang);
}

export function translateSummary(summary: string, lang: UiLang): string {
  const c = /^(.+?): (\d+) charge\(s\), reason (.+)$/.exec(summary);
  if (c) {
    const described = describe({ kind: "case", claim_type: c[1]!, reason: c[3]!, charge_count: Number(c[2]) }, lang);
    if (described) return described;
  }
  const t = /^(.+?)(?:: (.+?))?, (\d+) charge\(s\) known(?:, (.+?) pending and not run)?$/.exec(summary);
  if (t) {
    const described = describe(
      { kind: "transfer", reason: t[1]!, claim_type: t[2] ?? null, charge_count: Number(t[3]), pending_action: t[4] ?? null },
      lang,
    );
    if (described) return described;
  }
  return summary;
}
