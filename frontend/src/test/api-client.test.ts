import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { api, API_BASE_URL } from "@/lib/api/client";
import type { PurchaseOrderCreate } from "@/lib/api/types";

const po: PurchaseOrderCreate = {
  po_id: "P16",
  supplier_id: "S1",
  material_code: "RESIN-MED",
  purchase_date: "2025-08-03",
  quantity: 50,
  entered_unit_price: "110.00",
  currency: "INR",
};

describe("MediBuy API client contract", () => {
  const fetchMock = vi.fn(async (_input: RequestInfo | URL, _init?: RequestInit) =>
    Promise.resolve(
      new Response("{}", {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    ),
  );

  beforeEach(() => {
    fetchMock.mockClear();
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => vi.unstubAllGlobals());

  it("uses the configured local backend and every documented route", async () => {
    await api.health();
    await api.suppliers();
    await api.agreements();
    await api.purchaseOrders();
    await api.purchaseOrderPrice("P 06");
    await api.rebates(2025);
    await api.dashboard();
    await api.createPurchaseOrder(po);

    expect(API_BASE_URL).toBe("http://127.0.0.1:8000");
    expect(fetchMock.mock.calls.map(([url]) => url)).toEqual([
      `${API_BASE_URL}/health`,
      `${API_BASE_URL}/suppliers`,
      `${API_BASE_URL}/agreements`,
      `${API_BASE_URL}/purchase-orders`,
      `${API_BASE_URL}/purchase-orders/P%2006/price`,
      `${API_BASE_URL}/rebates/2025`,
      `${API_BASE_URL}/dashboard`,
      `${API_BASE_URL}/purchase-orders`,
    ]);

    const postOptions = fetchMock.mock.calls.at(-1)?.[1];
    expect(postOptions).toMatchObject({
      method: "POST",
      headers: { Accept: "application/json", "Content-Type": "application/json" },
    });
    expect(JSON.parse(String(postOptions?.body))).toEqual(po);
  });

  it("covers exactly the method/path operations in the exported OpenAPI document", () => {
    const openapi = JSON.parse(
      readFileSync(resolve(process.cwd(), "../frontend_handoff/openapi.json"), "utf-8"),
    ) as { paths: Record<string, Record<string, unknown>> };
    const operations = Object.entries(openapi.paths)
      .flatMap(([path, methods]) =>
        Object.keys(methods).map((method) => `${method.toUpperCase()} ${path}`),
      )
      .sort();

    expect(operations).toEqual(
      [
        "GET /agreements",
        "GET /dashboard",
        "GET /health",
        "GET /purchase-orders",
        "GET /purchase-orders/{po_id}/price",
        "GET /rebates/{year}",
        "GET /suppliers",
        "POST /purchase-orders",
      ].sort(),
    );
  });
});
