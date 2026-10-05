import { describe, expect, it } from "vitest";

import { dateLong, money, toDate } from "@/lib/format";

describe("money", () => {
  it("shows the currency code and the separators of its country, as VERA writes it", () => {
    expect(money("320000", "COP")).toBe("COP 320.000");
    expect(money("12500", "ARS")).toBe("ARS 12.500");
    expect(money("45.9", "USD")).toBe("USD 45,90");
  });

  it("keeps the raw text when the amount is not a number", () => {
    expect(money("n/a", "COP")).toBe("COP n/a");
  });
});

describe("dates", () => {
  it("read a legal deadline as the calendar day it names, in any time zone", () => {
    const day = toDate("2026-07-03");
    expect([day.getFullYear(), day.getMonth() + 1, day.getDate()]).toEqual([2026, 7, 3]);
    expect(dateLong("2026-07-03", "es-CO")).toBe("3 de julio de 2026");
  });
});
