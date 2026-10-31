from collections.abc import Iterator
from decimal import Decimal, ROUND_HALF_UP

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.main import app
from app.models import PurchaseOrderLine
from app.seed import seed_database


@pytest.fixture
def api_client(test_engine) -> Iterator[tuple[TestClient, object]]:
    seed_database(test_engine)

    def override_get_db():
        with Session(test_engine) as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as client:
        yield client, test_engine
    app.dependency_overrides.clear()


def test_health_endpoint(api_client) -> None:
    client, _ = api_client

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_suppliers_endpoint_returns_three_suppliers(api_client) -> None:
    client, _ = api_client

    response = client.get("/suppliers")

    assert response.status_code == 200
    assert [supplier["supplier_id"] for supplier in response.json()] == ["S1", "S2", "S3"]


def test_agreements_endpoint_returns_nested_versions_and_tiers(api_client) -> None:
    client, _ = api_client

    response = client.get("/agreements")

    assert response.status_code == 200
    agreements = response.json()
    assert len(agreements) == 3
    medpolymer = next(item for item in agreements if item["agreement_id"] == "AGR-001")
    assert [version["version_id"] for version in medpolymer["versions"]] == [
        "AGR-001-V1",
        "AGR-001-V2",
    ]
    assert medpolymer["versions"][0]["effective_to"] == "2025-05-14"
    assert medpolymer["versions"][1]["effective_from"] == "2025-05-15"
    assert medpolymer["versions"][1]["base_unit_price"] == "110.00"
    assert all(len(version["price_tiers"]) == 3 for version in medpolymer["versions"])


def test_purchase_orders_endpoint_returns_current_chronological_history(api_client) -> None:
    client, _ = api_client

    response = client.get("/purchase-orders")

    assert response.status_code == 200
    purchase_orders = response.json()
    assert len(purchase_orders) == 15
    sort_keys = [(item["purchase_date"], item["po_id"]) for item in purchase_orders]
    assert sort_keys == sorted(sort_keys)


@pytest.mark.parametrize(
    ("po_id", "version_id", "unit_price"),
    [
        ("P06", "AGR-001-V2", "104.50"),
        ("P07", "AGR-001-V2", "101.20"),
    ],
)
def test_purchase_order_price_endpoint(api_client, po_id, version_id, unit_price) -> None:
    client, _ = api_client

    response = client.get(f"/purchase-orders/{po_id}/price")

    assert response.status_code == 200
    payload = response.json()
    assert payload["agreement_version_id"] == version_id
    assert payload["correct_unit_price"] == unit_price
    assert isinstance(payload["correct_unit_price"], str)


def test_p06_price_response_matches_contract(api_client) -> None:
    client, _ = api_client

    payload = client.get("/purchase-orders/P06/price").json()

    assert payload == {
        "po_id": "P06",
        "supplier_id": "S1",
        "material_code": "RESIN-MED",
        "purchase_date": "2025-05-15",
        "quantity": 200,
        "currency": "INR",
        "agreement_id": "AGR-001",
        "agreement_version_id": "AGR-001-V2",
        "quarter": "2025-Q2",
        "quarter_quantity_before_po": 500,
        "quarter_quantity_after_po": 700,
        "annual_quantity_after_po": 1700,
        "tier_discount_percent": 5,
        "base_unit_price": "110.00",
        "entered_unit_price": "110.00",
        "correct_unit_price": "104.50",
        "correct_line_amount": "20900.00",
        "entered_line_amount": "22000.00",
        "variance_amount": "1100.00",
        "status": "OVERCHARGED",
        "annual_rebate_earned_after_po": "0.00",
        "rebate_newly_unlocked_by_po": "0.00",
    }


def test_rebates_endpoint_returns_expected_2025_totals(api_client) -> None:
    client, _ = api_client

    response = client.get("/rebates/2025")

    assert response.status_code == 200
    payload = response.json()
    assert payload["currency"] == "INR"
    assert {item["agreement_id"]: item["rebate_earned"] for item in payload["rebates"]} == {
        "AGR-001": "7723.80",
        "AGR-002": "1206.00",
        "AGR-003": "2931.20",
    }
    assert payload["total_rebate_earned"] == "11861.00"


