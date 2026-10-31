import { useQuery } from "@tanstack/react-query";
import { CheckCircle2, CircleDashed } from "lucide-react";
import { api, queryKeys } from "@/lib/api/client";
import { formatDate, formatMoney, formatQty } from "@/lib/format";
import { EmptyBlock, ErrorBlock, LoadingBlock, Panel } from "./shared";
import { cn } from "@/lib/utils";

export function RebateSummary({ year }: { year: number }) {
  const q = useQuery({ queryKey: queryKeys.rebates(year), queryFn: () => api.rebates(year) });
  const suppliers = useQuery({ queryKey: queryKeys.suppliers, queryFn: api.suppliers });
  const name = (id: string) =>
    suppliers.data?.find((s) => s.supplier_id === id)?.supplier_name ?? id;

  if (q.isLoading)
    return (
      <Panel>
        <LoadingBlock label="Loading rebate summary…" />
      </Panel>
    );
  if (q.isError)
    return (
      <Panel>
        <ErrorBlock error={q.error} onRetry={() => q.refetch()} />
      </Panel>
    );
  const r = q.data!;
  const currency = r.currency ?? "INR";

  return (
    <div className="grid gap-4 lg:grid-cols-[280px_1fr]">
      <Panel className="flex flex-col justify-between bg-navy p-5 text-navy-foreground">
        <div>
          <p className="text-xs font-medium uppercase tracking-wider opacity-70">
            Earned rebate · {r.year}
          </p>
          <p className="num mt-3 text-3xl font-semibold">
            {formatMoney(r.total_rebate_earned, currency)}
          </p>
        </div>
        <p className="mt-6 text-xs opacity-70">
          Earned on qualifying annual volume. Payment and claim settlement are not tracked.
        </p>
      </Panel>

      <Panel>
        {!r.rebates.length ? (
          <EmptyBlock label={`No rebate data for ${r.year}.`} />
        ) : (
          <ul className="divide-y">
            {r.rebates.map((b) => {
              // Visual progress width only — eligibility comes from target_met.
              const pct =
                b.annual_target_quantity > 0
                  ? Math.min(100, (b.annual_purchased_quantity / b.annual_target_quantity) * 100)
                  : 0;
              return (
                <li key={b.agreement_id} className="grid gap-4 p-5 md:grid-cols-[1.3fr_1.4fr_1fr]">
                  <div>
                    <p className="font-medium">{name(b.supplier_id)}</p>
                    <p className="num text-xs text-muted-foreground">{b.agreement_id}</p>
                    <span
                      className={cn(
                        "mt-2 inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-semibold",
                        b.target_met
                          ? "bg-success-soft text-success"
                          : "bg-muted text-muted-foreground",
                      )}
                    >
                      {b.target_met ? (
                        <CheckCircle2 className="h-3 w-3" />
                      ) : (
                        <CircleDashed className="h-3 w-3" />
                      )}
                      {b.target_met ? "Target achieved" : "Target not achieved"}
                    </span>
                  </div>
                  <div>
                    <div className="flex justify-between text-xs text-muted-foreground">
                      <span>Annual quantity</span>
                      <span className="num">
                        <span className="font-semibold text-foreground">
                          {formatQty(b.annual_purchased_quantity)}
                        </span>{" "}
                        / {formatQty(b.annual_target_quantity)}
                      </span>
                    </div>
                    <div
                      className="mt-2 h-2 overflow-hidden rounded-full bg-muted"
                      role="progressbar"
                      aria-valuemin={0}
                      aria-valuemax={b.annual_target_quantity}
                      aria-valuenow={b.annual_purchased_quantity}
                      aria-label={`${name(b.supplier_id)} progress toward annual target`}
                    >
                      <div
                        className={cn(
                          "h-full rounded-full",
                          b.target_met ? "bg-primary" : "bg-muted-foreground/50",
                        )}
                        style={{ width: `${pct}%` }}
                      />
                    </div>
                    <p className="mt-2 text-xs text-muted-foreground">
                      {b.target_first_met_by_po ? (
                        <>
                          First triggered by{" "}
                          <span className="num font-medium text-foreground">
                            {b.target_first_met_by_po}
                          </span>{" "}
                          on {formatDate(b.target_first_met_on)}
                        </>
                      ) : (
                        "Target not yet triggered"
                      )}
                    </p>
                  </div>
                  <dl className="grid grid-cols-2 gap-x-3 gap-y-1 text-xs md:text-right">
                    <dt className="text-muted-foreground">Eligible value</dt>
                    <dd className="num">{formatMoney(b.eligible_contract_value, currency)}</dd>
                    <dt className="text-muted-foreground">Rebate rate</dt>
                    <dd className="num">{b.rebate_percent}%</dd>
                    <dt className="text-muted-foreground">Earned rebate</dt>
                    <dd className="num text-sm font-semibold text-primary">
                      {formatMoney(b.rebate_earned, currency)}
                    </dd>
                  </dl>
                </li>
              );
            })}
          </ul>
        )}
      </Panel>
    </div>
  );
}
