# Actual API Samples

These responses were captured from the running FastAPI application against an
isolated copy of the original 15-PO database.

## `GET /suppliers`

```json
[
  {"supplier_id":"S1","supplier_name":"MedPolymer","material_code":"RESIN-MED","material_name":"Medical-grade plastic resin","unit":"kg"},
  {"supplier_id":"S2","supplier_name":"PureLatex","material_code":"LATEX-MED","material_name":"Medical-grade latex","unit":"kg"},
  {"supplier_id":"S3","supplier_name":"SteriPack","material_code":"FILM-MED","material_name":"Sterile packaging film","unit":"kg"}
]
```

## `GET /agreements`

```json
[
  {
    "agreement_id":"AGR-001","supplier_id":"S1","material_code":"RESIN-MED","valid_from":"2025-01-01","valid_to":"2025-12-31","annual_target_quantity":2500,"annual_rebate_percent":3,"currency":"INR","unit":"kg",
    "versions":[
      {"version_id":"AGR-001-V1","version_number":1,"effective_from":"2025-01-01","effective_to":"2025-05-14","base_unit_price":"100.00","change_note":"Original annual agreement.","price_tiers":[
        {"tier_id":"AGR-001-V1-T1","min_quantity_inclusive":0,"max_quantity_exclusive":500,"discount_percent":0},
        {"tier_id":"AGR-001-V1-T2","min_quantity_inclusive":500,"max_quantity_exclusive":1000,"discount_percent":5},
        {"tier_id":"AGR-001-V1-T3","min_quantity_inclusive":1000,"max_quantity_exclusive":null,"discount_percent":10}
      ]},
      {"version_id":"AGR-001-V2","version_number":2,"effective_from":"2025-05-15","effective_to":"2025-12-31","base_unit_price":"110.00","change_note":"Mid-Q2 amendment: base price rises from INR 100 to 110; top quarterly discount changes from 10% to 8%. Annual rebate remains unchanged.","price_tiers":[
        {"tier_id":"AGR-001-V2-T1","min_quantity_inclusive":0,"max_quantity_exclusive":500,"discount_percent":0},
        {"tier_id":"AGR-001-V2-T2","min_quantity_inclusive":500,"max_quantity_exclusive":1000,"discount_percent":5},
        {"tier_id":"AGR-001-V2-T3","min_quantity_inclusive":1000,"max_quantity_exclusive":null,"discount_percent":8}
      ]}
    ]
  },
  {
    "agreement_id":"AGR-002","supplier_id":"S2","material_code":"LATEX-MED","valid_from":"2025-01-01","valid_to":"2025-12-31","annual_target_quantity":1000,"annual_rebate_percent":2,"currency":"INR","unit":"kg",
    "versions":[{"version_id":"AGR-002-V1","version_number":1,"effective_from":"2025-01-01","effective_to":"2025-12-31","base_unit_price":"60.00","change_note":"Original annual agreement.","price_tiers":[
      {"tier_id":"AGR-002-V1-T1","min_quantity_inclusive":0,"max_quantity_exclusive":300,"discount_percent":0},
      {"tier_id":"AGR-002-V1-T2","min_quantity_inclusive":300,"max_quantity_exclusive":600,"discount_percent":5},
      {"tier_id":"AGR-002-V1-T3","min_quantity_inclusive":600,"max_quantity_exclusive":null,"discount_percent":10}
    ]}]
  },
  {
    "agreement_id":"AGR-003","supplier_id":"S3","material_code":"FILM-MED","valid_from":"2025-01-01","valid_to":"2025-12-31","annual_target_quantity":900,"annual_rebate_percent":4,"currency":"INR","unit":"kg",
    "versions":[{"version_id":"AGR-003-V1","version_number":1,"effective_from":"2025-01-01","effective_to":"2025-12-31","base_unit_price":"80.00","change_note":"Original annual agreement.","price_tiers":[
      {"tier_id":"AGR-003-V1-T1","min_quantity_inclusive":0,"max_quantity_exclusive":200,"discount_percent":0},
      {"tier_id":"AGR-003-V1-T2","min_quantity_inclusive":200,"max_quantity_exclusive":500,"discount_percent":2},
      {"tier_id":"AGR-003-V1-T3","min_quantity_inclusive":500,"max_quantity_exclusive":null,"discount_percent":5}
    ]}]
  }
]
```

