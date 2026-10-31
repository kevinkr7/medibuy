import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ChevronRight, GitBranch } from "lucide-react";
import { api, queryKeys } from "@/lib/api/client";
import type { AgreementResponse, SupplierResponse } from "@/lib/api/types";
import { formatDate, formatMoney, formatQty } from "@/lib/format";
import { EmptyBlock, ErrorBlock, LoadingBlock, Panel } from "./shared";
import { cn } from "@/lib/utils";

export function AgreementExplorer() {
  const agreements = useQuery({ queryKey: queryKeys.agreements, queryFn: api.agreements });
  const suppliers = useQuery({ queryKey: queryKeys.suppliers, queryFn: api.suppliers });
  const [open, setOpen] = useState<string | null>(null);

  const content = () => {
    if (agreements.isLoading || suppliers.isLoading)
      return <LoadingBlock label="Loading agreements…" />;
    const err = agreements.error ?? suppliers.error;
    if (err)
      return (
        <ErrorBlock
          error={err}
          onRetry={() => {
            agreements.refetch();
            suppliers.refetch();
          }}
        />
      );
    const list = agreements.data ?? [];
    if (!list.length) return <EmptyBlock label="No agreements on file." />;
    return (
      <ul className="divide-y">
        {list.map((a) => (
          <AgreementRow
            key={a.agreement_id}
            agreement={a}
            supplier={suppliers.data?.find(
              (s) => s.supplier_id === a.supplier_id && s.material_code === a.material_code,
            )}
            open={open === a.agreement_id}
            onToggle={() => setOpen(open === a.agreement_id ? null : a.agreement_id)}
          />
        ))}
      </ul>
    );
  };

  return (
    <Panel>
      <div className="hidden grid-cols-[1.6fr_1.2fr_1fr_0.8fr_0.7fr_0.6fr_24px] gap-4 border-b bg-surface px-5 py-2.5 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground lg:grid">
        <span>Supplier / material</span>
        <span>Agreement validity</span>
        <span className="text-right">Annual target</span>
        <span className="text-right">Rebate</span>
        <span className="text-right">Versions</span>
        <span />
        <span />
      </div>
      {content()}
    </Panel>
  );
}

function AgreementRow({
  agreement: a,
  supplier,
  open,
  onToggle,
}: {
  agreement: AgreementResponse;
  supplier: SupplierResponse | undefined;
  open: boolean;
  onToggle: () => void;
}) {
  return (
    <li>
      <button
        type="button"
        onClick={onToggle}
        aria-expanded={open}
        className="grid w-full grid-cols-[1fr_24px] items-center gap-4 px-5 py-4 text-left transition-colors hover:bg-surface focus-visible:bg-surface focus-visible:outline-none lg:grid-cols-[1.6fr_1.2fr_1fr_0.8fr_0.7fr_0.6fr_24px]"
      >
        <div>
          <p className="font-medium text-foreground">{supplier?.supplier_name ?? a.supplier_id}</p>
          <p className="text-xs text-muted-foreground">
            <span className="num">{a.agreement_id}</span> ·{" "}
            {supplier?.material_name ?? a.material_code}{" "}
            <span className="num">({a.material_code})</span>
          </p>
          <p className="mt-1 text-xs text-muted-foreground lg:hidden">
            {formatDate(a.valid_from)} – {formatDate(a.valid_to)} · Target{" "}
            {formatQty(a.annual_target_quantity, a.unit)} · {a.annual_rebate_percent}% rebate ·{" "}
            {a.versions.length} version{a.versions.length > 1 ? "s" : ""}
          </p>
        </div>
        <span className="hidden text-sm lg:block">
          {formatDate(a.valid_from)} – {formatDate(a.valid_to)}
        </span>
        <span className="num hidden text-right text-sm lg:block">
          {formatQty(a.annual_target_quantity, a.unit)}
        </span>
        <span className="num hidden text-right text-sm lg:block">{a.annual_rebate_percent}%</span>
        <span className="hidden justify-end lg:flex">
          <span
            className={cn(
              "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium",
              a.versions.length > 1
                ? "bg-accent text-accent-foreground"
                : "bg-muted text-muted-foreground",
            )}
          >
            <GitBranch className="h-3 w-3" />
            {a.versions.length}
          </span>
        </span>
        <span className="hidden lg:block" />
        <ChevronRight
          className={cn("h-4 w-4 text-muted-foreground transition-transform", open && "rotate-90")}
        />
      </button>
      {open && (
        <div className="border-t bg-surface px-5 py-5">
          <p className="mb-3 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
            Version history — one annual agreement
          </p>
          <ol className="relative space-y-4 border-l-2 border-border pl-5">
            {a.versions
              .slice()
              .sort((x, y) => x.version_number - y.version_number)
              .map((v) => (
                <li key={v.version_id} className="relative">
                  <span
                    className="absolute -left-[27px] top-4 h-3 w-3 rounded-full border-2 border-primary bg-card"
                    aria-hidden
                  />
                  <div className="rounded-md border bg-card">
                    <div className="flex flex-wrap items-baseline justify-between gap-2 border-b px-4 py-3">
                      <div>
                        <p className="text-sm font-semibold">
                          Version {v.version_number}{" "}
                          <span className="num text-xs font-normal text-muted-foreground">
                            {v.version_id}
                          </span>
                        </p>
                        <p className="text-xs text-muted-foreground">
                          Effective {formatDate(v.effective_from)} – {formatDate(v.effective_to)}
                        </p>
                      </div>
                      <p className="text-sm">
                        <span className="text-xs text-muted-foreground">Base price </span>
                        <span className="num font-semibold">
                          {formatMoney(v.base_unit_price, a.currency)}
                        </span>
                        <span className="text-xs text-muted-foreground"> / {a.unit}</span>
                      </p>
                    </div>
                    <p className="px-4 pt-3 text-xs text-muted-foreground">{v.change_note}</p>
                    <div className="overflow-x-auto px-4 pb-4 pt-3">
                      <table className="w-full min-w-[360px] text-sm">
                        <caption className="sr-only">
                          Quarterly quantity discount tiers for {v.version_id}
                        </caption>
                        <thead>
                          <tr className="text-left text-[11px] uppercase tracking-wider text-muted-foreground">
                            <th className="py-1.5 font-semibold">Tier</th>
                            <th className="py-1.5 font-semibold">Quarterly quantity</th>
                            <th className="py-1.5 text-right font-semibold">Discount</th>
                          </tr>
                        </thead>
                        <tbody>
                          {v.price_tiers.map((t, idx) => (
                            <tr key={t.tier_id} className="border-t">
                              <td className="py-1.5 text-muted-foreground">T{idx + 1}</td>
                              <td className="num py-1.5">
                                {t.max_quantity_exclusive === null
                                  ? `≥ ${formatQty(t.min_quantity_inclusive)} ${a.unit}`
                                  : `${formatQty(t.min_quantity_inclusive)} – <${formatQty(t.max_quantity_exclusive)} ${a.unit}`}
                              </td>
                              <td className="num py-1.5 text-right font-medium">
                                {t.discount_percent}%
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                </li>
              ))}
          </ol>
        </div>
      )}
    </li>
  );
}
