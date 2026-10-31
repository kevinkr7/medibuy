import type {
  AgreementResponse,
  AnnualRebateReportResponse,
  DashboardResponse,
  HealthResponse,
  PurchaseOrderCreate,
  PurchaseOrderPricingResponse,
  SupplierResponse,
} from "./types";

export const API_BASE_URL = (
  (import.meta.env["VITE_API_BASE_URL"] as string | undefined) ?? "http://127.0.0.1:8000"
).replace(/\/$/, "");

export class ApiError extends Error {
  status: number;
  code: string;
  details: unknown[] | undefined;
  constructor(status: number, code: string, message: string, details?: unknown[]) {
    super(message);
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

/** Thrown when the backend cannot be reached at all (offline, CORS, wrong URL). */
export class NetworkError extends Error {
  constructor() {
    super(`Backend unavailable at ${API_BASE_URL}`);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE_URL}${path}`, {
      ...init,
      headers: { Accept: "application/json", ...(init?.headers ?? {}) },
    });
  } catch {
    throw new NetworkError();
  }
  let payload: unknown = null;
  try {
    payload = await res.json();
  } catch {
    payload = null;
  }
  if (!res.ok) {
    const env = payload as {
      error?: { code?: string; message?: string; details?: unknown[] };
    } | null;
    throw new ApiError(
      res.status,
      env?.error?.code ?? `http_${res.status}`,
      env?.error?.message ?? `Request failed (${res.status})`,
      env?.error?.details,
    );
  }
  return payload as T;
}

export const api = {
  health: () => request<HealthResponse>("/health"),
  suppliers: () => request<SupplierResponse[]>("/suppliers"),
  agreements: () => request<AgreementResponse[]>("/agreements"),
  purchaseOrders: () => request<PurchaseOrderPricingResponse[]>("/purchase-orders"),
  purchaseOrderPrice: (poId: string) =>
    request<PurchaseOrderPricingResponse>(`/purchase-orders/${encodeURIComponent(poId)}/price`),
  createPurchaseOrder: (body: PurchaseOrderCreate) =>
    request<PurchaseOrderPricingResponse>("/purchase-orders", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  rebates: (year: number) => request<AnnualRebateReportResponse>(`/rebates/${year}`),
  dashboard: () => request<DashboardResponse>("/dashboard"),
};

export const queryKeys = {
  suppliers: ["suppliers"] as const,
  agreements: ["agreements"] as const,
  purchaseOrders: ["purchase-orders"] as const,
  poPrice: (id: string) => ["purchase-orders", id, "price"] as const,
  rebates: (year: number) => ["rebates", year] as const,
  dashboard: ["dashboard"] as const,
};