def test_dashboard_returns_seeded_summary(api_client) -> None:
    client, _ = api_client

    response = client.get("/dashboard")

    assert response.status_code == 200
    assert response.json() == {
        "total_suppliers": 3,
        "total_agreements": 3,
        "total_purchase_orders": 15,
        "overcharged_purchase_orders": 7,
        "undercharged_purchase_orders": 1,
        "total_overcharge_amount": "6860.00",
        "total_undercharge_amount": "400.00",
        "total_eligible_contract_value": "391040.00",
        "total_earned_rebate": "11861.00",
    }


def test_post_purchase_order_creates_and_persists_valid_po(api_client) -> None:
    client, _ = api_client
    request = {
        "po_id": "P16",
        "supplier_id": "S1",
        "material_code": "RESIN-MED",
        "purchase_date": "2025-08-03",
        "quantity": 50,
        "entered_unit_price": "110.00",
        "currency": "INR",
    }

    response = client.post("/purchase-orders", json=request)

    assert response.status_code == 201
    assert response.json()["po_id"] == "P16"
    assert response.json()["correct_unit_price"] == "110.00"
    assert client.get("/purchase-orders/P16/price").status_code == 200
    assert len(client.get("/purchase-orders").json()) == 16


def test_new_purchase_updates_later_annual_calculations(api_client) -> None:
    client, _ = api_client
    original_rebate = next(
        item
        for item in client.get("/rebates/2025").json()["rebates"]
        if item["agreement_id"] == "AGR-001"
    )
    original_dashboard = client.get("/dashboard").json()
    added_contract_value = Decimal("110.00") * 50
    expected_eligible_value = (
        Decimal(original_rebate["eligible_contract_value"]) + added_contract_value
    )
    expected_rebate = (expected_eligible_value * Decimal("0.03")).quantize(
        Decimal("0.01"),
        rounding=ROUND_HALF_UP,
    )
    response = client.post(
        "/purchase-orders",
        json={
            "po_id": "P16",
            "supplier_id": "S1",
            "material_code": "RESIN-MED",
            "purchase_date": "2025-08-03",
            "quantity": 50,
            "entered_unit_price": "110.00",
            "currency": "INR",
        },
    )
    assert response.status_code == 201

    p08 = client.get("/purchase-orders/P08/price").json()
    medpolymer = next(
        item
        for item in client.get("/rebates/2025").json()["rebates"]
        if item["agreement_id"] == "AGR-001"
    )
    assert p08["annual_quantity_after_po"] == 2650
    assert Decimal(p08["annual_rebate_earned_after_po"]) == expected_rebate
    assert Decimal(medpolymer["eligible_contract_value"]) == expected_eligible_value
    assert Decimal(medpolymer["rebate_earned"]) == expected_rebate
    updated_dashboard = client.get("/dashboard").json()
    assert Decimal(updated_dashboard["total_eligible_contract_value"]) == (
        Decimal(original_dashboard["total_eligible_contract_value"]) + added_contract_value
    )


def test_backdated_post_recalculates_affected_later_po(api_client) -> None:
    client, _ = api_client
    before = client.get("/purchase-orders/P01/price").json()
    assert before["quarter_quantity_after_po"] == 300
    assert before["correct_unit_price"] == "100.00"

    response = client.post(
        "/purchase-orders",
        json={
            "po_id": "P00",
            "supplier_id": "S1",
            "material_code": "RESIN-MED",
            "purchase_date": "2025-01-05",
            "quantity": 250,
            "entered_unit_price": "100.00",
            "currency": "INR",
        },
    )

    assert response.status_code == 201
    after = client.get("/purchase-orders/P01/price").json()
    assert after["quarter_quantity_before_po"] == 250
    assert after["quarter_quantity_after_po"] == 550
    assert after["tier_discount_percent"] == 5
    assert after["correct_unit_price"] == "95.00"


