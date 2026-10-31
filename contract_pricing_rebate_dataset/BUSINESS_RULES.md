# Business rules and stated assumptions

## Rules directly supported by the problem statement

- Suppliers sell medical manufacturing inputs under **yearly agreements**.
- An agreement establishes a **base price**, **quarterly quantity discount tiers**, **validity period** and **year-end rebate**.
- The backend verifies a buyer's **PO line price** against the agreement and tracks the **supplier rebate owed**.
- After a yearly purchase target is passed, the earned rebate also applies to **eligible earlier purchases**, not only new purchases.
- The sample must cover an **exact tier boundary** and an **agreement amendment in the middle of a quarter**.

## Necessary implementation assumptions (not specified by the prompt)

1. **Completed purchases:** Each seeded PO line is treated as an already purchased/received quantity. A real system would instead use goods receipts to determine eligible quantities.
2. **Quarter definition:** Calendar quarters: Q1 Jan–Mar, Q2 Apr–Jun, Q3 Jul–Sep, Q4 Oct–Dec, based on `purchase_date`.
3. **Quarterly tier logic:** For a PO, add its entire quantity to preceding same-agreement, same-quarter quantities. Select the tier for the **new cumulative total**, applying its discount to the **entire current PO line**. Previous PO prices are **not** revised due to subsequent quarterly tier changes. This is a simplifying interpretation, as the prompt specifies retroactivity only for the year-end rebate.
4. **Boundaries:** A tier starts at an **inclusive** quantity and ends at an **exclusive** quantity. Exactly 500 kg belongs to the tier starting at 500, for example. A `null` upper bound means no maximum.
5. **Version selection:** Each amendment is a new version of the **same agreement**, with a nonoverlapping effective-date window (both ends inclusive). The appropriate version is chosen by `purchase_date`, and earlier PO prices retain their effective version.
6. **Mid-quarter amendment:** Quarterly quantity accumulation **does not reset** at a version boundary. The applicable tier table and base price **do change** on the amendment date. An agreement's annual quantity/rebate calculation spans all versions.
7. **Annual target:** Rebate eligibility begins when total purchased quantity is **at least** the annual target (`>=`); 'crossing the target' includes reaching it. Each agreement has one annual target and percentage; the amendment doesn't change these in our sample.
8. **Retroactive rebate base:** Once the annual target is met, the rebate is its percentage of the **sum of all discounted contract line amounts** in the agreement year. Thus earlier purchases contribute even though their original PO prices do not change. The rebate is earned during the year and understood to be **settled at year end**.
9. **Money:** Prices and line amounts are in INR, excluding tax, freight and surcharges. Use decimal arithmetic. Round contract unit price to **2 decimals, HALF_UP** before multiplying by quantity. Round earned rebate to 2 decimals, HALF_UP.
10. **Audit / discrepancy:** `variance_amount = (entered_unit_price - correct_unit_price) * quantity`. Positive means potential overcharge, negative potential undercharge, zero a match. Rebate and pricing variance are reported **separately**.
11. **Backdated entries:** Always recompute chronological quarterly states and annual rebates from stored eligible purchases; an inserted backdated PO may affect the expected price of *later* POs. For multiple POs on the same day, sort by `po_id` as a deterministic tie-breaker.
12. **No claim-posting data:** The sample tracks **rebate earned**, not whether a credit note was already received or a claim already submitted. Do not present it as an unpaid balance without additional payment/claim records.

## Calculation examples

**Tier boundary — P02 (MedPolymer, Feb 05):** Q1 already has 300 kg (P01). Add P02's 200 kg to reach **500 kg**. Under V1, this qualifies for 5%. Expected unit price = `100.00 * (1 - 0.05) = 95.00`. Correct line amount = `200 * 95.00 = 19,000.00`. Buyer entered `100.00`, so potential overcharge = `(100.00 - 95.00) * 200 = 1,000.00`.

**Mid-quarter amendment — P06 (MedPolymer, May 15):** Q2 quantity before P06 = P04 (400) + P05 (100) = **500 kg**. Add 200 to reach **700 kg**. The purchase date selects **V2** with base price `110.00` and 5% tier, yielding `104.50` per kg and `20,900.00` for the PO. P05 on May 14 used **V1** and the 5% tier (`95.00`).

**Different tier changed by the amendment — P07 (Jun 20):** Q2 reaches **1,000 kg**. V2's top discount is 8% (not V1's 10%), yielding `110.00 * 0.92 = 101.20` per kg.

**Retroactive annual rebate — P08 (Dec 01):** MedPolymer moves from **2,000 kg** to **2,600 kg**, meeting the **2,500 kg** target. Sum of all P01–P08 *contract-priced* line values = `257,460.00`. Rebate earned = `257,460.00 * 3% = 7,723.80`, including values of purchases made before P08. No original PO price is rewritten.

## Scope boundaries for a 90-minute backend

**In scope:** Seed import, agreement/version lookup, tier-based pricing, buyer-price discrepancy, year-to-date rebate calculation, read endpoints, tests and simple error handling.

**Out of scope:** Authentication, supplier onboarding, receipt/returns workflows, tax and freight, real claim settlement and payments, multi-currency FX, multi-material agreements, prorated shipments and large-scale transaction concurrency.
