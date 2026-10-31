import { useQuery } from "@tanstack/react-query";
import { api, queryKeys } from "@/lib/api/client";
import { formatMoney, formatQty } from "@/lib/format";
import { ErrorBlock, Panel } from "./shared";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

export function DashboardSummary({ currency }: { currency: string }) {
  const q = useQuery({ queryKey: queryKeys.dashboard, queryFn: api.dashboard });

  if (q.isError) {
    return (
      <Panel>
        <ErrorBlock error={q.error} onRetry={() => q.refetch()} />
      </Panel>
    );
  }
  const d = q.data;
  const cards: {
    label: string;
    value: string | undefined;
    hint?: string | undefined;
    tone?: string | undefined;
  }[] = [
    { label: "Suppliers", value: d && formatQty(d.total_suppliers) },
    { label: "Agreements", value: d && formatQty(d.total_agreements) },
    { label: "Purchase orders", value: d && formatQty(d.total_purchase_orders) },
    {
      label: "Total overcharge",
      value: d && formatMoney(d.total_overcharge_amount, currency),
      hint: d && `${d.overcharged_purchase_orders} POs above contract`,
      tone: "text-danger",
    },
    {
      label: "Total undercharge",
      value: d && formatMoney(d.total_undercharge_amount, currency),
      hint: d && `${d.undercharged_purchase_orders} POs below contract`,
      tone: "text-info",
    },
    {
      label: "Earned rebate",
      value: d && formatMoney(d.total_earned_rebate, currency),
      hint: d && `on ${formatMoney(d.total_eligible_contract_value, currency)} eligible value`,
      tone: "text-primary",
    },
  ];

  return (
    <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
      {cards.map((c, i) => (
        <Panel
          key={c.label}
          className={cn(
            "flex min-h-[112px] flex-col justify-between p-4",
            i === 3 && "xl:border-l-4 xl:border-l-danger/40",
            i === 5 && "border-l-4 border-l-primary",
          )}
        >
          <p className="text-xs font-medium text-muted-foreground">{c.label}</p>
          {c.value === undefined ? (
            <Skeleton className="h-7 w-24" />
          ) : (
            <p className={cn("num text-xl font-semibold text-foreground sm:text-2xl", c.tone)}>
              {c.value}
            </p>
          )}
          <p className="min-h-4 text-[11px] text-muted-foreground">{c.hint ?? ""}</p>
        </Panel>
      ))}
    </div>
  );
}
