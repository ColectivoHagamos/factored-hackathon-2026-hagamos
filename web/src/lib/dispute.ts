import type { Lang, Movement } from "@/api/types";
import { dateLong, money } from "./format";

const loc = (l: Lang) => (l === "pt" ? "pt-BR" : "es-CO");

export function disputeMessage(m: Movement, lang: Lang) {
  if (m.kind === "bank_adjustment") {
    return lang === "pt" ? "Fui cobrado por um ajuste que não procede" : "Me cobraron un ajuste que no corresponde";
  }
  const amount = money(m.amount, m.currency);
  const date = dateLong(m.occurred_at, loc(lang));
  return lang === "pt"
    ? `Não reconheço a cobrança de ${m.merchant} por ${amount} em ${date}`
    : `No reconozco el cargo de ${m.merchant} por ${amount} del ${date}`;
}

export const humanMessage = (lang: Lang) => (lang === "pt" ? "Quero falar com uma pessoa" : "Quiero hablar con una persona");