## `GET /purchase-orders/P06/price`

```json
{
  "po_id":"P06","supplier_id":"S1","material_code":"RESIN-MED","purchase_date":"2025-05-15","quantity":200,"currency":"INR",
  "agreement_id":"AGR-001","agreement_version_id":"AGR-001-V2","quarter":"2025-Q2","quarter_quantity_before_po":500,"quarter_quantity_after_po":700,"annual_quantity_after_po":1700,
  "tier_discount_percent":5,"base_unit_price":"110.00","entered_unit_price":"110.00","correct_unit_price":"104.50","correct_line_amount":"20900.00","entered_line_amount":"22000.00","variance_amount":"1100.00","status":"OVERCHARGED","annual_rebate_earned_after_po":"0.00","rebate_newly_unlocked_by_po":"0.00"
}
```

## `GET /rebates/2025`

```json
{
  "year":2025,"currency":"INR",
  "rebates":[
    {"agreement_id":"AGR-001","supplier_id":"S1","annual_purchased_quantity":2600,"annual_target_quantity":2500,"target_met":true,"eligible_contract_value":"257460.00","rebate_percent":3,"rebate_earned":"7723.80","target_first_met_by_po":"P08","target_first_met_on":"2025-12-01"},
    {"agreement_id":"AGR-002","supplier_id":"S2","annual_purchased_quantity":1050,"annual_target_quantity":1000,"target_met":true,"eligible_contract_value":"60300.00","rebate_percent":2,"rebate_earned":"1206.00","target_first_met_by_po":"P12","target_first_met_on":"2025-11-11"},
    {"agreement_id":"AGR-003","supplier_id":"S3","annual_purchased_quantity":950,"annual_target_quantity":900,"target_met":true,"eligible_contract_value":"73280.00","rebate_percent":4,"rebate_earned":"2931.20","target_first_met_by_po":"P15","target_first_met_on":"2025-12-12"}
  ],
  "total_rebate_earned":"11861.00"
}
```

## `GET /dashboard`

```json
{
  "total_suppliers":3,
  "total_agreements":3,
  "total_purchase_orders":15,
  "overcharged_purchase_orders":7,
  "undercharged_purchase_orders":1,
  "total_overcharge_amount":"6860.00",
  "total_undercharge_amount":"400.00",
  "total_eligible_contract_value":"391040.00",
  "total_earned_rebate":"11861.00"
}
```

## `POST /purchase-orders`

Request:

```json
{"po_id":"P16","supplier_id":"S1","material_code":"RESIN-MED","purchase_date":"2025-08-03","quantity":50,"entered_unit_price":"110.00","currency":"INR"}
```

Actual `201 Created` response from a disposable seeded database:

```json
{
  "po_id":"P16","supplier_id":"S1","material_code":"RESIN-MED","purchase_date":"2025-08-03","quantity":50,"currency":"INR",
  "agreement_id":"AGR-001","agreement_version_id":"AGR-001-V2","quarter":"2025-Q3","quarter_quantity_before_po":0,"quarter_quantity_after_po":50,"annual_quantity_after_po":2050,
  "tier_discount_percent":0,"base_unit_price":"110.00","entered_unit_price":"110.00","correct_unit_price":"110.00","correct_line_amount":"5500.00","entered_line_amount":"5500.00","variance_amount":"0.00","status":"MATCH","annual_rebate_earned_after_po":"0.00","rebate_newly_unlocked_by_po":"0.00"
}
```
