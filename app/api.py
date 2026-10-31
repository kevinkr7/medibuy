"""Thin FastAPI routes over the persistence and business-service layers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, FastAPI, Path, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.models import Agreement, AgreementVersion, PurchaseOrderLine, Supplier
from app.schemas import (
    AgreementResponse,
    AgreementVersionResponse,
    AnnualRebateReportResponse,
    AnnualRebateResponse,
    DashboardResponse,
    HealthResponse,
    PriceTierResponse,
    PurchaseOrderCreate,
    PurchaseOrderPricingResponse,
    SupplierResponse,
)
from app.services import (
    AgreementNotFoundError,
    AgreementVersionNotFoundError,
    PricingConfigurationError,
    PricingDomainError,
    PurchaseOrderNotFoundError,
    PurchaseOrderPricingResult,
    PurchaseOrderValidationError,
    calculate_annual_rebates,
    calculate_purchase_history,
    calculate_purchase_order_pricing,
)

router = APIRouter()
ZERO_MONEY = Decimal("0.00")


@dataclass
class APIError(Exception):
    status_code: int
    code: str
    message: str


def _money(value: Decimal) -> str:
    return format(value, ".2f")


def _error_content(code: str, message: str, details=None) -> dict:
    error = {"code": code, "message": message}
    if details is not None:
        error["details"] = details
    return {"error": error}


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(APIError)
    async def api_error_handler(_request: Request, exc: APIError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=_error_content(exc.code, exc.message),
        )

    @app.exception_handler(RequestValidationError)
    async def request_validation_handler(
        _request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content=jsonable_encoder(
                _error_content(
                    "validation_error",
                    "Request validation failed",
                    exc.errors(),
                )
            ),
        )

    @app.exception_handler(PricingDomainError)
    async def pricing_error_handler(_request: Request, exc: PricingDomainError) -> JSONResponse:
        if isinstance(exc, PurchaseOrderNotFoundError):
            status_code, code = status.HTTP_404_NOT_FOUND, "purchase_order_not_found"
        elif isinstance(exc, AgreementNotFoundError):
            status_code, code = status.HTTP_404_NOT_FOUND, "agreement_not_found"
        elif isinstance(exc, AgreementVersionNotFoundError):
            status_code, code = status.HTTP_404_NOT_FOUND, "agreement_version_not_found"
        elif isinstance(exc, PurchaseOrderValidationError):
            status_code, code = status.HTTP_422_UNPROCESSABLE_CONTENT, "invalid_purchase_order"
        elif isinstance(exc, PricingConfigurationError):
            status_code, code = status.HTTP_409_CONFLICT, "pricing_configuration_conflict"
        else:
            status_code, code = status.HTTP_400_BAD_REQUEST, "invalid_business_operation"
        return JSONResponse(
            status_code=status_code,
            content=_error_content(code, str(exc)),
        )


def _pricing_response(
    session: Session,
    result: PurchaseOrderPricingResult,
) -> PurchaseOrderPricingResponse:
    purchase_order = session.get(PurchaseOrderLine, result.po_id)
    version = session.get(AgreementVersion, result.agreement_version_id)
    if purchase_order is None:
        raise PurchaseOrderNotFoundError(f"Unknown purchase order: {result.po_id}")
    if version is None:
        raise AgreementVersionNotFoundError(
            f"Unknown agreement version: {result.agreement_version_id}"
        )
    return PurchaseOrderPricingResponse(
        po_id=purchase_order.po_id,
        supplier_id=purchase_order.supplier_id,
        material_code=purchase_order.material_code,
        purchase_date=purchase_order.purchase_date,
        quantity=purchase_order.quantity,
        currency=purchase_order.currency,
        agreement_id=result.agreement_id,
        agreement_version_id=result.agreement_version_id,
        quarter=result.quarter,
        quarter_quantity_before_po=result.quarter_quantity_before_po,
        quarter_quantity_after_po=result.quarter_quantity_after_po,
        annual_quantity_after_po=result.annual_quantity_after_po,
        tier_discount_percent=result.tier_discount_percent,
        base_unit_price=_money(version.base_unit_price),
        entered_unit_price=_money(purchase_order.entered_unit_price),
        correct_unit_price=_money(result.correct_unit_price),
        correct_line_amount=_money(result.correct_line_amount),
        entered_line_amount=_money(result.entered_line_amount),
        variance_amount=_money(result.variance_amount),
        status=result.status,
        annual_rebate_earned_after_po=_money(result.annual_rebate_earned_after_po),
        rebate_newly_unlocked_by_po=_money(result.rebate_newly_unlocked_by_po),
    )


@router.get("/health", response_model=HealthResponse, tags=["system"])
def health() -> HealthResponse:
    return HealthResponse(status="ok")


@router.get("/suppliers", response_model=list[SupplierResponse], tags=["catalog"])
def list_suppliers(session: Session = Depends(get_db)) -> list[SupplierResponse]:
    suppliers = session.scalars(select(Supplier).order_by(Supplier.supplier_id)).all()
    return [SupplierResponse.model_validate(supplier, from_attributes=True) for supplier in suppliers]


@router.get("/agreements", response_model=list[AgreementResponse], tags=["catalog"])
def list_agreements(session: Session = Depends(get_db)) -> list[AgreementResponse]:
    agreements = session.scalars(
        select(Agreement)
        .options(
            selectinload(Agreement.versions).selectinload(AgreementVersion.price_tiers)
        )
        .order_by(Agreement.agreement_id)
    ).all()
    responses: list[AgreementResponse] = []
    for agreement in agreements:
        versions = [
            AgreementVersionResponse(
                version_id=version.version_id,
                version_number=version.version_number,
                effective_from=version.effective_from,
                effective_to=version.effective_to,
                base_unit_price=_money(version.base_unit_price),
                change_note=version.change_note,
                price_tiers=[
                    PriceTierResponse(
                        tier_id=tier.tier_id,
                        min_quantity_inclusive=tier.min_quantity_inclusive,
                        max_quantity_exclusive=tier.max_quantity_exclusive,
                        discount_percent=tier.discount_percent,
                    )
                    for tier in version.price_tiers
                ],
            )
            for version in agreement.versions
        ]
        responses.append(
            AgreementResponse(
                agreement_id=agreement.agreement_id,
                supplier_id=agreement.supplier_id,
                material_code=agreement.material_code,
                valid_from=agreement.valid_from,
                valid_to=agreement.valid_to,
                annual_target_quantity=agreement.annual_target_quantity,
                annual_rebate_percent=agreement.annual_rebate_percent,
                currency=agreement.currency,
                unit=agreement.unit,
                versions=versions,
            )
        )
    return responses


@router.get(
    "/purchase-orders",
    response_model=list[PurchaseOrderPricingResponse],
    tags=["purchase orders"],
)
def list_purchase_orders(
    session: Session = Depends(get_db),
) -> list[PurchaseOrderPricingResponse]:
    return [_pricing_response(session, result) for result in calculate_purchase_history(session)]


@router.get(
    "/purchase-orders/{po_id}/price",
    response_model=PurchaseOrderPricingResponse,
    tags=["purchase orders"],
)
def get_purchase_order_price(
    po_id: str,
    session: Session = Depends(get_db),
) -> PurchaseOrderPricingResponse:
    return _pricing_response(session, calculate_purchase_order_pricing(session, po_id))


@router.post(
    "/purchase-orders",
    response_model=PurchaseOrderPricingResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["purchase orders"],
)
def create_purchase_order(
    payload: PurchaseOrderCreate,
    session: Session = Depends(get_db),
) -> PurchaseOrderPricingResponse:
    if session.get(PurchaseOrderLine, payload.po_id) is not None:
        raise APIError(status.HTTP_409_CONFLICT, "duplicate_po_id", f"PO {payload.po_id} already exists")
    supplier = session.get(Supplier, payload.supplier_id)
    if supplier is None:
        raise APIError(
            status.HTTP_404_NOT_FOUND,
            "supplier_not_found",
            f"Unknown supplier: {payload.supplier_id}",
        )
    if payload.material_code != supplier.material_code:
        raise APIError(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "material_mismatch",
            f"Material {payload.material_code} does not match supplier {payload.supplier_id}",
        )

    purchase_order = PurchaseOrderLine(**payload.model_dump())
    try:
        session.add(purchase_order)
        session.flush()
        result = calculate_purchase_order_pricing(session, payload.po_id)
        response = _pricing_response(session, result)
        session.commit()
        return response
    except IntegrityError as exc:
        session.rollback()
        raise APIError(
            status.HTTP_409_CONFLICT,
            "purchase_order_conflict",
            f"PO {payload.po_id} conflicts with existing data",
        ) from exc
    except Exception:
        session.rollback()
        raise


@router.get(
    "/rebates/{year}",
    response_model=AnnualRebateReportResponse,
    tags=["rebates"],
)
def get_rebates(
    year: int = Path(ge=1, le=9999),
    session: Session = Depends(get_db),
) -> AnnualRebateReportResponse:
    report = calculate_annual_rebates(session, year)
    currencies = {summary.currency for summary in report.rebates}
    return AnnualRebateReportResponse(
        year=report.year,
        currency=next(iter(currencies)) if len(currencies) == 1 else None,
        rebates=[
            AnnualRebateResponse(
                agreement_id=summary.agreement_id,
                supplier_id=summary.supplier_id,
                annual_purchased_quantity=summary.annual_purchased_quantity,
                annual_target_quantity=summary.annual_target_quantity,
                target_met=summary.target_met,
                eligible_contract_value=_money(summary.eligible_contract_value),
                rebate_percent=summary.rebate_percent,
                rebate_earned=_money(summary.rebate_earned),
                target_first_met_by_po=summary.target_first_met_by_po,
                target_first_met_on=summary.target_first_met_on,
            )
            for summary in report.rebates
        ],
        total_rebate_earned=_money(report.total_rebate_earned),
    )


@router.get("/dashboard", response_model=DashboardResponse, tags=["dashboard"])
def get_dashboard(session: Session = Depends(get_db)) -> DashboardResponse:
    history = calculate_purchase_history(session)
    overcharges = [result for result in history if result.status == "OVERCHARGED"]
    undercharges = [result for result in history if result.status == "UNDERCHARGED"]
    years = sorted(
        set(session.scalars(select(PurchaseOrderLine.purchase_date)).all())
    )
    purchase_years = sorted({purchase_date.year for purchase_date in years})
    total_rebate = sum(
        (calculate_annual_rebates(session, year).total_rebate_earned for year in purchase_years),
        start=ZERO_MONEY,
    )
    return DashboardResponse(
        total_suppliers=session.scalar(select(func.count()).select_from(Supplier)) or 0,
        total_agreements=session.scalar(select(func.count()).select_from(Agreement)) or 0,
        total_purchase_orders=len(history),
        overcharged_purchase_orders=len(overcharges),
        undercharged_purchase_orders=len(undercharges),
        total_overcharge_amount=_money(
            sum((result.variance_amount for result in overcharges), start=ZERO_MONEY)
        ),
        total_undercharge_amount=_money(
            sum((-result.variance_amount for result in undercharges), start=ZERO_MONEY)
        ),
        total_eligible_contract_value=_money(
            sum((result.correct_line_amount for result in history), start=ZERO_MONEY)
        ),
        total_earned_rebate=_money(total_rebate),
    )
