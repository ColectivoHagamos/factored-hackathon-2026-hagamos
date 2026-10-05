import { describe, expect, it } from "vitest";

import { queueSummary, translateSummary } from "@/lib/analyst-text";

describe("translateSummary", () => {
  it("reads a case summary of the API in the language of the console", () => {
    const summary = "unrecognized charge: 3 charge(s), reason fraud";
    expect(translateSummary(summary, "es")).toBe("Cargo no reconocido · 3 cargos · motivo: fraude");
    expect(translateSummary(summary, "pt")).toContain("Cobrança não reconhecida");
  });

  it("reads a transfer summary, with the action left pending", () => {
    expect(translateSummary("person requested, 0 charge(s) known", "es")).toBe("Pidió una persona · 0 cargos identificados");
    const pending = translateSummary("lost card, 1 charge(s) known, block card pending and not run", "es");
    expect(pending).toContain("bloqueo de tarjeta pendiente");
  });

  it("leaves an unknown text as the API wrote it", () => {
    expect(translateSummary("something new", "es")).toBe("something new");
  });
});

describe("translateSummary with a reason code", () => {
  it("reads a reason written with underscores, as the API sends it", () => {
    expect(translateSummary("improper charge: 1 charge(s), reason bank_charge", "es")).toBe("Cobro indebido · 1 cargo · motivo: cargo del banco");
  });
});

describe("queueSummary", () => {
  it("reads the parts the API sends, in the language of the console", () => {
    const item = { kind: "case" as const, summary: "x", claim_type: "unrecognized_charge", reason: "fraud", charge_count: 3 };
    expect(queueSummary(item, "es")).toBe("Cargo no reconocido · 3 cargos · motivo: fraude");
    const transfer = { kind: "transfer" as const, summary: "x", claim_type: null, reason: "lost_card", charge_count: 1, pending_action: "block_card" as const };
    expect(queueSummary(transfer, "es")).toBe("Tarjeta perdida o robada · 1 cargo identificado · bloqueo de tarjeta pendiente, no ejecutado");
  });

  it("falls back to the English summary of an older item", () => {
    expect(queueSummary({ kind: "case", summary: "unrecognized charge: 2 charge(s), reason fraud" }, "pt")).toBe(
      "Cobrança não reconhecida · 2 cobranças · motivo: fraude",
    );
  });
});
