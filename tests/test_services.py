import json
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models import Agreement, AgreementVersion, PriceTier, PurchaseOrderLine
from app.seed import seed_database
from app.services import (
    AgreementNotFoundError,
    AgreementVersionNotFoundError,
    PricingConfigurationError,
    calculate_annual_rebates,
    calculate_purchase_history,
    calculate_purchase_order_pricing,
    resolve_agreement_version,
)

EXPECTED_RESULTS_PATH = (
    Path(__file__).resolve().parent.parent
    / "contract_pricing_rebate_dataset"
    / "expected_results.json"
)
MONEY_FIELDS = {
    "correct_unit_price",
    "correct_line_amount",
    "entered_line_amount",
    "variance_amount",
    "annual_rebate_earned_after_po",
    "rebate_newly_unlocked_by_po",
}


@pytest.fixture
def seeded_session(test_engine):
    seed_database(test_engine)
    with Session(test_engine) as session:
        yield session


@pytest.fixture(scope="module")
def oracle() -> dict:
    return json.loads(EXPECTED_RESULTS_PATH.read_text(encoding="utf-8"))


def _by_po(session: Session) -> dict[str, object]:
    return {result.po_id: result for result in calculate_purchase_history(session)}


def test_all_15_po_results_match_frozen_oracle(seeded_session, oracle) -> None:
    actual = _by_po(seeded_session)

    assert set(actual) == {row["po_id"] for row in oracle["purchase_order_results"]}
    for expected in oracle["purchase_order_results"]:
        result = actual[expected["po_id"]]
        for field, expected_value in expected.items():
            actual_value = getattr(result, field)
            if field in MONEY_FIELDS:
                expected_value = Decimal(expected_value)
            assert actual_value == expected_value, f"{expected['po_id']}.{field}"


def test_p02_exact_tier_boundary_and_overcharge(seeded_session) -> None:
    result = calculate_purchase_order_pricing(seeded_session, "P02")

    assert result.agreement_version_id == "AGR-001-V1"
    assert result.quarter_quantity_after_po == 500
    assert result.tier_discount_percent == 5
    assert result.correct_unit_price == Decimal("95.00")
    assert result.variance_amount == Decimal("1000.00")
    assert result.status == "OVERCHARGED"


def test_p05_and_p06_resolve_inclusive_amendment_dates(seeded_session) -> None:
    p05 = seeded_session.get(PurchaseOrderLine, "P05")
    p06 = seeded_session.get(PurchaseOrderLine, "P06")
    assert p05 is not None and p06 is not None

    _, p05_version = resolve_agreement_version(seeded_session, p05)
    _, p06_version = resolve_agreement_version(seeded_session, p06)
    assert (p05_version.version_id, p05_version.effective_to) == (
        "AGR-001-V1",
        date(2025, 5, 14),
    )
    assert (p06_version.version_id, p06_version.effective_from) == (
        "AGR-001-V2",
        date(2025, 5, 15),
    )
    assert calculate_purchase_order_pricing(seeded_session, "P05").correct_unit_price == Decimal(
        "95.00"
    )


def test_p06_quantity_continues_across_amendment(seeded_session) -> None:
    result = calculate_purchase_order_pricing(seeded_session, "P06")

    assert result.agreement_version_id == "AGR-001-V2"
    assert result.quarter_quantity_after_po == 700
    assert result.tier_discount_percent == 5
    assert result.correct_unit_price == Decimal("104.50")
    assert result.correct_line_amount == Decimal("20900.00")


def test_p07_uses_amended_top_tier(seeded_session) -> None:
    result = calculate_purchase_order_pricing(seeded_session, "P07")

    assert result.agreement_version_id == "AGR-001-V2"
    assert result.quarter_quantity_after_po == 1000
    assert result.tier_discount_percent == 8
    assert result.correct_unit_price == Decimal("101.20")


def test_quarter_resets_but_annual_quantity_does_not(seeded_session) -> None:
    result = calculate_purchase_order_pricing(seeded_session, "P08")

    assert result.quarter == "2025-Q4"
    assert result.quarter_quantity_before_po == 0
    assert result.quarter_quantity_after_po == 600
    assert result.annual_quantity_after_po == 2600


def test_negative_variance_is_classified_as_undercharged(seeded_session) -> None:
    result = calculate_purchase_order_pricing(seeded_session, "P12")

    assert result.variance_amount == Decimal("-400.00")
    assert result.status == "UNDERCHARGED"


