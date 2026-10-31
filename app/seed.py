"""Validate and load the supplied seed fixture.

Run ``python -m app.seed`` to seed missing records. Run
``python -m app.seed --reset`` to restore the original demonstration state.
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from sqlalchemy import Engine, delete, func, select
from sqlalchemy.orm import Session

from app.database import Base, engine
from app.models import Agreement, AgreementVersion, PriceTier, PurchaseOrderLine, Supplier

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SEED_DIR = PROJECT_ROOT / "contract_pricing_rebate_dataset" / "seed_data"

MODEL_FILES = (
    (Supplier, "suppliers.json", "supplier_id"),
    (Agreement, "agreements.json", "agreement_id"),
    (AgreementVersion, "agreement_versions.json", "version_id"),
    (PriceTier, "price_tiers.json", "tier_id"),
    (PurchaseOrderLine, "purchase_orders.json", "po_id"),
)

REQUIRED_FIELDS = {
    "suppliers": {"supplier_id", "supplier_name", "material_code", "material_name", "unit"},
    "agreements": {
        "agreement_id", "supplier_id", "material_code", "valid_from", "valid_to",
        "annual_target_quantity", "annual_rebate_percent", "currency", "unit",
    },
    "agreement_versions": {
        "version_id", "agreement_id", "version_number", "effective_from", "effective_to",
        "base_unit_price", "change_note",
    },
    "price_tiers": {
        "tier_id", "version_id", "min_quantity_inclusive", "max_quantity_exclusive",
        "discount_percent",
    },
    "purchase_orders": {
        "po_id", "supplier_id", "material_code", "purchase_date", "quantity",
        "entered_unit_price", "currency",
    },
}

DATE_FIELDS = {
    "agreements": ("valid_from", "valid_to"),
    "agreement_versions": ("effective_from", "effective_to"),
    "purchase_orders": ("purchase_date",),
}
DECIMAL_FIELDS = {
    "agreement_versions": ("base_unit_price",),
    "purchase_orders": ("entered_unit_price",),
}


class SeedDataError(ValueError):
    """Raised when fixture data or existing rows conflict with the seed contract."""


def _read_json_array(path: Path) -> list[dict[str, Any]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SeedDataError(f"Cannot read valid JSON from {path}: {exc}") from exc
    if not isinstance(payload, list) or not all(isinstance(row, dict) for row in payload):
        raise SeedDataError(f"{path.name} must contain a JSON array of objects")
    return payload


def load_seed_files(seed_dir: Path = DEFAULT_SEED_DIR) -> dict[str, list[dict[str, Any]]]:
    """Read only the five production seed inputs; expected_results.json is excluded."""

    return {
        "suppliers": _read_json_array(seed_dir / "suppliers.json"),
        "agreements": _read_json_array(seed_dir / "agreements.json"),
        "agreement_versions": _read_json_array(seed_dir / "agreement_versions.json"),
        "price_tiers": _read_json_array(seed_dir / "price_tiers.json"),
        "purchase_orders": _read_json_array(seed_dir / "purchase_orders.json"),
    }


def _parse_date(value: Any, label: str) -> date:
    if not isinstance(value, str):
        raise SeedDataError(f"{label} must be an ISO date string")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise SeedDataError(f"{label} is not a valid ISO date: {value!r}") from exc


def _parse_decimal(value: Any, label: str) -> Decimal:
    if not isinstance(value, str):
        raise SeedDataError(f"{label} must be a decimal string")
    try:
        parsed = Decimal(value)
    except InvalidOperation as exc:
        raise SeedDataError(f"{label} is not a valid decimal: {value!r}") from exc
    if not parsed.is_finite() or parsed.as_tuple().exponent < -2:
        raise SeedDataError(f"{label} must be finite with at most two decimal places")
    return parsed


def _require_exact_fields(data: dict[str, list[dict[str, Any]]]) -> None:
    for group, rows in data.items():
        required = REQUIRED_FIELDS[group]
        for index, row in enumerate(rows):
            missing = required - row.keys()
            extra = row.keys() - required
            if missing or extra:
                raise SeedDataError(
                    f"{group}[{index}] field mismatch; missing={sorted(missing)}, extra={sorted(extra)}"
                )


def _index_unique(rows: list[dict[str, Any]], key: str, group: str) -> dict[str, dict[str, Any]]:
    indexed: dict[str, dict[str, Any]] = {}
    for row in rows:
        value = row[key]
        if not isinstance(value, str) or not value.strip():
            raise SeedDataError(f"{group}.{key} must be a non-empty string")
        if value in indexed:
            raise SeedDataError(f"Duplicate {group}.{key}: {value}")
        indexed[value] = row
    return indexed


def validate_seed_data(data: dict[str, list[dict[str, Any]]]) -> None:
    """Validate required values, references, date windows, and tier ranges."""

    if set(data) != set(REQUIRED_FIELDS):
        raise SeedDataError(f"Expected seed groups: {sorted(REQUIRED_FIELDS)}")
    _require_exact_fields(data)

    suppliers = _index_unique(data["suppliers"], "supplier_id", "suppliers")
    agreements = _index_unique(data["agreements"], "agreement_id", "agreements")
    versions = _index_unique(data["agreement_versions"], "version_id", "agreement_versions")
    _index_unique(data["price_tiers"], "tier_id", "price_tiers")
    _index_unique(data["purchase_orders"], "po_id", "purchase_orders")

    for supplier in suppliers.values():
        for field in ("supplier_name", "material_code", "material_name", "unit"):
            if not isinstance(supplier[field], str) or not supplier[field].strip():
                raise SeedDataError(f"Supplier {supplier['supplier_id']} has invalid {field}")

    agreements_by_scope: dict[tuple[str, str], list[tuple[date, date, str]]] = defaultdict(list)
    for agreement in agreements.values():
        supplier = suppliers.get(agreement["supplier_id"])
        if supplier is None:
            raise SeedDataError(f"Agreement {agreement['agreement_id']} has unknown supplier")
        if agreement["material_code"] != supplier["material_code"]:
            raise SeedDataError(f"Agreement {agreement['agreement_id']} material does not match supplier")
        if agreement["unit"] != supplier["unit"]:
            raise SeedDataError(f"Agreement {agreement['agreement_id']} unit does not match supplier")
        valid_from = _parse_date(agreement["valid_from"], f"{agreement['agreement_id']}.valid_from")
        valid_to = _parse_date(agreement["valid_to"], f"{agreement['agreement_id']}.valid_to")
        if valid_from > valid_to:
            raise SeedDataError(f"Agreement {agreement['agreement_id']} has an inverted validity range")
        if not isinstance(agreement["annual_target_quantity"], int) or agreement["annual_target_quantity"] <= 0:
            raise SeedDataError(f"Agreement {agreement['agreement_id']} target must be positive")
        rebate = agreement["annual_rebate_percent"]
        if not isinstance(rebate, int) or not 0 <= rebate <= 100:
            raise SeedDataError(f"Agreement {agreement['agreement_id']} rebate percent is invalid")
        for field in ("currency", "unit"):
            if not isinstance(agreement[field], str) or not agreement[field].strip():
                raise SeedDataError(f"Agreement {agreement['agreement_id']} has invalid {field}")
        agreements_by_scope[(agreement["supplier_id"], agreement["material_code"])].append(
            (valid_from, valid_to, agreement["agreement_id"])
        )

    for scope_agreements in agreements_by_scope.values():
        ordered = sorted(scope_agreements)
        for older, newer in zip(ordered, ordered[1:]):
            if newer[0] <= older[1]:
                raise SeedDataError(f"Overlapping agreements: {older[2]} and {newer[2]}")

    versions_by_agreement: dict[str, list[tuple[date, date, str]]] = defaultdict(list)
    version_numbers: set[tuple[str, int]] = set()
    for version in versions.values():
        agreement = agreements.get(version["agreement_id"])
        if agreement is None:
            raise SeedDataError(f"Version {version['version_id']} has unknown agreement")
        number = version["version_number"]
        if not isinstance(number, int) or number <= 0:
            raise SeedDataError(f"Version {version['version_id']} number must be positive")
        number_key = (version["agreement_id"], number)
        if number_key in version_numbers:
            raise SeedDataError(f"Duplicate version number for {version['agreement_id']}: {number}")
        version_numbers.add(number_key)
        effective_from = _parse_date(version["effective_from"], f"{version['version_id']}.effective_from")
        effective_to = _parse_date(version["effective_to"], f"{version['version_id']}.effective_to")
        agreement_from = _parse_date(agreement["valid_from"], f"{agreement['agreement_id']}.valid_from")
        agreement_to = _parse_date(agreement["valid_to"], f"{agreement['agreement_id']}.valid_to")
        if effective_from > effective_to:
            raise SeedDataError(f"Version {version['version_id']} has an inverted date range")
        if effective_from < agreement_from or effective_to > agreement_to:
            raise SeedDataError(f"Version {version['version_id']} lies outside its agreement")
        if _parse_decimal(version["base_unit_price"], f"{version['version_id']}.base_unit_price") < 0:
            raise SeedDataError(f"Version {version['version_id']} price cannot be negative")
        if not isinstance(version["change_note"], str):
            raise SeedDataError(f"Version {version['version_id']} change_note must be a string")
        versions_by_agreement[version["agreement_id"]].append(
            (effective_from, effective_to, version["version_id"])
        )

    for agreement_id in agreements:
        ordered = sorted(versions_by_agreement.get(agreement_id, []))
        if not ordered:
            raise SeedDataError(f"Agreement {agreement_id} has no versions")
        for older, newer in zip(ordered, ordered[1:]):
            if newer[0] <= older[1]:
                raise SeedDataError(f"Overlapping versions: {older[2]} and {newer[2]}")

    tiers_by_version: dict[str, list[tuple[int, int | None, str]]] = defaultdict(list)
    for tier in data["price_tiers"]:
        if tier["version_id"] not in versions:
            raise SeedDataError(f"Tier {tier['tier_id']} has unknown agreement version")
        minimum = tier["min_quantity_inclusive"]
        maximum = tier["max_quantity_exclusive"]
        discount = tier["discount_percent"]
        if not isinstance(minimum, int) or minimum < 0:
            raise SeedDataError(f"Tier {tier['tier_id']} minimum is invalid")
        if maximum is not None and (not isinstance(maximum, int) or maximum <= minimum):
            raise SeedDataError(f"Tier {tier['tier_id']} maximum is invalid")
        if not isinstance(discount, int) or not 0 <= discount <= 100:
            raise SeedDataError(f"Tier {tier['tier_id']} discount is invalid")
        tiers_by_version[tier["version_id"]].append((minimum, maximum, tier["tier_id"]))

    for version_id in versions:
        ordered = sorted(tiers_by_version.get(version_id, []), key=lambda tier: tier[0])
        if not ordered:
            raise SeedDataError(f"Version {version_id} has no price tiers")
        if ordered[0][0] != 0:
            raise SeedDataError(f"Version {version_id} tiers must begin at zero")
        for older, newer in zip(ordered, ordered[1:]):
            if older[1] is None or newer[0] < older[1]:
                raise SeedDataError(f"Overlapping tiers: {older[2]} and {newer[2]}")
            if newer[0] != older[1]:
                raise SeedDataError(f"Gap between tiers: {older[2]} and {newer[2]}")
        if ordered[-1][1] is not None:
            raise SeedDataError(f"Version {version_id} must end with an unbounded tier")

    for po in data["purchase_orders"]:
        supplier = suppliers.get(po["supplier_id"])
        if supplier is None:
            raise SeedDataError(f"PO {po['po_id']} has unknown supplier")
        if po["material_code"] != supplier["material_code"]:
            raise SeedDataError(f"PO {po['po_id']} material does not match supplier")
        if not isinstance(po["quantity"], int) or po["quantity"] <= 0:
            raise SeedDataError(f"PO {po['po_id']} quantity must be positive")
        if _parse_decimal(po["entered_unit_price"], f"{po['po_id']}.entered_unit_price") < 0:
            raise SeedDataError(f"PO {po['po_id']} price cannot be negative")
        purchase_date = _parse_date(po["purchase_date"], f"{po['po_id']}.purchase_date")
        matching_agreements = [
            agreement for agreement in agreements.values()
            if agreement["supplier_id"] == po["supplier_id"]
            and agreement["material_code"] == po["material_code"]
            and _parse_date(agreement["valid_from"], "valid_from") <= purchase_date
            <= _parse_date(agreement["valid_to"], "valid_to")
        ]
        if len(matching_agreements) != 1:
            raise SeedDataError(f"PO {po['po_id']} must match exactly one active agreement")
        agreement = matching_agreements[0]
        if po["currency"] != agreement["currency"]:
            raise SeedDataError(f"PO {po['po_id']} currency does not match agreement")
        matching_versions = [
            window for window in versions_by_agreement[agreement["agreement_id"]]
            if window[0] <= purchase_date <= window[1]
        ]
        if len(matching_versions) != 1:
            raise SeedDataError(f"PO {po['po_id']} must match exactly one active agreement version")


def _converted_rows(data: dict[str, list[dict[str, Any]]], group: str) -> list[dict[str, Any]]:
    converted: list[dict[str, Any]] = []
    for source in data[group]:
        row = dict(source)
        for field in DATE_FIELDS.get(group, ()):
            row[field] = _parse_date(row[field], f"{group}.{field}")
        for field in DECIMAL_FIELDS.get(group, ()):
            row[field] = _parse_decimal(row[field], f"{group}.{field}")
        converted.append(row)
    return converted


def _assert_existing_matches(existing: Any, values: dict[str, Any], primary_key: str) -> None:
    mismatched = [field for field, expected in values.items() if getattr(existing, field) != expected]
    if mismatched:
        identity = values[primary_key]
        raise SeedDataError(
            f"Existing {type(existing).__name__} {identity} conflicts in fields: {', '.join(mismatched)}"
        )


def seed_database(
    database_engine: Engine = engine,
    seed_dir: Path = DEFAULT_SEED_DIR,
    *,
    reset: bool = False,
) -> dict[str, int]:
    """Validate and transactionally seed the database, returning table counts."""

    data = load_seed_files(seed_dir)
    validate_seed_data(data)

    Base.metadata.create_all(database_engine)
    with Session(database_engine) as session, session.begin():
        if reset:
            for model in (PurchaseOrderLine, PriceTier, AgreementVersion, Agreement, Supplier):
                session.execute(delete(model))

        for model, filename, primary_key in MODEL_FILES:
            group = filename.removesuffix(".json")
            for values in _converted_rows(data, group):
                existing = session.get(model, values[primary_key])
                if existing is None:
                    session.add(model(**values))
                    session.flush()
                else:
                    _assert_existing_matches(existing, values, primary_key)

    with Session(database_engine) as session:
        return {
            model.__tablename__: session.scalar(select(func.count()).select_from(model)) or 0
            for model, _, _ in MODEL_FILES
        }


def main() -> None:
    parser = argparse.ArgumentParser(description="Load the original MediBuy seed fixture")
    parser.add_argument(
        "--reset",
        action="store_true",
        help="delete application rows and restore the original 15-PO fixture",
    )
    args = parser.parse_args()
    action = "Reset and seeded" if args.reset else "Seeded"
    try:
        counts = seed_database(reset=args.reset)
    except SeedDataError as exc:
        parser.exit(1, f"Seed failed: {exc}\n")
    formatted = ", ".join(f"{table}={count}" for table, count in counts.items())
    print(f"{action} {engine.url.database}: {formatted}")


if __name__ == "__main__":
    main()
