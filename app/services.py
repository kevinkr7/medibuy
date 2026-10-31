"""Deterministic contract-pricing and annual-rebate calculations.

The engine derives every result from stored source records. It does not persist
calculated amounts, so inserting a backdated purchase order cannot leave stale
pricing or rebate data behind.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import Agreement, AgreementVersion, PriceTier, PurchaseOrderLine

MONEY_QUANTUM = Decimal("0.01")
ONE_HUNDRED = Decimal("100")
ZERO_MONEY = Decimal("0.00")


class PricingDomainError(ValueError):
    """Base error for pricing and rebate domain failures."""


class PurchaseOrderNotFoundError(PricingDomainError):
    """Raised when a requested purchase order does not exist."""


class AgreementNotFoundError(PricingDomainError):
    """Raised when a purchase has no agreement valid on its purchase date."""


class AgreementVersionNotFoundError(PricingDomainError):
    """Raised when an agreement has no version valid on a purchase date."""


class PurchaseOrderValidationError(PricingDomainError):
    """Raised when PO values conflict with an otherwise valid agreement."""


class PricingConfigurationError(PricingDomainError):
    """Raised for ambiguous agreements, versions, or price tiers."""


@dataclass(frozen=True)
class PurchaseOrderPricingResult:
    po_id: str
    agreement_id: str
    agreement_version_id: str
    quarter: str
    quarter_quantity_before_po: int
    quarter_quantity_after_po: int
    annual_quantity_after_po: int
    tier_discount_percent: int
    correct_unit_price: Decimal
    correct_line_amount: Decimal
    entered_line_amount: Decimal
    variance_amount: Decimal
    status: str
    annual_rebate_earned_after_po: Decimal
    rebate_newly_unlocked_by_po: Decimal


@dataclass(frozen=True)
class AnnualRebateSummary:
    supplier_id: str
    agreement_id: str
    year: int
    currency: str
    annual_target_quantity: int
    annual_purchased_quantity: int
    target_met: bool
    target_first_met_by_po: str | None
    target_first_met_on: date | None
    eligible_contract_value: Decimal
    rebate_percent: int
    rebate_earned: Decimal


@dataclass(frozen=True)
class AnnualRebateReport:
    year: int
    rebates: tuple[AnnualRebateSummary, ...]
    total_rebate_earned: Decimal


@dataclass
class _AnnualState:
    quantity: int = 0
    contract_value: Decimal = ZERO_MONEY
    rebate_earned: Decimal = ZERO_MONEY
    trigger_po_id: str | None = None
    trigger_date: date | None = None


def _money(value: Decimal) -> Decimal:
    return value.quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP)


def _quarter_number(value: date) -> int:
    return ((value.month - 1) // 3) + 1


def resolve_agreement_version(
    session: Session,
    purchase_order: PurchaseOrderLine,
) -> tuple[Agreement, AgreementVersion]:
    """Resolve the one agreement and version active for a purchase order."""

    agreements = session.scalars(
        select(Agreement).where(
            Agreement.supplier_id == purchase_order.supplier_id,
            Agreement.material_code == purchase_order.material_code,
            Agreement.valid_from <= purchase_order.purchase_date,
            Agreement.valid_to >= purchase_order.purchase_date,
        )
    ).all()
    if not agreements:
        raise AgreementNotFoundError(
            f"No agreement for PO {purchase_order.po_id} "
            f"({purchase_order.supplier_id}/{purchase_order.material_code}) "
            f"on {purchase_order.purchase_date.isoformat()}"
        )
    if len(agreements) > 1:
        raise PricingConfigurationError(
            f"PO {purchase_order.po_id} matches multiple active agreements"
        )

    agreement = agreements[0]
    if purchase_order.currency != agreement.currency:
        raise PurchaseOrderValidationError(
            f"PO {purchase_order.po_id} currency {purchase_order.currency} "
            f"does not match agreement {agreement.agreement_id} currency {agreement.currency}"
        )

    versions = session.scalars(
        select(AgreementVersion)
        .where(
            AgreementVersion.agreement_id == agreement.agreement_id,
            AgreementVersion.effective_from <= purchase_order.purchase_date,
            AgreementVersion.effective_to >= purchase_order.purchase_date,
        )
        .options(selectinload(AgreementVersion.price_tiers))
    ).all()
    if not versions:
        raise AgreementVersionNotFoundError(
            f"No version of agreement {agreement.agreement_id} is active for "
            f"PO {purchase_order.po_id} on {purchase_order.purchase_date.isoformat()}"
        )
    if len(versions) > 1:
        raise PricingConfigurationError(
            f"PO {purchase_order.po_id} matches multiple versions of {agreement.agreement_id}"
        )
    return agreement, versions[0]


def _select_price_tier(
    version: AgreementVersion,
    cumulative_quantity: int,
) -> PriceTier:
    matches = [
        tier
        for tier in version.price_tiers
        if tier.min_quantity_inclusive <= cumulative_quantity
        and (
            tier.max_quantity_exclusive is None
            or cumulative_quantity < tier.max_quantity_exclusive
        )
    ]
    if len(matches) != 1:
        raise PricingConfigurationError(
            f"Agreement version {version.version_id} has {len(matches)} matching price tiers "
            f"for cumulative quantity {cumulative_quantity}; expected exactly one"
        )
    return matches[0]


def calculate_purchase_history(
    session: Session,
    *,
    year: int | None = None,
) -> list[PurchaseOrderPricingResult]:
    """Recalculate purchase pricing and rebate state in chronological order."""

    statement = select(PurchaseOrderLine)
    if year is not None:
        statement = statement.where(
            PurchaseOrderLine.purchase_date >= date(year, 1, 1),
            PurchaseOrderLine.purchase_date <= date(year, 12, 31),
        )
    statement = statement.order_by(PurchaseOrderLine.purchase_date, PurchaseOrderLine.po_id)
    purchase_orders = session.scalars(statement).all()

    quarterly_quantities: dict[tuple[str, int, int], int] = defaultdict(int)
    annual_states: dict[tuple[str, int], _AnnualState] = defaultdict(_AnnualState)
    results: list[PurchaseOrderPricingResult] = []

    for purchase_order in purchase_orders:
        agreement, version = resolve_agreement_version(session, purchase_order)
        quarter_number = _quarter_number(purchase_order.purchase_date)
        quarter_key = (agreement.agreement_id, purchase_order.purchase_date.year, quarter_number)
        annual_key = (agreement.agreement_id, purchase_order.purchase_date.year)

        quarter_before = quarterly_quantities[quarter_key]
        quarter_after = quarter_before + purchase_order.quantity
        quarterly_quantities[quarter_key] = quarter_after

        tier = _select_price_tier(version, quarter_after)
        correct_unit_price = _money(
            version.base_unit_price
            * (ONE_HUNDRED - Decimal(tier.discount_percent))
            / ONE_HUNDRED
        )
        correct_line_amount = _money(correct_unit_price * purchase_order.quantity)
        entered_line_amount = _money(purchase_order.entered_unit_price * purchase_order.quantity)
        variance_amount = _money(entered_line_amount - correct_line_amount)
        status = (
            "OVERCHARGED"
            if variance_amount > ZERO_MONEY
            else "UNDERCHARGED"
            if variance_amount < ZERO_MONEY
            else "MATCH"
        )

        annual_state = annual_states[annual_key]
        previous_rebate = annual_state.rebate_earned
        annual_state.quantity += purchase_order.quantity
        annual_state.contract_value = _money(
            annual_state.contract_value + correct_line_amount
        )
        if (
            annual_state.trigger_po_id is None
            and annual_state.quantity >= agreement.annual_target_quantity
        ):
            annual_state.trigger_po_id = purchase_order.po_id
            annual_state.trigger_date = purchase_order.purchase_date
        annual_state.rebate_earned = (
            _money(
                annual_state.contract_value
                * Decimal(agreement.annual_rebate_percent)
                / ONE_HUNDRED
            )
            if annual_state.quantity >= agreement.annual_target_quantity
            else ZERO_MONEY
        )

        results.append(
            PurchaseOrderPricingResult(
                po_id=purchase_order.po_id,
                agreement_id=agreement.agreement_id,
                agreement_version_id=version.version_id,
                quarter=f"{purchase_order.purchase_date.year}-Q{quarter_number}",
                quarter_quantity_before_po=quarter_before,
                quarter_quantity_after_po=quarter_after,
                annual_quantity_after_po=annual_state.quantity,
                tier_discount_percent=tier.discount_percent,
                correct_unit_price=correct_unit_price,
                correct_line_amount=correct_line_amount,
                entered_line_amount=entered_line_amount,
                variance_amount=variance_amount,
                status=status,
                annual_rebate_earned_after_po=annual_state.rebate_earned,
                rebate_newly_unlocked_by_po=_money(
                    annual_state.rebate_earned - previous_rebate
                ),
            )
        )

    return results


def calculate_purchase_order_pricing(
    session: Session,
    po_id: str,
) -> PurchaseOrderPricingResult:
    """Return a PO result after recalculating the complete stored history."""

    results = calculate_purchase_history(session)
    try:
        return next(result for result in results if result.po_id == po_id)
    except StopIteration as exc:
        raise PurchaseOrderNotFoundError(f"Unknown purchase order: {po_id}") from exc


def calculate_annual_rebates(session: Session, year: int) -> AnnualRebateReport:
    """Calculate retroactive annual rebate summaries for all active agreements."""

    history = calculate_purchase_history(session, year=year)
    results_by_agreement: dict[str, list[PurchaseOrderPricingResult]] = defaultdict(list)
    for result in history:
        results_by_agreement[result.agreement_id].append(result)

    agreements = session.scalars(
        select(Agreement)
        .where(
            Agreement.valid_from <= date(year, 12, 31),
            Agreement.valid_to >= date(year, 1, 1),
        )
        .order_by(Agreement.agreement_id)
    ).all()

    summaries: list[AnnualRebateSummary] = []
    for agreement in agreements:
        agreement_results = results_by_agreement.get(agreement.agreement_id, [])
        annual_quantity = (
            agreement_results[-1].annual_quantity_after_po if agreement_results else 0
        )
        eligible_value = _money(
            sum(
                (result.correct_line_amount for result in agreement_results),
                start=ZERO_MONEY,
            )
        )
        target_met = annual_quantity >= agreement.annual_target_quantity
        trigger = next(
            (
                result
                for result in agreement_results
                if result.annual_quantity_after_po >= agreement.annual_target_quantity
            ),
            None,
        )
        rebate_earned = (
            _money(
                eligible_value
                * Decimal(agreement.annual_rebate_percent)
                / ONE_HUNDRED
            )
            if target_met
            else ZERO_MONEY
        )
        trigger_po = session.get(PurchaseOrderLine, trigger.po_id) if trigger else None
        summaries.append(
            AnnualRebateSummary(
                supplier_id=agreement.supplier_id,
                agreement_id=agreement.agreement_id,
                year=year,
                currency=agreement.currency,
                annual_target_quantity=agreement.annual_target_quantity,
                annual_purchased_quantity=annual_quantity,
                target_met=target_met,
                target_first_met_by_po=trigger.po_id if trigger else None,
                target_first_met_on=trigger_po.purchase_date if trigger_po else None,
                eligible_contract_value=eligible_value,
                rebate_percent=agreement.annual_rebate_percent,
                rebate_earned=rebate_earned,
            )
        )

    total = _money(
        sum((summary.rebate_earned for summary in summaries), start=ZERO_MONEY)
    )
    return AnnualRebateReport(year=year, rebates=tuple(summaries), total_rebate_earned=total)
