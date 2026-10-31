"""Pydantic request and response contracts for the MediBuy API."""

from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class StrictSchema(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class HealthResponse(BaseModel):
    status: str


class SupplierResponse(BaseModel):
    supplier_id: str
    supplier_name: str
    material_code: str
    material_name: str
    unit: str


class PriceTierResponse(BaseModel):
    tier_id: str
    min_quantity_inclusive: int
    max_quantity_exclusive: int | None
    discount_percent: int


class AgreementVersionResponse(BaseModel):
    version_id: str
    version_number: int
    effective_from: date
    effective_to: date
    base_unit_price: str
    change_note: str
    price_tiers: list[PriceTierResponse]


class AgreementResponse(BaseModel):
    agreement_id: str
    supplier_id: str
    material_code: str
    valid_from: date
    valid_to: date
    annual_target_quantity: int
    annual_rebate_percent: int
    currency: str
    unit: str
    versions: list[AgreementVersionResponse]


class PurchaseOrderCreate(StrictSchema):
    po_id: str = Field(min_length=1, max_length=100)
    supplier_id: str = Field(min_length=1, max_length=100)
    material_code: str = Field(min_length=1, max_length=100)
    purchase_date: date
    quantity: int = Field(gt=0)
    entered_unit_price: Decimal = Field(
        ge=Decimal("0.00"),
        decimal_places=2,
        max_digits=12,
    )
    currency: str = Field(min_length=3, max_length=3, pattern=r"^[A-Z]{3}$")


class PurchaseOrderPricingResponse(BaseModel):
    po_id: str
    supplier_id: str
    material_code: str
    purchase_date: date
    quantity: int
    currency: str
    agreement_id: str
    agreement_version_id: str
    quarter: str
    quarter_quantity_before_po: int
    quarter_quantity_after_po: int
    annual_quantity_after_po: int
    tier_discount_percent: int
    base_unit_price: str
    entered_unit_price: str
    correct_unit_price: str
    correct_line_amount: str
    entered_line_amount: str
    variance_amount: str
    status: Literal["MATCH", "OVERCHARGED", "UNDERCHARGED"]
    annual_rebate_earned_after_po: str
    rebate_newly_unlocked_by_po: str


class AnnualRebateResponse(BaseModel):
    agreement_id: str
    supplier_id: str
    annual_purchased_quantity: int
    annual_target_quantity: int
    target_met: bool
    eligible_contract_value: str
    rebate_percent: int
    rebate_earned: str
    target_first_met_by_po: str | None
    target_first_met_on: date | None


class AnnualRebateReportResponse(BaseModel):
    year: int
    currency: str | None
    rebates: list[AnnualRebateResponse]
    total_rebate_earned: str


class DashboardResponse(BaseModel):
    total_suppliers: int
    total_agreements: int
    total_purchase_orders: int
    overcharged_purchase_orders: int
    undercharged_purchase_orders: int
    total_overcharge_amount: str
    total_undercharge_amount: str
    total_eligible_contract_value: str
    total_earned_rebate: str