def test_annual_rebate_summaries_match_oracle(seeded_session, oracle) -> None:
    report = calculate_annual_rebates(seeded_session, 2025)
    actual = {summary.agreement_id: summary for summary in report.rebates}

    for expected in oracle["year_end_rebates"]:
        summary = actual[expected["agreement_id"]]
        assert summary.supplier_id == expected["supplier_id"]
        assert summary.annual_target_quantity == expected["annual_target_quantity"]
        assert summary.annual_purchased_quantity == expected["annual_purchased_quantity"]
        assert summary.target_met is expected["target_met"]
        assert summary.target_first_met_by_po == expected["target_first_met_by_po"]
        assert summary.target_first_met_on == date.fromisoformat(expected["target_first_met_on"])
        assert summary.eligible_contract_value == Decimal(expected["eligible_contract_value"])
        assert summary.rebate_percent == expected["rebate_percent"]
        assert summary.rebate_earned == Decimal(expected["rebate_earned"])
    assert report.total_rebate_earned == Decimal("11861.00")


def test_p08_unlocks_retroactive_medpolymer_rebate(seeded_session) -> None:
    p08 = calculate_purchase_order_pricing(seeded_session, "P08")
    summary = {
        item.agreement_id: item
        for item in calculate_annual_rebates(seeded_session, 2025).rebates
    }["AGR-001"]

    assert summary.annual_purchased_quantity == 2600
    assert summary.annual_target_quantity == 2500
    assert summary.eligible_contract_value == Decimal("257460.00")
    assert summary.rebate_earned == Decimal("7723.80")
    assert summary.target_first_met_by_po == "P08"
    assert p08.annual_rebate_earned_after_po == Decimal("7723.80")
    assert p08.rebate_newly_unlocked_by_po == Decimal("7723.80")


def test_rebate_is_zero_when_annual_target_is_not_reached(seeded_session) -> None:
    agreement = seeded_session.get(Agreement, "AGR-001")
    assert agreement is not None
    agreement.annual_target_quantity = 5000
    seeded_session.flush()

    summary = {
        item.agreement_id: item
        for item in calculate_annual_rebates(seeded_session, 2025).rebates
    }["AGR-001"]
    medpolymer_results = [
        result
        for result in calculate_purchase_history(seeded_session)
        if result.agreement_id == "AGR-001"
    ]
    assert summary.annual_purchased_quantity == 2600
    assert summary.target_met is False
    assert summary.rebate_earned == Decimal("0.00")
    assert summary.target_first_met_by_po is None
    assert all(result.annual_rebate_earned_after_po == Decimal("0.00") for result in medpolymer_results)


def test_backdated_po_recalculates_later_history_deterministically(seeded_session) -> None:
    before = calculate_purchase_order_pricing(seeded_session, "P01")
    assert before.quarter_quantity_after_po == 300
    assert before.correct_unit_price == Decimal("100.00")

    seeded_session.add(
        PurchaseOrderLine(
            po_id="P00",
            supplier_id="S1",
            material_code="RESIN-MED",
            purchase_date=date(2025, 1, 5),
            quantity=250,
            entered_unit_price=Decimal("100.00"),
            currency="INR",
        )
    )
    seeded_session.flush()

    first_recalculation = calculate_purchase_order_pricing(seeded_session, "P01")
    second_recalculation = calculate_purchase_order_pricing(seeded_session, "P01")
    assert first_recalculation == second_recalculation
    assert first_recalculation.quarter_quantity_before_po == 250
    assert first_recalculation.quarter_quantity_after_po == 550
    assert first_recalculation.tier_discount_percent == 5
    assert first_recalculation.correct_unit_price == Decimal("95.00")


def test_backdated_q2_po_reprices_only_affected_history_and_preserves_inputs(
    seeded_session,
) -> None:
    original_results = _by_po(seeded_session)
    original_entered_prices = {
        po.po_id: po.entered_unit_price
        for po in seeded_session.scalars(select(PurchaseOrderLine)).all()
    }
    seeded_session.add(
        PurchaseOrderLine(
            po_id="P04A",
            supplier_id="S1",
            material_code="RESIN-MED",
            purchase_date=date(2025, 5, 1),
            quantity=500,
            entered_unit_price=Decimal("100.00"),
            currency="INR",
        )
    )
    seeded_session.flush()

    first = _by_po(seeded_session)
    second = _by_po(seeded_session)
    assert first == second

    assert first["P04"] == original_results["P04"]
    assert first["P09"] == original_results["P09"]
    assert first["P05"].quarter_quantity_before_po == 900
    assert first["P05"].quarter_quantity_after_po == 1000
    assert first["P05"].tier_discount_percent == 10
    assert first["P05"].correct_unit_price == Decimal("90.00")
    assert first["P06"].quarter_quantity_before_po == 1000
    assert first["P06"].quarter_quantity_after_po == 1200
    assert first["P06"].tier_discount_percent == 8
    assert first["P06"].correct_unit_price == Decimal("101.20")
    assert first["P07"].quarter_quantity_after_po == 1500

    stored_entered_prices = {
        po.po_id: po.entered_unit_price
        for po in seeded_session.scalars(select(PurchaseOrderLine)).all()
        if po.po_id in original_entered_prices
    }
    assert stored_entered_prices == original_entered_prices

    medpolymer_results = [
        result for result in first.values() if result.agreement_id == "AGR-001"
    ]
    independently_summed_value = sum(
        (result.correct_line_amount for result in medpolymer_results),
        start=Decimal("0.00"),
    )
    expected_rebate = (independently_summed_value * Decimal("0.03")).quantize(
        Decimal("0.01")
    )
    summary = {
        item.agreement_id: item
        for item in calculate_annual_rebates(seeded_session, 2025).rebates
    }["AGR-001"]
    assert summary.eligible_contract_value == independently_summed_value
    assert summary.rebate_earned == expected_rebate
    assert summary.target_first_met_by_po == "P07"


