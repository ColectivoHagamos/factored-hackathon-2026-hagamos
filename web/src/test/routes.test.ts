import { createMemoryHistory, createRouter, rootRouteId } from "@tanstack/react-router";
import { describe, expect, it } from "vitest";

import { routeTree } from "@/routeTree.gen";

describe("routes", () => {
  it.each(["/", "/login", "/clientes", "/banca", "/chat", "/analista"])("%s is a page of the app", (path) => {
    const router = createRouter({ routeTree, history: createMemoryHistory({ initialEntries: [path] }) });
    expect(router.matchRoutes(path).at(-1)?.routeId).not.toBe(rootRouteId);
  });
});
