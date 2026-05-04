"""Compare vectorizer output for one part field-by-field against ground truth."""
import json, sys
sys.path.insert(0, '.')
from datasheet_vectorizer import vectorize
import _validate_phase1 as v

if len(sys.argv) < 2:
    print("Usage: py _compare_one.py <PART_NUMBER>")
    sys.exit(1)

PART = sys.argv[1]
gt_all = json.load(open('ground_truth.json'))
if PART not in gt_all:
    print(f"{PART} not in ground_truth.json")
    sys.exit(1)
if PART not in v.PART_TO_PDF:
    print(f"{PART} has no PDF mapping")
    sys.exit(1)

gt = gt_all[PART]
pdf = v.PART_TO_PDF[PART]
result = vectorize.vectorize(pdf, PART, max_pages=15)
ours = result['fields']

print(f"Part: {PART}")
print(f"PDF:  {pdf}")
print(f"Sources: {result['sources']}")
print(f"Ground truth source: {gt.get('source', '')}")
print()
print(f"     {'FIELD':<30} {'GROUND TRUTH':<22} {'OURS':<22}")
print("-" * 82)

correct = 0
wrong = 0
missing = 0
issues = []

for gt_field, canon in v.GT_TO_CANONICAL.items():
    if canon is None:
        continue
    if gt_field not in gt:
        continue
    truth = str(gt[gt_field]).strip()
    if not truth:
        continue
    our = str(ours.get(canon, '')).strip()
    if v.values_match(truth, our):
        marker = "OK "
        correct += 1
    elif not our:
        marker = "?? "
        missing += 1
        issues.append((gt_field, truth, our))
    else:
        marker = "XX "
        wrong += 1
        issues.append((gt_field, truth, our))
    print(f" {marker} {gt_field:<30} {truth:<22} {our:<22}")

total = correct + wrong + missing
print()
print(f"Score: {correct}/{total} ({correct / max(total,1) * 100:.1f}%)")
print(f"  Correct: {correct}")
print(f"  Wrong:   {wrong}")
print(f"  Missing: {missing}")

if issues:
    print()
    print("Issues to investigate:")
    for f, t, o in issues:
        print(f"  {f}: truth={t!r} ours={o!r}")
