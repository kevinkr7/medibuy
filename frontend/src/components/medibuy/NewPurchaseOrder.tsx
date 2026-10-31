import { useMemo, useState, type FormEvent, type ReactNode } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, Loader2, Plus } from "lucide-react";
import { api, ApiError, NetworkError, queryKeys } from "@/lib/api/client";
import type { PurchaseOrderCreate, PurchaseOrderPricingResponse } from "@/lib/api/types";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { PricingDetail } from "./PurchaseOrders";

const EMPTY: PurchaseOrderCreate = {
  po_id: "",
  supplier_id: "",
  material_code: "",
  purchase_date: "",
  quantity: 0,
  entered_unit_price: "",
  currency: "INR",
};

type Errors = Partial<Record<keyof PurchaseOrderCreate, string>>;

function validate(f: PurchaseOrderCreate, qtyRaw: string): Errors {
  const e: Errors = {};
  if (!f.po_id.trim()) e.po_id = "PO ID is required.";
  if (!f.supplier_id) e.supplier_id = "Select a supplier.";
  if (!f.material_code) e.material_code = "Select a material.";
  if (!/^\d{4}-\d{2}-\d{2}$/.test(f.purchase_date)) e.purchase_date = "Enter a purchase date.";
  if (!/^[1-9]\d*$/.test(qtyRaw)) e.quantity = "Quantity must be a positive whole number.";
  if (!/^\d+(\.\d{1,2})?$/.test(f.entered_unit_price))
    e.entered_unit_price = "Enter a non-negative price with up to 2 decimals.";
  if (!/^[A-Z]{3}$/.test(f.currency)) e.currency = "Use a 3-letter uppercase code, e.g. INR.";
  return e;
}

const selectCls =
  "flex h-9 w-full rounded-md border border-input bg-card px-3 py-1 text-sm shadow-xs focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-50";

function Field({
  id,
  label,
  error,
  children,
}: {
  id: string;
  label: string;
  error: string | undefined;
  children: ReactNode;
}) {
  return (
    <div className="space-y-1.5">
      <Label htmlFor={id}>{label}</Label>
      {children}
      {error && (
        <p id={`${id}-err`} className="text-xs text-destructive">
          {error}
        </p>
      )}
    </div>
  );
}

