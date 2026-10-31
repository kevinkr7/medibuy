// Types derived from the MediBuy OpenAPI schema (components.schemas).
// Money fields are decimal strings with two places, e.g. "104.50".
export type Money = string;
export type IsoDate = string;

export interface HealthResponse {
  status: string;
}

export interface SupplierResponse {
  supplier_id: string;
  supplier_name: string;
  material_code: string;
  material_name: string;
  unit: string;
}

export interface PriceTierResponse {
  tier_id: string;
  min_quantity_inclusive: number;
  max_quantity_exclusive: number | null;
  discount_percent: number;
}

export interface AgreementVersionResponse {
  version_id: string;
  version_number: number;
  effective_from: IsoDate;
  effective_to: IsoDate;
  base_unit_price: Money;
  change_note: string;
  price_tiers: PriceTierResponse[];
}

export interface AgreementResponse {
  agreement_id: string;
  supplier_id: string;
  material_code: string;
  valid_from: IsoDate;
  valid_to: IsoDate;
  annual_target_quantity: number;
  annual_rebate_percent: number;
  currency: string;
  unit: string;
  versions: AgreementVersionResponse[];
}

export type PricingStatus = "MATCH" | "OVERCHARGED" | "UNDERCHARGED";

export interface PurchaseOrderPricingResponse {
  po_id: string;
  supplier_id: string;
  material_code: string;
  purchase_date: IsoDate;
  quantity: number;
  currency: string;
  agreement_id: string;
  agreement_version_id: string;
  quarter: string;
  quarter_quantity_before_po: number;
  quarter_quantity_after_po: number;
  annual_quantity_after_po: number;
  tier_discount_percent: number;
  base_unit_price: Money;
  entered_unit_price: Money;
  correct_unit_price: Money;
  correct_line_amount: Money;
  entered_line_amount: Money;
  variance_amount: Money;
  status: PricingStatus;
  annual_rebate_earned_after_po: Money;
  rebate_newly_unlocked_by_po: Money;
}

export interface PurchaseOrderCreate {
  po_id: string;
  supplier_id: string;
  material_code: string;
  purchase_date: IsoDate;
  quantity: number;
  entered_unit_price: string;
  currency: string;
}

export interface AnnualRebateResponse {
  agreement_id: string;
  supplier_id: string;
  annual_purchased_quantity: number;
  annual_target_quantity: number;
  target_met: boolean;
  eligible_contract_value: Money;
  rebate_percent: number;
  rebate_earned: Money;
  target_first_met_by_po: string | null;
  target_first_met_on: IsoDate | null;
}

export interface AnnualRebateReportResponse {
  year: number;
  currency: string | null;
  rebates: AnnualRebateResponse[];
  total_rebate_earned: Money;
}

export interface DashboardResponse {
  total_suppliers: number;
  total_agreements: number;
  total_purchase_orders: number;
  overcharged_purchase_orders: number;
  undercharged_purchase_orders: number;
  total_overcharge_amount: Money;
  total_undercharge_amount: Money;
  total_eligible_contract_value: Money;
  total_earned_rebate: Money;
}

export interface ApiErrorEnvelope {
  error: { code: string; message: string; details?: unknown[] };
}
