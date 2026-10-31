import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Search } from "lucide-react";
import { api, queryKeys } from "@/lib/api/client";
import type { PurchaseOrderPricingResponse, PricingStatus } from "@/lib/api/types";
import { formatDate, formatMoney, formatQty, isNegative } from "@/lib/format";
import { DefRow, EmptyBlock, ErrorBlock, LoadingBlock, Panel, StatusBadge } from "./shared";
import { Input } from "@/components/ui/input";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { cn } from "@/lib/utils";

const FILTERS: ("ALL" | PricingStatus)[] = ["ALL", "MATCH", "OVERCHARGED", "UNDERCHARGED"];

export function Variance({ value, currency }: { value: string; currency: string }) {
  const neg = isNegative(value);
  const zero = /^[-+]?0*\.?0*$/.test(value.trim());
  return (
    <span className={cn("num", zero ? "text-muted-foreground" : neg ? "text-info" : "text-danger")}>
      {formatMoney(value, currency, { signed: true })}
    </span>
  );
}

export function PurchaseOrders() {
  const pos = useQuery({ queryKey: queryKeys.purchaseOrders, queryFn: api.purchaseOrders });
  const suppliers = useQuery({ queryKey: queryKeys.suppliers, queryFn: api.suppliers });
  const [term, setTerm] = useState("");
  const [filter, setFilter] = useState<(typeof FILTERS)[number]>("ALL");
  const [selected, setSelected] = useState<string | null>(null);

  const supplierName = (id: string) =>
    suppliers.data?.find((s) => s.supplier_id === id)?.supplier_name ?? id;

  const rows = useMemo(() => {
    const t = term.trim().toLowerCase();
    return (pos.data ?? []).filter((p) => {
      if (filter !== "ALL" && p.status !== filter) return false;
      if (!t) return true;
      const name =
        suppliers.data?.find((s) => s.supplier_id === p.supplier_id)?.supplier_name ?? "";
      return [
        p.po_id,
        p.supplier_id,
        name,
        p.material_code,
        p.agreement_version_id,
        p.purchase_date,
      ]
        .join(" ")
        .toLowerCase()
        .includes(t);
    });
  }, [pos.data, suppliers.data, term, filter]);

  return (
    <Panel>
      <div className="flex flex-col gap-3 border-b px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="relative w-full sm:max-w-xs">
          <Search className="pointer-events-none absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            aria-label="Search purchase orders"
            placeholder="Search PO, supplier, material…"
            value={term}
            onChange={(e) => setTerm(e.target.value)}
            className="pl-8"
          />
        </div>
        <div className="flex flex-wrap gap-1" role="group" aria-label="Filter by status">
          {FILTERS.map((f) => (
            <button
              key={f}
              type="button"
              aria-pressed={filter === f}
              onClick={() => setFilter(f)}
              className={cn(
                "rounded-md px-2.5 py-1 text-xs font-medium transition-colors",
                filter === f
                  ? "bg-navy text-navy-foreground"
                  : "text-muted-foreground hover:bg-muted",
              )}
            >
              {f === "ALL" ? "All" : f.charAt(0) + f.slice(1).toLowerCase()}
            </button>
          ))}
        </div>
      </div>

      {pos.isLoading ? (
        <LoadingBlock label="Loading purchase orders…" />
      ) : pos.isError ? (
        <ErrorBlock error={pos.error} onRetry={() => pos.refetch()} />
      ) : !rows.length ? (
        <EmptyBlock
          label={
            pos.data?.length ? "No purchase orders match your search." : "No purchase orders yet."
          }
        />
      ) : (
        <>
          {/* Desktop table */}
          <div className="hidden overflow-x-auto md:block">
            <table className="w-full text-sm">
              <thead className="bg-surface text-left text-[11px] uppercase tracking-wider text-muted-foreground">
                <tr>
                  <th className="px-4 py-2.5 font-semibold">PO</th>
                  <th className="px-3 py-2.5 font-semibold">Supplier / material</th>
                  <th className="px-3 py-2.5 font-semibold">Date</th>
                  <th className="px-3 py-2.5 text-right font-semibold">Qty</th>
                  <th className="px-3 py-2.5 text-right font-semibold">Entered</th>
                  <th className="px-3 py-2.5 text-right font-semibold">Contract</th>
                  <th className="px-3 py-2.5 font-semibold">Version</th>
                  <th className="px-3 py-2.5 text-right font-semibold">Disc.</th>
                  <th className="px-3 py-2.5 text-right font-semibold">Variance</th>
                  <th className="px-4 py-2.5 font-semibold">Status</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((p) => (
                  <tr
                    key={p.po_id}
                    tabIndex={0}
                    onClick={() => setSelected(p.po_id)}
                    onKeyDown={(e) =>
                      (e.key === "Enter" || e.key === " ") &&
                      (e.preventDefault(), setSelected(p.po_id))
                    }
                    className="cursor-pointer border-t transition-colors hover:bg-surface focus-visible:bg-accent focus-visible:outline-none"
                  >
                    <td className="num px-4 py-3 font-semibold">{p.po_id}</td>
                    <td className="px-3 py-3">
                      <div className="font-medium">{supplierName(p.supplier_id)}</div>
                      <div className="num text-xs text-muted-foreground">{p.material_code}</div>
                    </td>
                    <td className="whitespace-nowrap px-3 py-3">{formatDate(p.purchase_date)}</td>
                    <td className="num px-3 py-3 text-right">{formatQty(p.quantity)}</td>
                    <td className="num px-3 py-3 text-right">
                      {formatMoney(p.entered_unit_price, p.currency)}
                    </td>
                    <td className="num px-3 py-3 text-right font-medium">
                      {formatMoney(p.correct_unit_price, p.currency)}
                    </td>
                    <td className="num px-3 py-3 text-xs text-muted-foreground">
                      {p.agreement_version_id}
                    </td>
                    <td className="num px-3 py-3 text-right">{p.tier_discount_percent}%</td>
                    <td className="px-3 py-3 text-right">
                      <Variance value={p.variance_amount} currency={p.currency} />
                    </td>
                    <td className="px-4 py-3">
                      <StatusBadge status={p.status} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {/* Mobile cards */}
          <ul className="divide-y md:hidden">
            {rows.map((p) => (
              <li key={p.po_id}>
                <button
                  type="button"
                  onClick={() => setSelected(p.po_id)}
                  className="w-full px-4 py-3 text-left hover:bg-surface"
                >
                  <div className="flex items-center justify-between">
                    <span className="num font-semibold">{p.po_id}</span>
                    <StatusBadge status={p.status} />
                  </div>
                  <p className="mt-1 text-sm">
                    {supplierName(p.supplier_id)} ·{" "}
                    <span className="num text-xs">{p.material_code}</span>
                  </p>
                  <div className="mt-1 flex justify-between text-xs text-muted-foreground">
                    <span>
                      {formatDate(p.purchase_date)} · {formatQty(p.quantity)} @{" "}
                      {formatMoney(p.entered_unit_price, p.currency)}
                    </span>
                    <Variance value={p.variance_amount} currency={p.currency} />
                  </div>
                </button>
              </li>
            ))}
          </ul>
        </>
      )}

      <PoDetailSheet
        poId={selected}
        supplierName={selected ? supplierName : undefined}
        onClose={() => setSelected(null)}
      />
    </Panel>
  );
}

function PoDetailSheet({
  poId,
  supplierName,
  onClose,
}: {
  poId: string | null;
  supplierName: ((id: string) => string) | undefined;
  onClose: () => void;
}) {
  const q = useQuery({
    queryKey: queryKeys.poPrice(poId ?? ""),
    queryFn: () => api.purchaseOrderPrice(poId!),
    enabled: !!poId,
  });
  return (
    <Sheet open={!!poId} onOpenChange={(o) => !o && onClose()}>
      <SheetContent className="w-full overflow-y-auto sm:max-w-md">
        <SheetHeader>
          <SheetTitle className="num">{poId}</SheetTitle>
          <SheetDescription>
            Pricing verification from GET /purchase-orders/{"{po_id}"}/price
          </SheetDescription>
        </SheetHeader>
        <div className="mt-4 px-4 pb-6">
          {q.isLoading ? (
            <LoadingBlock />
          ) : q.isError ? (
            <ErrorBlock error={q.error} onRetry={() => q.refetch()} />
          ) : q.data ? (
            <PricingDetail po={q.data} supplierName={supplierName?.(q.data.supplier_id)} />
          ) : null}
        </div>
      </SheetContent>
    </Sheet>
  );
}

export function PricingDetail({
  po,
  supplierName,
}: {
  po: PurchaseOrderPricingResponse;
  supplierName: string | undefined;
}) {
  const c = po.currency;
  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between rounded-md border bg-surface p-3">
        <div>
          <p className="text-xs text-muted-foreground">Signed variance (entered − contract)</p>
          <p className="text-lg font-semibold">
            <Variance value={po.variance_amount} currency={c} />
          </p>
        </div>
        <StatusBadge status={po.status} />
      </div>
      <div>
        <p className="mb-1 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
          Order
        </p>
        <dl>
          <DefRow label="Supplier">
            {supplierName ?? po.supplier_id}{" "}
            <span className="num text-xs text-muted-foreground">({po.supplier_id})</span>
          </DefRow>
          <DefRow label="Material">
            <span className="num">{po.material_code}</span>
          </DefRow>
          <DefRow label="Purchase date">{formatDate(po.purchase_date)}</DefRow>
          <DefRow label="Quantity">
            <span className="num">{formatQty(po.quantity)}</span>
          </DefRow>
          <DefRow label="Currency">{c}</DefRow>
        </dl>
      </div>
      <div>
        <p className="mb-1 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
          Contract terms applied
        </p>
        <dl>
          <DefRow label="Agreement">
            <span className="num">{po.agreement_id}</span>
          </DefRow>
          <DefRow label="Version">
            <span className="num">{po.agreement_version_id}</span>
          </DefRow>
          <DefRow label="Quarter">{po.quarter}</DefRow>
          <DefRow label="Quarter qty before → after">
            <span className="num">
              {formatQty(po.quarter_quantity_before_po)} → {formatQty(po.quarter_quantity_after_po)}
            </span>
          </DefRow>
          <DefRow label="Annual qty after PO">
            <span className="num">{formatQty(po.annual_quantity_after_po)}</span>
          </DefRow>
          <DefRow label="Tier discount">
            <span className="num">{po.tier_discount_percent}%</span>
          </DefRow>
        </dl>
      </div>
      <div>
        <p className="mb-1 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
          Pricing
        </p>
        <dl>
          <DefRow label="Base unit price">
            <span className="num">{formatMoney(po.base_unit_price, c)}</span>
          </DefRow>
          <DefRow label="Buyer-entered unit price">
            <span className="num">{formatMoney(po.entered_unit_price, c)}</span>
          </DefRow>
          <DefRow label="Correct contract unit price">
            <span className="num">{formatMoney(po.correct_unit_price, c)}</span>
          </DefRow>
          <DefRow label="Entered line amount">
            <span className="num">{formatMoney(po.entered_line_amount, c)}</span>
          </DefRow>
          <DefRow label="Correct line amount">
            <span className="num">{formatMoney(po.correct_line_amount, c)}</span>
          </DefRow>
        </dl>
      </div>
      <div className="rounded-md border border-primary/30 bg-accent/50 p-3">
        <p className="mb-1 text-[11px] font-semibold uppercase tracking-wider text-accent-foreground">
          Rebate (separate from pricing)
        </p>
        <dl>
          <DefRow label="Annual earned rebate after PO">
            <span className="num">{formatMoney(po.annual_rebate_earned_after_po, c)}</span>
          </DefRow>
          <DefRow label="Rebate unlocked by this PO">
            <span className="num">{formatMoney(po.rebate_newly_unlocked_by_po, c)}</span>
          </DefRow>
        </dl>
      </div>
    </div>
  );
}
