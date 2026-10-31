import type { ReactNode } from "react";
import { AlertTriangle, Inbox, Loader2, WifiOff } from "lucide-react";
import { API_BASE_URL, ApiError, NetworkError } from "@/lib/api/client";
import type { PricingStatus } from "@/lib/api/types";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";

export function BrandMark({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 32 32" className={cn("h-8 w-8", className)} aria-hidden>
      <rect width="32" height="32" rx="7" className="fill-navy" />
      <path
        d="M8 23V9l8 8 8-8v14"
        fill="none"
        strokeWidth="3"
        strokeLinejoin="round"
        className="stroke-primary"
      />
      <circle cx="16" cy="17" r="2" className="fill-navy-foreground" />
    </svg>
  );
}

export function Section({
  id,
  eyebrow,
  title,
  description,
  actions,
  children,
}: {
  id: string;
  eyebrow: string;
  title: string;
  description?: string;
  actions?: ReactNode;
  children: ReactNode;
}) {
  return (
    <section id={id} className="scroll-mt-24">
      <div className="mb-5 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.14em] text-primary">
            {eyebrow}
          </p>
          <h2 className="mt-1 text-xl font-semibold tracking-tight text-foreground">{title}</h2>
          {description && (
            <p className="mt-1 max-w-2xl text-sm text-muted-foreground">{description}</p>
          )}
        </div>
        {actions && <div className="flex shrink-0 items-center gap-2">{actions}</div>}
      </div>
      {children}
    </section>
  );
}

export function Panel({ children, className }: { children: ReactNode; className?: string }) {
  return <div className={cn("rounded-lg border bg-card shadow-card", className)}>{children}</div>;
}

export function LoadingBlock({ label = "Loading…" }: { label?: string }) {
  return (
    <div
      className="flex items-center justify-center gap-2 py-12 text-sm text-muted-foreground"
      role="status"
    >
      <Loader2 className="h-4 w-4 animate-spin" /> {label}
    </div>
  );
}

export function EmptyBlock({ label }: { label: string }) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 py-12 text-sm text-muted-foreground">
      <Inbox className="h-5 w-5" /> {label}
    </div>
  );
}

export function ErrorBlock({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const offline = error instanceof NetworkError;
  return (
    <div
      className="flex flex-col items-center justify-center gap-3 px-6 py-10 text-center"
      role="alert"
    >
      <div
        className={cn(
          "rounded-full p-2.5",
          offline ? "bg-muted text-muted-foreground" : "bg-danger-soft text-danger",
        )}
      >
        {offline ? <WifiOff className="h-5 w-5" /> : <AlertTriangle className="h-5 w-5" />}
      </div>
      <div>
        <p className="text-sm font-medium text-foreground">
          {offline ? "Backend unavailable" : "Request failed"}
        </p>
        <p className="mt-1 max-w-md text-xs text-muted-foreground">
          {offline
            ? `Could not reach the MediBuy API at ${API_BASE_URL}. Start the FastAPI server and check CORS settings.`
            : error instanceof ApiError
              ? `${error.message} (${error.code})`
              : String((error as Error)?.message ?? error)}
        </p>
      </div>
      {onRetry && (
        <Button size="sm" variant="outline" onClick={onRetry}>
          Retry
        </Button>
      )}
    </div>
  );
}

const STATUS_STYLES: Record<PricingStatus, string> = {
  MATCH: "bg-success-soft text-success",
  OVERCHARGED: "bg-danger-soft text-danger",
  UNDERCHARGED: "bg-info-soft text-info",
};

export function StatusBadge({ status }: { status: PricingStatus }) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-[11px] font-semibold tracking-wide",
        STATUS_STYLES[status] ?? "bg-muted text-muted-foreground",
      )}
    >
      <span className="h-1.5 w-1.5 rounded-full bg-current" aria-hidden />
      {status}
    </span>
  );
}

export function DefRow({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex items-baseline justify-between gap-4 border-b border-dashed py-2 last:border-0">
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd className="text-right text-sm font-medium text-foreground">{children}</dd>
    </div>
  );
}
