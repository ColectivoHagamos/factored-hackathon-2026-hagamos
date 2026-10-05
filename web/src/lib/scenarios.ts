/** Scenario tags of the demo customers, as the demo subset names them (pipeline/demo.py). */

/** "A1_co_recent_domestic_purchase" belongs to the scenario code "A1". */
export const hasScenario = (tags: string[], code: string) => tags.some((tag) => tag === code || tag.startsWith(`${code}_`));

/** The tags a person reads: the segment already has its own field. */
export const visibleScenarios = (tags: string[]) => tags.filter((tag) => !tag.startsWith("segment_"));

/** The short reference of a demo customer: "CO-01" of "CO-01 · plus". */
export const shortAlias = (alias: string) => alias.split(" · ")[0] ?? alias;

/** The readable name of a tag, or the tag itself when the web does not know it yet. */
export function scenarioLabel(t: (key: string) => string, tag: string) {
  const key = `scenario.${tag}`;
  const label = t(key);
  return label === key ? tag : label;
}
