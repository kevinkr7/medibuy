# MediBuy API Guide

## Base URL

Use `http://127.0.0.1:8000` for a local interview demo. The frontend should read
the base URL from `VITE_API_BASE_URL` and must not embed pricing or rebate rules.

Swagger is available at `/docs`; the generated machine-readable contract is
`/openapi.json` and is also included beside this guide.

## Endpoints

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/health` | Service health |
| `GET` | `/suppliers` | Supplier and material catalog |
| `GET` | `/agreements` | Agreements, dated versions and price tiers |
| `GET` | `/purchase-orders` | Chronological POs with calculated verification |
| `GET` | `/purchase-orders/{po_id}/price` | Verification for one PO |
| `POST` | `/purchase-orders` | Validate, persist and calculate a new PO |
| `GET` | `/rebates/{year}` | Earned rebate summary for a calendar year |
| `GET` | `/dashboard` | Portfolio counts and financial totals |

## Create a purchase order

Send `Content-Type: application/json` with all seven fields:

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

`quantity` must be a positive integer. `entered_unit_price` must be nonnegative
with no more than two decimal places. Currency is a three-letter uppercase code.
The supplier, material, currency, purchase date, agreement and agreement version
must agree. A successful request returns `201` and the full calculated PO result.

Creating a backdated PO can change later rows. Refresh the PO list, annual rebate
report and dashboard after every successful POST.

## Important response fields

- `agreement_version_id` identifies the contract terms selected by purchase date.
- `quarter_quantity_before_po` and `quarter_quantity_after_po` explain tier selection.
- `entered_unit_price` is the buyer-entered input and is never overwritten.
- `correct_unit_price` and `correct_line_amount` are derived contract amounts.
- `variance_amount` is entered line value minus correct line value.
- `status` is `MATCH`, `OVERCHARGED` or `UNDERCHARGED`.
- `rebate_earned` means the annual target was achieved. It does not describe
  payment, claim or credit-note status.

Show price variance and earned rebate in separate UI sections. Display a positive
variance as a potential overcharge and a negative variance as an undercharge.

## Serialization

All money fields are JSON strings with exactly two decimal places, such as
`"104.50"`. Parse them with a decimal-safe money library if arithmetic is needed;
do not use binary floating-point values for financial totals. Dates are ISO
`YYYY-MM-DD`. Quantities and percentages are JSON numbers.

## Errors

Errors use one envelope:

```json
{
  "error": {
    "code": "duplicate_po_id",
    "message": "PO P01 already exists"
  }
}
```

Validation errors also contain an `error.details` array.

| Status | Meaning |
| --- | --- |
| `404` | Unknown PO or supplier, or no agreement/version for the date |
| `409` | Duplicate PO or contradictory pricing configuration |
| `422` | Invalid payload, material mismatch or currency mismatch |

Use `error.message` for a concise form error and retain `error.code` for stable UI
branching.
