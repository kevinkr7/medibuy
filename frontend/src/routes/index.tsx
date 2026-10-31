import { createFileRoute } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { api, API_BASE_URL } from "@/lib/api/client";
import { BrandMark, Section } from "@/components/medibuy/shared";
import { DashboardSummary } from "@/components/medibuy/DashboardSummary";
import { AgreementExplorer } from "@/components/medibuy/AgreementExplorer";
import { PurchaseOrders } from "@/components/medibuy/PurchaseOrders";
import { NewPurchaseOrder } from "@/components/medibuy/NewPurchaseOrder";
import { RebateSummary } from "@/components/medibuy/RebateSummary";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "MediBuy — Procurement Agreements & Rebate Tracking" },
      {
        name: "description",
        content:
          "Verify purchase order pricing against supplier agreements and track earned annual rebates.",
      },
      { property: "og:title", content: "MediBuy — Procurement Agreements & Rebate Tracking" },
      {
        property: "og:description",
        content: "Verify PO pricing against contract tiers and track earned supplier rebates.",
      },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: Index,
});

const REBATE_YEAR = 2025;
const NAV = [
  { id: "summary", label: "Summary" },
  { id: "agreements", label: "Agreements" },
  { id: "orders", label: "Purchase orders" },
  { id: "rebates", label: "Rebates" },
];

function Index() {
  const health = useQuery({
    queryKey: ["health"],
    queryFn: api.health,
    retry: 0,
    refetchInterval: 30000,
  });
  const status = health.isLoading ? "checking" : health.isSuccess ? "online" : "offline";

  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-30 border-b bg-card/90 backdrop-blur">
        <div className="mx-auto flex max-w-7xl items-center gap-6 px-4 py-3 sm:px-6">
          <div className="flex items-center gap-2.5">
            <BrandMark />
            <div className="leading-tight">
              <p className="text-base font-semibold tracking-tight">MediBuy</p>
              <p className="hidden text-[11px] text-muted-foreground sm:block">
                Procurement & rebates
              </p>
            </div>
          </div>
          <nav className="hidden flex-1 items-center gap-1 md:flex" aria-label="Sections">
            {NAV.map((n) => (
              <a
                key={n.id}
                href={`#${n.id}`}
                className="rounded-md px-3 py-1.5 text-sm text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
              >
                {n.label}
              </a>
            ))}
          </nav>
          <div
            className="ml-auto flex items-center gap-2 text-xs text-muted-foreground"
            title={API_BASE_URL}
          >
            <span
              className={cn(
                "h-2 w-2 rounded-full",
                status === "online"
                  ? "bg-success"
                  : status === "offline"
                    ? "bg-destructive"
                    : "bg-muted-foreground",
              )}
              aria-hidden
            />
            <span>
              {status === "online"
                ? "API connected"
                : status === "offline"
                  ? "Backend unavailable"
                  : "Checking API…"}
            </span>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-7xl space-y-14 px-4 py-8 sm:px-6 sm:py-10">
        <Section
          id="summary"
          eyebrow="Overview"
          title="Procurement summary"
          description={`Portfolio totals reported by the MediBuy backend. Pricing discrepancies and earned rebates are shown separately.`}
        >
          <DashboardSummary currency="INR" />
        </Section>

        <Section
          id="agreements"
          eyebrow="Contracts"
          title="Agreement explorer"
          description="Annual supplier agreements with dated amendment versions and quarterly discount tiers. Expand a row for version history."
        >
          <AgreementExplorer />
        </Section>

        <Section
          id="orders"
          eyebrow="Verification"
          title="Purchase order verification"
          description="Buyer-entered prices compared with the contract price for the version and tier in effect. Select a row for full detail."
          actions={<NewPurchaseOrder />}
        >
          <PurchaseOrders />
        </Section>

        <Section
          id="rebates"
          eyebrow={`Fiscal ${REBATE_YEAR}`}
          title="Annual rebate summary"
          description="Year-end retroactive rebates earned on agreements that reached their annual quantity target."
        >
          <RebateSummary year={REBATE_YEAR} />
        </Section>
      </main>

      <footer className="border-t py-6 text-center text-xs text-muted-foreground">
        MediBuy · Connected to <span className="num">{API_BASE_URL}</span>
      </footer>
    </div>
  );
}
