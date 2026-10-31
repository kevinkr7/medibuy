from copy import deepcopy
from datetime import date

import pytest
from sqlalchemy import inspect, select, text
from sqlalchemy.orm import Session, selectinload

from app.models import Agreement, AgreementVersion, PriceTier, PurchaseOrderLine, Supplier
from app.seed import SeedDataError, load_seed_files, seed_database, validate_seed_data


EXPECTED_COUNTS = {
    "suppliers": 3,
    "agreements": 3,
    "agreement_versions": 4,
    "price_tiers": 12,
    "purchase_order_lines": 15,
}


def test_seed_creates_all_five_tables(test_engine) -> None:
    seed_database(test_engine)

    assert set(inspect(test_engine).get_table_names()) == set(EXPECTED_COUNTS)


def test_seed_creates_expected_record_counts(test_engine) -> None:
    counts = seed_database(test_engine)

    assert counts == EXPECTED_COUNTS


def test_foreign_keys_and_relationships_are_valid(test_engine) -> None:
    seed_database(test_engine)

    with test_engine.connect() as connection:
        assert connection.execute(text("PRAGMA foreign_key_check")).all() == []

    with Session(test_engine) as session:
        suppliers = session.scalars(
            select(Supplier).options(
                selectinload(Supplier.agreements),
                selectinload(Supplier.purchase_order_lines),
            )
        ).all()
        assert sum(len(supplier.agreements) for supplier in suppliers) == 3
        assert sum(len(supplier.purchase_order_lines) for supplier in suppliers) == 15


def _medpolymer_versions(test_engine) -> list[AgreementVersion]:
    seed_database(test_engine)

    with Session(test_engine) as session:
        agreement = session.scalar(
            select(Agreement)
            .where(Agreement.agreement_id == "AGR-001")
            .options(selectinload(Agreement.versions))
        )
        assert agreement is not None
        session.expunge_all()
        return agreement.versions


def test_medpolymer_agreement_preserves_both_versions(test_engine) -> None:
    versions = _medpolymer_versions(test_engine)

    assert [version.version_id for version in versions] == ["AGR-001-V1", "AGR-001-V2"]
    assert all(version.agreement_id == "AGR-001" for version in versions)


def test_medpolymer_v1_ends_on_may_14(test_engine) -> None:
    versions = _medpolymer_versions(test_engine)

    assert versions[0].effective_to == date(2025, 5, 14)


def test_medpolymer_v2_starts_on_may_15(test_engine) -> None:
    versions = _medpolymer_versions(test_engine)

    assert versions[1].effective_from == date(2025, 5, 15)


def test_every_version_has_its_price_tiers(test_engine) -> None:
    seed_database(test_engine)

    with Session(test_engine) as session:
        versions = session.scalars(
            select(AgreementVersion).options(selectinload(AgreementVersion.price_tiers))
        ).all()
        assert len(versions) == 4
        assert {version.version_id: len(version.price_tiers) for version in versions} == {
            "AGR-001-V1": 3,
            "AGR-001-V2": 3,
            "AGR-002-V1": 3,
            "AGR-003-V1": 3,
        }


def test_all_original_purchase_orders_and_decimal_prices_are_preserved(test_engine) -> None:
    seed_database(test_engine)

    with Session(test_engine) as session:
        purchase_orders = session.scalars(select(PurchaseOrderLine).order_by(PurchaseOrderLine.po_id)).all()
        assert [po.po_id for po in purchase_orders] == [f"P{number:02d}" for number in range(1, 16)]
        assert str(purchase_orders[5].entered_unit_price) == "110.00"


def test_repeated_seeding_is_idempotent(test_engine) -> None:
    assert seed_database(test_engine) == EXPECTED_COUNTS
    assert seed_database(test_engine) == EXPECTED_COUNTS


def test_overlapping_version_and_tier_configurations_are_rejected() -> None:
    overlapping_versions = deepcopy(load_seed_files())
    overlapping_versions["agreement_versions"][1]["effective_from"] = "2025-05-14"
    with pytest.raises(SeedDataError, match="Overlapping versions"):
        validate_seed_data(overlapping_versions)

    overlapping_tiers = deepcopy(load_seed_files())
    overlapping_tiers["price_tiers"][1]["min_quantity_inclusive"] = 499
    with pytest.raises(SeedDataError, match="Overlapping tiers"):
        validate_seed_data(overlapping_tiers)
