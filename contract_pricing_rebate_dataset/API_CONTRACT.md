# Suggested REST API contract — share unchanged with Codex and Lovable

**Purpose:** A minimal backend to verify each purchased PO line and calculate earned year-end rebates. Response prices/amounts should be **JSON strings with two decimal places** for reliable display (e.g. `"104.50"`). Quantity and percentage fields are numbers. All dates are `YYYY-MM-DD`.

**Important:** The following routes are an **implementation proposal**, not requirements stated by the interviewer. The dataset is authoritative; the implementation must compute results, not read `expected_results.json` for API responses.

## Read routes

- `GET /suppliers` — all supplier/material records.
- `GET /agreements` — annual agreements, versions, tiers (can be nested objects in response).
- `GET /purchase-orders` — seeded and newly added PO rows with optional computed correctness summary.
- `GET /purchase-orders/{po_id}/price` — version and tier used, correct price, entered price, and variance for a PO.
- `GET /rebates/{year}` — rebate earned per annual agreement and total.
- `GET /dashboard` — PO count, discrepancy totals, total rebates earned.

## Write route

`POST /purchase-orders` — persist one new purchased PO line. Return `201` with the new line ID and its computed verification (or a link to its verification). Required JSON keys:

```json
{
  "po_id": "P16",
  "supplier_id": "S1",
  "material_code": "RESIN-MED",
  "purchase_date": "2025-08-03",
  "quantity": 50,
  "entered_unit_price": "110.00",
  "currency": "INR"
}
```

**Warning:** This is an *example additional PO*, not part of the frozen 15-line fixture. Inserting it changes annual totals, and possibly prices of later POs. Reset seed data before comparing to `expected_results.json`.

## Example: `GET /purchase-orders/P06/price`

```json
{
  "po_id": "P06",
  "agreement_id": "AGR-001",
  "agreement_version_id": "AGR-001-V2",
  "quarter": "2025-Q2",
  "quarter_quantity_after_po": 700,
  "tier_discount_percent": 5,
  "base_unit_price": "110.00",
  "correct_unit_price": "104.50",
  "entered_unit_price": "110.00",
  "correct_line_amount": "20900.00",
  "entered_line_amount": "22000.00",
  "variance_amount": "1100.00",
  "status": "OVERCHARGED"
}
```

## Example: `GET /rebates/2025`

```json
{
  "year": 2025,
  "currency": "INR",
  "rebates": [
    {"agreement_id": "AGR-001", "supplier_id": "S1", "annual_purchased_quantity": 2600, "annual_target_quantity": 2500, "target_met": true, "eligible_contract_value": "257460.00", "rebate_percent": 3, "rebate_earned": "7723.80"},
    {"agreement_id": "AGR-002", "supplier_id": "S2", "annual_purchased_quantity": 1050, "annual_target_quantity": 1000, "target_met": true, "eligible_contract_value": "60300.00", "rebate_percent": 2, "rebate_earned": "1206.00"},
    {"agreement_id": "AGR-003", "supplier_id": "S3", "annual_purchased_quantity": 950, "annual_target_quantity": 900, "target_met": true, "eligible_contract_value": "73280.00", "rebate_percent": 4, "rebate_earned": "2931.20"}
  ],
  "total_rebate_earned": "11861.00"
}
```

## Error behavior

- `422` invalid quantity, price, currency, date or material mismatch.
- `404` unknown PO, supplier/agreement, or no agreement effective on the PO date (choose this interpretation consistently).
- `409` duplicate PO ID or contradictory agreement configuration.

Use FastAPI/Pydantic validation and `Decimal` for money. Permit local development frontend origins via explicit CORS configuration. For demonstration, seeded database state should be resettable to the original dataset.

## Minimum frontend

One responsive page with **(1) supplier/agreement viewer, (2) PO form and price verification table, (3) year-end rebate summary**. Show correct price, buyer-entered price, signed variance/status and year-end rebate *separately*. A frontend never implements its own pricing business logic.
