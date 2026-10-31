# Acceptance tests — fixed input data and expected outputs

The 15 seeded POs in `seed_data/purchase_orders.json` are **input**. Use `expected_results.json` only in automated tests, never in your pricing endpoint logic.

## Price verification for every PO line

`Variance = buyer-entered line value - correct contract line value`. Positive is potential overcharge; negative is potential undercharge.

| PO | Version | Quarter quantity after | Discount | Correct unit INR | Correct line INR | Variance INR |
|---|---|---:|---:|---:|---:|---:|
| P01 | AGR-001-V1 | 300 | 0% | 100.00 | 30,000.00 | 0.00 |
| P02 | AGR-001-V1 | **500** | **5%** | 95.00 | 19,000.00 | +1,000.00 |
| P03 | AGR-001-V1 | **1,000** | **10%** | 90.00 | 45,000.00 | 0.00 |
| P04 | AGR-001-V1 | 400 | 0% | 100.00 | 40,000.00 | 0.00 |
| P05 | AGR-001-V1 | **500** | 5% | 95.00 | 9,500.00 | +500.00 |
| P06 | **AGR-001-V2** | 700 | 5% | 104.50 | 20,900.00 | +1,100.00 |
| P07 | AGR-001-V2 | **1,000** | **8%** | 101.20 | 30,360.00 | +2,640.00 |
| P08 | AGR-001-V2 | 600 | 5% | 104.50 | 62,700.00 | 0.00 |
| P09 | AGR-002-V1 | **300** | 5% | 57.00 | 17,100.00 | +900.00 |
| P10 | AGR-002-V1 | **600** | 10% | 54.00 | 16,200.00 | 0.00 |
| P11 | AGR-002-V1 | 250 | 0% | 60.00 | 15,000.00 | 0.00 |
| P12 | AGR-002-V1 | 200 | 0% | 60.00 | 12,000.00 | **−400.00** |
| P13 | AGR-003-V1 | **200** | 2% | 78.40 | 15,680.00 | +320.00 |
| P14 | AGR-003-V1 | **500** | 5% | 76.00 | 38,000.00 | 0.00 |
| P15 | AGR-003-V1 | 250 | 2% | 78.40 | 19,600.00 | +400.00 |

## Essential positive scenarios

1. **Exact tier boundary:** P02 hits 500 kg, not 499, so the MedPolymer Q1 discount is 5%, not 0%.
2. **Another boundary:** P03 hits 1,000 kg, so its own Q1 discount is 10%; earlier P01/P02 remain at their historical prices.
3. **Mid-quarter amendment:** P05 on May 14 selects V1; P06 on May 15 selects V2. The cumulative Q2 quantity for P06 is 700 kg, **not 200 kg**.
4. **Amended tier table:** P07 reaches 1,000 kg in Q2. It uses V2's 8% highest discount, **not V1's 10%**.
5. **Quarter reset:** P08 starts at 0 kg in Q4 before adding its 600 kg. Annual accumulation **does not** reset.
6. **Retroactive annual rebate:** Immediately before P08, MedPolymer's annual quantity is 2,000 kg and no rebate has been earned. After P08, total quantity is 2,600 kg, eligible value is INR 257,460.00, rebate becomes INR 7,723.80 **including earlier POs**.
7. **Other annual rebates:** P12 first meets PureLatex's annual target (1,050 kg, INR 1,206.00 rebate), and P15 first meets SteriPack's target (950 kg, INR 2,931.20 rebate).
8. **Negative discrepancy:** P12 has buyer-entered unit INR 58.00 vs correct INR 60.00; variance = INR −400.00, status `UNDERCHARGED`.
9. **Chronological order:** Loading input POs in file order (supplier grouped) vs date order must produce identical correct outputs when calculations sort by `(purchase_date, po_id)`.

## Annual expected summaries

| Agreement | Purchased kg | Contract value INR | Target kg | First trigger | Rebate INR |
|---|---:|---:|---:|---|---:|
| AGR-001 | 2,600 | 257,460.00 | 2,500 | P08 | 7,723.80 |
| AGR-002 | 1,050 | 60,300.00 | 1,000 | P12 | 1,206.00 |
| AGR-003 | 950 | 73,280.00 | 900 | P15 | 2,931.20 |
| **Total** | | **391,040.00** | | | **11,861.00** |

## Negative tests to construct yourself (not extra seed POs)

- PO with date `2026-01-01` and no active agreement → reject (`404` or `422`, consistently documented).
- PO with unknown supplier or mismatched material → reject.
- Quantity of 0 or less → validation error (`422`).
- Duplicate `po_id` → conflict (`409`).
- Overlapping effective dates for the same agreement → reject setup data; never pick an arbitrary version.
- Overlapping price tiers or a missing tier at an applicable quantity → reject configuration.
- Insert a backdated PO → recompute later same-quarter POs and annual eligible value; do not rely on insert order.
- For an agreement that never reaches its annual target (e.g. a copy of AGR-001 with target 5,000), rebate should be exactly 0.

**Reminder:** These expected values depend on the explicit rules in `BUSINESS_RULES.md`. If the interviewer clarifies that quarterly discounts are also retroactive, update the rule, fixtures and expected-results oracle together.
