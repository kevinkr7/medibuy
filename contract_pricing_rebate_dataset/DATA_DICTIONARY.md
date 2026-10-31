# Data dictionary and relationships

All five seed files contain **JSON arrays** of objects. Field names are in `snake_case`. IDs and dates are ISO-style strings. Prices are decimal strings for lossless `Decimal` handling.

## `suppliers.json` — supplier/material catalog

| Field | Type | Meaning |
|---|---|---|
| `supplier_id` | string (PK) | Unique supplier ID, e.g. `S1`. |
| `supplier_name` | string | Display name. |
| `material_code` | string | Material bought from this supplier, e.g. `RESIN-MED`. |
| `material_name` | string | Readable material name. |
| `unit` | string | Quantity unit; all samples are `kg`. |

One material per supplier **in this minimal fixture**; production may use separate Suppliers and Materials tables.

## `agreements.json` — annual agreement

| Field | Type | Meaning |
|---|---|---|
| `agreement_id` | string (PK) | Annual agreement ID. |
| `supplier_id` | string (FK) | References `suppliers.supplier_id`. |
| `material_code` | string | Material to which the agreement applies. |
| `valid_from`, `valid_to` | ISO date | Inclusive annual validity window. |
| `annual_target_quantity` | integer | Annual purchased quantity needed to earn rebate. |
| `annual_rebate_percent` | integer | Percent paid back on full eligible contract value after target is met. |
| `currency` | string | `INR` in this fixture. |
| `unit` | string | `kg` in this fixture. |

## `agreement_versions.json` — dated amendments

| Field | Type | Meaning |
|---|---|---|
| `version_id` | string (PK) | A version of a particular agreement, e.g. `AGR-001-V2`. |
| `agreement_id` | string (FK) | References `agreements.agreement_id`. |
| `version_number` | integer | Ordered sequence within the agreement. |
| `effective_from`, `effective_to` | ISO date | **Inclusive** application dates; ranges must not overlap. |
| `base_unit_price` | decimal string | Base INR/kg for POs placed in this window. |
| `change_note` | string | Explanation of original agreement or amendment. |

## `price_tiers.json` — pricing tier for a version

| Field | Type | Meaning |
|---|---|---|
| `tier_id` | string (PK) | Unique tier ID. |
| `version_id` | string (FK) | References `agreement_versions.version_id`. |
| `min_quantity_inclusive` | integer | Lowest quarterly cumulative quantity in this tier. |
| `max_quantity_exclusive` | integer or null | First quantity *outside* the tier; `null` = unbounded. |
| `discount_percent` | integer | Percentage discount applied to entire current line. |

Example: `[500, 1000)` means **500–999 kg**. The table for MedPolymer V1 is 0–499: 0%, 500–999: 5%, 1,000+: 10%. V2 changes the top 10% to 8%.

## `purchase_orders.json` — purchased PO lines

| Field | Type | Meaning |
|---|---|---|
| `po_id` | string (PK) | Unique PO-line ID, e.g. `P06`. |
| `supplier_id` | string (FK) | References `suppliers.supplier_id`. |
| `material_code` | string | Purchased material; match against selected agreement. |
| `purchase_date` | ISO date | Contract version, quarter and year selection date. |
| `quantity` | integer | Positive purchased quantity in kg. |
| `entered_unit_price` | decimal string | **Buyer-entered** INR/kg, intentionally inaccurate on some lines. |
| `currency` | string | Must agree with agreement currency. |

These are **seed inputs**. Never store expected/priced values as inputs to the calculation. Output values live only in `expected_results.json` for tests.

## `expected_results.json` — test oracle (NOT production data)

`purchase_order_results` has one row for each PO: version selected, quarter, cumulative quantities, discount, correct unit/line price, buyer-entered line amount, signed variance, status, and rebate newly unlocked by that line. `year_end_rebates` summarizes targets, annual quantities, eligible value, rebate percent and triggering PO. `portfolio_totals` aggregates both pricing discrepancies and rebates.

### Relationships

```text
Supplier (S1)
  └─ Annual Agreement (AGR-001) [target + year-end rebate]
       ├─ Version 1 (Jan 1–May 14) [base price]
       │    └─ 3 price tiers
       ├─ Version 2 (May 15–Dec 31) [amended base price]
       │    └─ 3 price tiers
       └─ Many PO lines, each date-matched to one active version
```

When implementing SQLAlchemy, use unique constraints for IDs and consider enforcing nonoverlapping version dates and tier intervals in validation logic.
