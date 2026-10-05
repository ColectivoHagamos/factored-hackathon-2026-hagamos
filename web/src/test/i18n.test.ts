import { describe, expect, it } from "vitest";

import en from "@/i18n/en.json";
import es from "@/i18n/es.json";
import pt from "@/i18n/pt.json";

const dictionaries: Record<string, Record<string, string>> = { es, en, pt };

describe("translations", () => {
  it("cover the same keys in Spanish, English and Portuguese", () => {
    const keys = Object.keys(es).sort();
    expect(Object.keys(en).sort()).toEqual(keys);
    expect(Object.keys(pt).sort()).toEqual(keys);
  });

  it("never leave a text empty", () => {
    for (const [lang, dictionary] of Object.entries(dictionaries)) {
      const empty = Object.entries(dictionary).filter(([, text]) => !text.trim());
      expect(empty, lang).toEqual([]);
    }
  });

  it("speak of a product and its clients, not of a contest", () => {
    for (const dictionary of Object.values(dictionaries)) {
      for (const text of Object.values(dictionary)) {
        expect(text).not.toMatch(/jurado|\bjury\b|júri|hackat/i);
      }
    }
  });
});
