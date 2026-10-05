import { describe, expect, it } from "vitest";

import es from "@/i18n/es.json";
import { hasScenario, scenarioLabel, shortAlias, visibleScenarios } from "@/lib/scenarios";

const t = (key: string) => (es as Record<string, string>)[key] ?? key;

describe("scenarios", () => {
  it("match a code by the prefix of the tag the demo subset uses", () => {
    expect(hasScenario(["A1_co_recent_domestic_purchase"], "A1")).toBe(true);
    expect(hasScenario(["A10_bank_adjustment"], "A1")).toBe(false);
    expect(hasScenario(["A10_bank_adjustment"], "A10")).toBe(true);
  });

  it("show readable names, hide the segment and keep an unknown tag as it is", () => {
    expect(visibleScenarios(["segment_plus", "A2_pending_purchase"])).toEqual(["A2_pending_purchase"]);
    expect(scenarioLabel(t, "A2_pending_purchase")).toBe("Compra pendiente");
    expect(scenarioLabel(t, "a_new_tag")).toBe("a_new_tag");
  });

  it("shorten the alias of a demo customer", () => {
    expect(shortAlias("AR-01 · plus")).toBe("AR-01");
  });
});