export function NewPurchaseOrder() {
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState<PurchaseOrderCreate>(EMPTY);
  const [qtyRaw, setQtyRaw] = useState("");
  const [errors, setErrors] = useState<Errors>({});
  const [result, setResult] = useState<PurchaseOrderPricingResponse | null>(null);

  const suppliers = useQuery({ queryKey: queryKeys.suppliers, queryFn: api.suppliers });
  const agreements = useQuery({ queryKey: queryKeys.agreements, queryFn: api.agreements });

  const supplierOptions = useMemo(() => {
    const m = new Map<string, string>();
    suppliers.data?.forEach((s) => m.set(s.supplier_id, s.supplier_name));
    return [...m.entries()];
  }, [suppliers.data]);
  const materialOptions = (suppliers.data ?? []).filter((s) => s.supplier_id === form.supplier_id);

  const mutation = useMutation({
    mutationFn: api.createPurchaseOrder,
    onSuccess: (data) => {
      setResult(data);
      qc.invalidateQueries({ queryKey: queryKeys.purchaseOrders });
      qc.invalidateQueries({ queryKey: ["rebates"] });
      qc.invalidateQueries({ queryKey: queryKeys.dashboard });
    },
  });

  const set = <K extends keyof PurchaseOrderCreate>(k: K, v: PurchaseOrderCreate[K]) =>
    setForm((f) => ({ ...f, [k]: v }));

  const onSupplier = (id: string) => {
    const mats = (suppliers.data ?? []).filter((s) => s.supplier_id === id);
    const mat = mats.length === 1 ? mats[0]!.material_code : "";
    const agr = agreements.data?.find((a) => a.supplier_id === id && a.material_code === mat);
    setForm((f) => ({
      ...f,
      supplier_id: id,
      material_code: mat,
      currency: agr?.currency ?? f.currency,
    }));
  };

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    const errs = validate(form, qtyRaw);
    setErrors(errs);
    if (Object.keys(errs).length) return;
    mutation.mutate({ ...form, po_id: form.po_id.trim(), quantity: Number(qtyRaw) });
  };

  const reset = () => {
    setForm(EMPTY);
    setQtyRaw("");
    setErrors({});
    setResult(null);
    mutation.reset();
  };

  const err = mutation.error;
  const errTitle =
    err instanceof NetworkError
      ? "Backend unavailable"
      : err instanceof ApiError
        ? err.code === "duplicate_po_id"
          ? "Duplicate PO ID"
          : err.status === 404
            ? "No matching agreement or record"
            : err.status === 422
              ? "Validation error"
              : err.status === 409
                ? "Conflict"
                : "Request failed"
        : "Request failed";

  return (
    <Dialog
      open={open}
      onOpenChange={(o) => {
        setOpen(o);
        if (!o) reset();
      }}
    >
      <DialogTrigger asChild>
        <Button>
          <Plus className="h-4 w-4" /> New purchase order
        </Button>
      </DialogTrigger>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>{result ? "Purchase order recorded" : "New purchase order"}</DialogTitle>
          <DialogDescription>
            {result
              ? "The backend verified this order against the applicable contract version."
              : "Contract price, discount tier and variance are calculated by the backend."}
          </DialogDescription>
        </DialogHeader>

        {result ? (
          <div className="space-y-4">
            <Alert>
              <CheckCircle2 className="h-4 w-4 text-success" />
              <AlertTitle className="num">{result.po_id} created</AlertTitle>
              <AlertDescription>
                Purchase orders, rebates and dashboard have been refreshed.
              </AlertDescription>
            </Alert>
            <PricingDetail
              po={result}
              supplierName={supplierOptions.find(([id]) => id === result.supplier_id)?.[1]}
            />
            <div className="flex justify-end gap-2">
              <Button variant="outline" onClick={reset}>
                Add another
              </Button>
              <Button
                onClick={() => {
                  setOpen(false);
                  reset();
                }}
              >
                Done
              </Button>
            </div>
          </div>
        ) : (
          <form onSubmit={onSubmit} noValidate className="space-y-4">
            {suppliers.isError && (
              <Alert variant="destructive">
                <AlertTitle>Supplier list unavailable</AlertTitle>
                <AlertDescription>Cannot load suppliers from the backend.</AlertDescription>
              </Alert>
            )}
            <div className="grid gap-4 sm:grid-cols-2">
              <Field id="po_id" label="PO ID" error={errors.po_id}>
                <Input
                  id="po_id"
                  value={form.po_id}
                  onChange={(e) => set("po_id", e.target.value)}
                  placeholder="P16"
                  aria-invalid={!!errors.po_id}
                />
              </Field>
              <Field id="purchase_date" label="Purchase date" error={errors.purchase_date}>
                <Input
                  id="purchase_date"
                  type="date"
                  value={form.purchase_date}
                  onChange={(e) => set("purchase_date", e.target.value)}
                  aria-invalid={!!errors.purchase_date}
                />
              </Field>
              <Field id="supplier_id" label="Supplier" error={errors.supplier_id}>
                <select
                  id="supplier_id"
                  className={selectCls}
                  value={form.supplier_id}
                  onChange={(e) => onSupplier(e.target.value)}
                  disabled={!suppliers.data}
                >
                  <option value="">{suppliers.isLoading ? "Loading…" : "Select supplier"}</option>
                  {supplierOptions.map(([id, name]) => (
                    <option key={id} value={id}>
                      {name} ({id})
                    </option>
                  ))}
                </select>
              </Field>
              <Field id="material_code" label="Material" error={errors.material_code}>
                <select
                  id="material_code"
                  className={selectCls}
                  value={form.material_code}
                  onChange={(e) => set("material_code", e.target.value)}
                  disabled={!form.supplier_id}
                >
                  <option value="">Select material</option>
                  {materialOptions.map((m) => (
                    <option key={m.material_code} value={m.material_code}>
                      {m.material_name} ({m.material_code})
                    </option>
                  ))}
                </select>
              </Field>
              <Field id="quantity" label="Quantity" error={errors.quantity}>
                <Input
                  id="quantity"
                  inputMode="numeric"
                  value={qtyRaw}
                  onChange={(e) => setQtyRaw(e.target.value.trim())}
                  placeholder="50"
                  aria-invalid={!!errors.quantity}
                />
              </Field>
              <Field
                id="entered_unit_price"
                label="Entered unit price"
                error={errors.entered_unit_price}
              >
                <Input
                  id="entered_unit_price"
                  inputMode="decimal"
                  value={form.entered_unit_price}
                  onChange={(e) => set("entered_unit_price", e.target.value.trim())}
                  placeholder="110.00"
                  aria-invalid={!!errors.entered_unit_price}
                />
              </Field>
              <Field id="currency" label="Currency" error={errors.currency}>
                <Input
                  id="currency"
                  value={form.currency}
                  maxLength={3}
                  onChange={(e) => set("currency", e.target.value.toUpperCase())}
                  aria-invalid={!!errors.currency}
                />
              </Field>
            </div>

            {mutation.isError && (
              <Alert variant="destructive" role="alert">
                <AlertTitle>{errTitle}</AlertTitle>
                <AlertDescription>
                  {err?.message}
                  {err instanceof ApiError && (
                    <span className="num ml-1 text-xs opacity-80">[{err.code}]</span>
                  )}
                </AlertDescription>
              </Alert>
            )}

            <div className="flex justify-end gap-2 pt-1">
              <Button type="button" variant="outline" onClick={() => setOpen(false)}>
                Cancel
              </Button>
              <Button type="submit" disabled={mutation.isPending}>
                {mutation.isPending && <Loader2 className="h-4 w-4 animate-spin" />}
                {mutation.isPending ? "Verifying…" : "Submit & verify"}
              </Button>
            </div>
          </form>
        )}
      </DialogContent>
    </Dialog>
  );
}