@pytest.mark.parametrize(
    "changes",
    [
        {"quantity": 0},
        {"quantity": -1},
        {"entered_unit_price": "-0.01"},
        {"entered_unit_price": "100.001"},
        {"currency": "inr"},
    ],
)
def test_invalid_payloads_return_consistent_422(api_client, changes) -> None:
    client, _ = api_client
    request = {
        "po_id": "P16",
        "supplier_id": "S1",
        "material_code": "RESIN-MED",
        "purchase_date": "2025-08-03",
        "quantity": 50,
        "entered_unit_price": "110.00",
        "currency": "INR",
    }
    request.update(changes)

    response = client.post("/purchase-orders", json=request)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_material_mismatch_returns_422(api_client) -> None:
    client, _ = api_client

    response = client.post(
        "/purchase-orders",
        json={
            "po_id": "P16",
            "supplier_id": "S1",
            "material_code": "LATEX-MED",
            "purchase_date": "2025-08-03",
            "quantity": 50,
            "entered_unit_price": "110.00",
            "currency": "INR",
        },
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "material_mismatch"


def test_unknown_supplier_returns_404_without_insert(api_client) -> None:
    client, test_engine = api_client

    response = client.post(
        "/purchase-orders",
        json={
            "po_id": "P16",
            "supplier_id": "UNKNOWN",
            "material_code": "RESIN-MED",
            "purchase_date": "2025-08-03",
            "quantity": 50,
            "entered_unit_price": "110.00",
            "currency": "INR",
        },
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "supplier_not_found"
    with Session(test_engine) as session:
        assert session.get(PurchaseOrderLine, "P16") is None


def test_currency_mismatch_returns_422_and_rolls_back(api_client) -> None:
    client, test_engine = api_client

    response = client.post(
        "/purchase-orders",
        json={
            "po_id": "P16",
            "supplier_id": "S1",
            "material_code": "RESIN-MED",
            "purchase_date": "2025-08-03",
            "quantity": 50,
            "entered_unit_price": "110.00",
            "currency": "USD",
        },
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_purchase_order"
    with Session(test_engine) as session:
        assert session.get(PurchaseOrderLine, "P16") is None


def test_duplicate_po_id_returns_409(api_client) -> None:
    client, _ = api_client

    response = client.post(
        "/purchase-orders",
        json={
            "po_id": "P01",
            "supplier_id": "S1",
            "material_code": "RESIN-MED",
            "purchase_date": "2025-08-03",
            "quantity": 50,
            "entered_unit_price": "110.00",
            "currency": "INR",
        },
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "duplicate_po_id"


def test_missing_po_id_returns_404(api_client) -> None:
    client, _ = api_client

    response = client.get("/purchase-orders/DOES-NOT-EXIST/price")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "purchase_order_not_found"


def test_failed_post_rolls_back_insert(api_client) -> None:
    client, test_engine = api_client

    response = client.post(
        "/purchase-orders",
        json={
            "po_id": "OUTSIDE",
            "supplier_id": "S1",
            "material_code": "RESIN-MED",
            "purchase_date": "2026-01-01",
            "quantity": 1,
            "entered_unit_price": "110.00",
            "currency": "INR",
        },
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "agreement_not_found"
    with Session(test_engine) as session:
        count = session.scalar(select(func.count()).select_from(PurchaseOrderLine))
        assert count == 15
        assert session.get(PurchaseOrderLine, "OUTSIDE") is None


def test_docs_and_openapi_are_available(api_client) -> None:
    client, _ = api_client

    assert client.get("/docs").status_code == 200
    openapi = client.get("/openapi.json")
    assert openapi.status_code == 200
    expected_paths = {
        "/health",
        "/suppliers",
        "/agreements",
        "/purchase-orders",
        "/purchase-orders/{po_id}/price",
        "/rebates/{year}",
        "/dashboard",
    }
    assert expected_paths <= set(openapi.json()["paths"])



@pytest.mark.parametrize(
    "origin",
    [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
)
def test_cors_allows_explicit_local_frontend_origins(api_client, origin) -> None:
    client, _ = api_client

    simple = client.get("/health", headers={"Origin": origin})
    assert simple.status_code == 200
    assert simple.headers["access-control-allow-origin"] == origin

    preflight = client.options(
        "/purchase-orders",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert preflight.status_code == 200
    assert preflight.headers["access-control-allow-origin"] == origin


def test_cors_does_not_allow_unconfigured_origin(api_client) -> None:
    client, _ = api_client

    response = client.get("/health", headers={"Origin": "http://example.com"})

    assert response.status_code == 200
    assert "access-control-allow-origin" not in response.headers
