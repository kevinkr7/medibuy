# Contract Pricing & Rebate Tracker — Interview Dataset

A **fully synthetic, self-contained fixture** for a 90-minute procurement-pricing backend assessment. No real companies or contracts are represented. This ZIP is **sample data plus expected outputs and documentation**, not a finished backend.

## What the backend must do

1. Given a purchase-order (PO) line, find the supplier/material agreement version effective on its purchase date.
2. Find the discount tier from the **cumulative quantity purchased in that calendar quarter, including the current PO**; return its correct contract unit price and flag discrepancies from the buyer's entered price.
3. Track the annual purchase target. As soon as it is met, calculate the year-end rebate on **all** eligible contract-priced purchases that year, including earlier ones. Do **not** overwrite PO prices when rebates accrue.

## What's included

```text
contract_pricing_rebate_dataset/
├── seed_data/
│   ├── suppliers.json                 # 3 suppliers / 3 medical materials
│   ├── agreements.json                # 3 annual contracts with rebate targets
│   ├── agreement_versions.json        # 4 records; AGR-001 amended on May 15
│   ├── price_tiers.json               # 12 version-scoped quarterly discount tiers
│   └── purchase_orders.json           # 15 intentionally mixed-correctness PO lines
├── expected_results.json              # frozen, independently checked test oracle
├── BUSINESS_RULES.md                  # important interpretation choices and formulas
├── DATA_DICTIONARY.md                 # field-level schema and relationships
├── TEST_CASES.md                      # acceptance tests with numeric outputs
├── API_CONTRACT.md                    # suggested shared contract for Codex + Lovable
└── validate_dataset.py                # standard-library-only integrity check
```

## Dataset at a glance

| Supplier | Agreement | Material | Base unit price | Annual target | Annual rebate |
|---|---|---|---|---:|---:|
| MedPolymer (S1) | AGR-001 | Resin | INR 100.00 (V1), INR 110.00 (V2) | 2,500 kg | 3% |
| PureLatex (S2) | AGR-002 | Latex | INR 60.00 | 1,000 kg | 2% |
| SteriPack (S3) | AGR-003 | Film | INR 80.00 | 900 kg | 4% |

All agreements cover **2025-01-01 through 2025-12-31**. AGR-001's Version 1 ends on **2025-05-14**, and Version 2 begins on **2025-05-15** — an amendment in the middle of Q2. Versions remain part of **one** annual agreement and its rebate target.

**Exact tier boundary:** MedPolymer PO **P02** takes Q1 quantity from 300 kg to **500 kg**, so the 5% tier applies to P02. **Mid-quarter amendment:** PO **P05** is May 14 (V1); PO **P06** is May 15 (V2), while both share the Q2 accumulated quantity. **Annual retroactive rebate:** PO **P08** pushes MedPolymer's yearly quantity from 2,000 kg to 2,600 kg, unlocking a 3% rebate on *all* its eligible 2025 contract value.

## Final expected totals (2025)

| Supplier | Year quantity | Contract-priced value | Earned year-end rebate |
|---|---:|---:|---:|
| MedPolymer | 2,600 kg | INR 257,460.00 | INR 7,723.80 |
| PureLatex | 1,050 kg | INR 60,300.00 | INR 1,206.00 |
| SteriPack | 950 kg | INR 73,280.00 | INR 2,931.20 |
| **Total** | | **INR 391,040.00** | **INR 11,861.00** |

Buyer-entered PO values sum to **INR 397,500.00**, comprising potential overcharges of **INR 6,860.00** and undercharges of **INR 400.00** (net overcharge **INR 6,460.00**). Pricing discrepancies and earned rebates are **different accounting concepts** and should not be conflated. The net contract value after earned rebates is **INR 379,179.00**; this is illustrative net procurement cost, not an invoice or receipt ledger.

## Start here

1. Read `BUSINESS_RULES.md` before implementing. The original interview statement does not specify every pricing detail, so the chosen interpretations are explicit and consistent.
2. Load the five JSON arrays from `seed_data/` into SQLite using your chosen FastAPI/SQLAlchemy models. Treat `expected_results.json` as **test-only**; never import correct prices or rebates from it into production calculations.
3. Run `python validate_dataset.py` from this extracted folder. It checks cross-file references, period coverage, tier boundaries, expected price math, histories and totals without installing packages.
4. Implement the endpoints defined in `API_CONTRACT.md`, then write pytest assertions using the frozen expectations and acceptance cases in `TEST_CASES.md`.
5. Connect Lovable to the same API contract. A simple page with PO verification, agreement history and year-end rebate summary is sufficient.

Prices are stored as **decimal strings** for safe conversion to Python `Decimal`. Quantity and discount percentages are integers. All samples use `INR` and `kg`. Records are ordered by PO ID in the input file, **not globally by purchase date**; always sort chronologically by `(purchase_date, po_id)` before calculating cumulative quantities.