def test_post_threshold_purchase_increases_earned_rebate(seeded_session) -> None:
    seeded_session.add(
        PurchaseOrderLine(
            po_id="P16",
            supplier_id="S1",
            material_code="RESIN-MED",
            purchase_date=date(2025, 12, 15),
            quantity=100,
            entered_unit_price=Decimal("104.50"),
            currency="INR",
        )
    )
    seeded_session.flush()

    p16 = calculate_purchase_order_pricing(seeded_session, "P16")
    summary = {
        item.agreement_id: item
        for item in calculate_annual_rebates(seeded_session, 2025).rebates
    }["AGR-001"]
    assert p16.annual_rebate_earned_after_po == Decimal("8037.30")
    assert p16.rebate_newly_unlocked_by_po == Decimal("313.50")
    assert summary.annual_purchased_quantity == 2700
    assert summary.rebate_earned == Decimal("8037.30")


def test_same_day_purchase_orders_use_po_id_as_tie_breaker(seeded_session) -> None:
    seeded_session.add_all(
        [
            PurchaseOrderLine(
                po_id="P17",
                supplier_id="S1",
                material_code="RESIN-MED",
                purchase_date=date(2025, 8, 1),
                quantity=100,
                entered_unit_price=Decimal("110.00"),
                currency="INR",
            ),
            PurchaseOrderLine(
                po_id="P16",
                supplier_id="S1",
                material_code="RESIN-MED",
                purchase_date=date(2025, 8, 1),
                quantity=400,
                entered_unit_price=Decimal("110.00"),
                currency="INR",
            ),
        ]
    )
    seeded_session.flush()

    results = _by_po(seeded_session)
    assert results["P16"].quarter_quantity_after_po == 400
    assert results["P16"].tier_discount_percent == 0
    assert results["P17"].quarter_quantity_before_po == 400
    assert results["P17"].quarter_quantity_after_po == 500
    assert results["P17"].tier_discount_percent == 5


def test_missing_agreement_raises_clear_domain_error(seeded_session) -> None:
    purchase_order = PurchaseOrderLine(
        po_id="OUTSIDE",
        supplier_id="S1",
        material_code="RESIN-MED",
        purchase_date=date(2026, 1, 1),
        quantity=1,
        entered_unit_price=Decimal("110.00"),
        currency="INR",
    )

    with pytest.raises(AgreementNotFoundError, match="No agreement for PO OUTSIDE"):
        resolve_agreement_version(seeded_session, purchase_order)


def test_ambiguous_agreements_raise_configuration_error(seeded_session) -> None:
    seeded_session.add(
        Agreement(
            agreement_id="AGR-ALT",
            supplier_id="S1",
            material_code="RESIN-MED",
            valid_from=date(2025, 1, 1),
            valid_to=date(2025, 12, 31),
            annual_target_quantity=9999,
            annual_rebate_percent=0,
            currency="INR",
            unit="kg",
        )
    )
    seeded_session.flush()
    purchase_order = seeded_session.get(PurchaseOrderLine, "P01")
    assert purchase_order is not None

    with pytest.raises(PricingConfigurationError, match="multiple active agreements"):
        resolve_agreement_version(seeded_session, purchase_order)


def test_missing_version_raises_clear_domain_error(seeded_session) -> None:
    version = seeded_session.get(AgreementVersion, "AGR-001-V2")
    purchase_order = seeded_session.get(PurchaseOrderLine, "P06")
    assert version is not None and purchase_order is not None
    version.effective_from = date(2025, 5, 16)
    seeded_session.flush()

    with pytest.raises(AgreementVersionNotFoundError, match="No version"):
        resolve_agreement_version(seeded_session, purchase_order)


def test_missing_tier_raises_configuration_error(seeded_session) -> None:
    seeded_session.execute(
        delete(PriceTier).where(PriceTier.tier_id == "AGR-001-V1-T2")
    )
    seeded_session.expire_all()

    with pytest.raises(PricingConfigurationError, match="0 matching price tiers"):
        calculate_purchase_order_pricing(seeded_session, "P02")
