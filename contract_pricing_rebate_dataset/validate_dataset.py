"""Audit seed-data integrity and the frozen test oracle; no third-party packages needed.

Run: python validate_dataset.py
This is a fixture verifier, NOT an implementation of a FastAPI backend.
"""
from pathlib import Path
from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP
import json

root = Path(__file__).resolve().parent
load = lambda f: json.loads((root / 'seed_data' / f).read_text(encoding='utf-8'))
suppliers = load('suppliers.json')
agreements = load('agreements.json')
versions = load('agreement_versions.json')
tiers = load('price_tiers.json')
pos = load('purchase_orders.json')
expected = json.loads((root / 'expected_results.json').read_text(encoding='utf-8'))

def cents(value):
    return Decimal(str(value)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

def unique(items, name):
    ids = [x[name] for x in items]
    assert len(ids) == len(set(ids)), f'Duplicate {name}'
    return {x[name]: x for x in items}

supplier_by_id = unique(suppliers, 'supplier_id')
agreement_by_id = unique(agreements, 'agreement_id')
version_by_id = unique(versions, 'version_id')
tier_by_id = unique(tiers, 'tier_id')
po_by_id = unique(pos, 'po_id')
expected_by_id = unique(expected['purchase_order_results'], 'po_id')
assert len(suppliers) == 3 and len(agreements) == 3
assert len(versions) == 4 and len(tiers) == 12 and len(pos) == 15
assert set(po_by_id) == set(expected_by_id)

agreements_for = defaultdict(list)
for ag in agreements:
    assert ag['supplier_id'] in supplier_by_id
    assert ag['material_code'] == supplier_by_id[ag['supplier_id']]['material_code']
    assert ag['valid_from'] <= ag['valid_to']
    agreements_for[(ag['supplier_id'], ag['material_code'])].append(ag)

versions_for = defaultdict(list)
for v in versions:
    assert v['agreement_id'] in agreement_by_id
    ag = agreement_by_id[v['agreement_id']]
    assert ag['valid_from'] <= v['effective_from'] <= v['effective_to'] <= ag['valid_to']
    assert cents(v['base_unit_price']) >= 0
    versions_for[v['agreement_id']].append(v)
for ag_id, list_versions in versions_for.items():
    ordered = sorted(list_versions, key=lambda v: v['effective_from'])
    assert ordered[0]['effective_from'] == agreement_by_id[ag_id]['valid_from']
    assert ordered[-1]['effective_to'] == agreement_by_id[ag_id]['valid_to']
    for older, newer in zip(ordered, ordered[1:]):
        assert older['effective_to'] < newer['effective_from'], f'Overlapping versions for {ag_id}'

tiers_for = defaultdict(list)
for t in tiers:
    assert t['version_id'] in version_by_id
    assert t['max_quantity_exclusive'] is None or t['max_quantity_exclusive'] > t['min_quantity_inclusive']
    assert 0 <= t['discount_percent'] <= 100
    tiers_for[t['version_id']].append(t)
for version_id, list_tiers in tiers_for.items():
    ordered = sorted(list_tiers, key=lambda t: t['min_quantity_inclusive'])
    assert ordered[0]['min_quantity_inclusive'] == 0
    assert ordered[-1]['max_quantity_exclusive'] is None
    for first, second in zip(ordered, ordered[1:]):
        assert first['max_quantity_exclusive'] == second['min_quantity_inclusive']

q_qty = defaultdict(int)
y_qty = defaultdict(int)
y_spend = defaultdict(lambda: Decimal('0.00'))
trigger = {}
tot_contract = Decimal('0.00')
tot_entered = Decimal('0.00')
positive = Decimal('0.00')
negative = Decimal('0.00')

for po in sorted(pos, key=lambda po: (po['purchase_date'], po['po_id'])):
    assert po['quantity'] > 0 and cents(po['entered_unit_price']) >= 0
    assert po['supplier_id'] in supplier_by_id
    assert po['material_code'] == supplier_by_id[po['supplier_id']]['material_code']
    matched_ag = [a for a in agreements_for[(po['supplier_id'], po['material_code'])]
                  if a['valid_from'] <= po['purchase_date'] <= a['valid_to']]
    assert len(matched_ag) == 1, f'Missing/ambiguous agreement: {po["po_id"]}'
    ag = matched_ag[0]
    assert po['currency'] == ag['currency']
    matched_v = [v for v in versions_for[ag['agreement_id']]
                 if v['effective_from'] <= po['purchase_date'] <= v['effective_to']]
    assert len(matched_v) == 1, f'Missing/ambiguous version: {po["po_id"]}'
    v = matched_v[0]
    quarter = f'{po["purchase_date"][:4]}-Q{(int(po["purchase_date"][5:7])-1)//3+1}'
    k = (ag['agreement_id'], quarter)
    qty_before = q_qty[k]
    year_before = y_qty[ag['agreement_id']]
    q_qty[k] += po['quantity']
    y_qty[ag['agreement_id']] += po['quantity']
    matched_t = [t for t in tiers_for[v['version_id']]
                 if t['min_quantity_inclusive'] <= q_qty[k]
                 and (t['max_quantity_exclusive'] is None or q_qty[k] < t['max_quantity_exclusive'])]
    assert len(matched_t) == 1
    tier = matched_t[0]
    price = cents(Decimal(v['base_unit_price']) * (Decimal(100)-Decimal(tier['discount_percent'])) / 100)
    line = cents(price * po['quantity'])
    billed = cents(Decimal(po['entered_unit_price']) * po['quantity'])
    variance = billed - line
    if variance > 0: positive += variance
    if variance < 0: negative -= variance
    tot_contract += line
    tot_entered += billed
    y_spend[ag['agreement_id']] += line
    if year_before < ag['annual_target_quantity'] <= y_qty[ag['agreement_id']]:
        trigger[ag['agreement_id']] = po['po_id']
    e = expected_by_id[po['po_id']]
    assert e['agreement_id'] == ag['agreement_id'] and e['agreement_version_id'] == v['version_id']
    assert e['quarter'] == quarter
    assert e['quarter_quantity_before_po'] == qty_before
    assert e['quarter_quantity_after_po'] == q_qty[k]
    assert e['annual_quantity_after_po'] == y_qty[ag['agreement_id']]
    assert e['tier_discount_percent'] == tier['discount_percent']
    assert cents(e['correct_unit_price']) == price
    assert cents(e['correct_line_amount']) == line
    assert cents(e['entered_line_amount']) == billed
    assert cents(e['variance_amount']) == variance
    assert e['status'] == ('OVERCHARGED' if variance > 0 else 'UNDERCHARGED' if variance < 0 else 'MATCH')

rebate_sum = Decimal('0.00')
for r in expected['year_end_rebates']:
    ag = agreement_by_id[r['agreement_id']]
    assert r['supplier_id'] == ag['supplier_id']
    assert r['annual_target_quantity'] == ag['annual_target_quantity']
    assert r['annual_purchased_quantity'] == y_qty[ag['agreement_id']]
    assert r['target_met'] == (y_qty[ag['agreement_id']] >= ag['annual_target_quantity'])
    assert r['target_first_met_by_po'] == trigger.get(ag['agreement_id'])
    assert cents(r['eligible_contract_value']) == y_spend[ag['agreement_id']]
    assert r['rebate_percent'] == ag['annual_rebate_percent']
    earned = cents(y_spend[ag['agreement_id']] * Decimal(ag['annual_rebate_percent']) / 100) if r['target_met'] else Decimal('0.00')
    assert cents(r['rebate_earned']) == earned
    rebate_sum += earned

for po in pos:
    e = expected_by_id[po['po_id']]
    summary = next(r for r in expected['year_end_rebates'] if r['supplier_id'] == po['supplier_id'])
    unlock = cents(summary['rebate_earned']) if summary['target_first_met_by_po'] == po['po_id'] else Decimal('0.00')
    assert cents(e['rebate_newly_unlocked_by_po']) == unlock
    assert cents(e['annual_rebate_earned_after_po']) == unlock, 'Fixture has no post-threshold purchases for this supplier'

portfolio = expected['portfolio_totals']
assert portfolio['purchase_order_count'] == len(pos)
assert cents(portfolio['correct_contract_value']) == tot_contract
assert cents(portfolio['buyer_entered_value']) == tot_entered
assert cents(portfolio['potential_overcharges']) == positive
assert cents(portfolio['potential_undercharges']) == negative
assert cents(portfolio['net_price_variance']) == tot_entered-tot_contract
assert cents(portfolio['total_annual_rebates_earned']) == rebate_sum
assert cents(portfolio['contract_value_after_rebates']) == tot_contract-rebate_sum

print('PASS: 3 suppliers, 3 agreements, 4 versions, 12 tiers, 15 PO lines')
print('PASS: date/version, tier boundary, quantity accumulation and all frozen PO values')
print('PASS: year-end rebate triggers and portfolio totals')
print(f'Contract value INR {tot_contract:,.2f} | buyer-entered INR {tot_entered:,.2f}')
print(f'Overcharges INR {positive:,.2f} | undercharges INR {negative:,.2f}')
print(f'Earned rebates INR {rebate_sum:,.2f}')
