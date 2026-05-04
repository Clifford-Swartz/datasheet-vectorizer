"""Join verifier findings against vectorized_all.json field-by-field.
Compute honest accuracy stratified by:
- whether the part was in its assigned PDF (wrong-PDF problem)
- per-field correctness on parts where the PDF IS correct
"""
import json
import re

vec = json.load(open("vectorized_all.json", encoding="utf-8-sig"))

verifier = {}
for i in range(1, 4):
    try:
        for entry in json.load(open(f"verify_results_batch{i}.json", encoding="utf-8-sig")):
            verifier[entry["part"]] = entry
    except Exception as e:
        print(f"Couldn't load batch{i}: {e}")


def normalize(v):
    if v is None: return ""
    s = str(v).strip()
    if s.lower() in ("none", "n/a", "null", "-", "—", ""): return ""
    if re.match(r"^\d+\.0+$", s): s = str(int(float(s)))
    return s


def values_match(a, b):
    a, b = normalize(a), normalize(b)
    if a == b: return True
    if not a and not b: return True
    try:
        if abs(float(a) - float(b)) < 0.05: return True
    except (ValueError, TypeError): pass
    if a.lower() == b.lower(): return True
    return False


parts_in_pdf = []  # parts where verifier found values
parts_wrong_pdf = []  # parts where verifier said notfound for everything

# Cell-level stats per stratum
stats_in_pdf = {"correct": 0, "wrong": 0, "ours_blank_truth_known": 0, "ours_known_truth_blank": 0}
stats_wrong_pdf = {"ours_filled": 0, "ours_blank": 0}

# Per-field breakdown (only on in_pdf parts)
field_correct = {}
field_total = {}
errors_to_show = []

for part, entry in verifier.items():
    findings = entry.get("findings", [])
    our_fields = vec.get(part, {}).get("fields", {})
    n_found = sum(1 for f in findings if f.get("confidence") != "notfound")
    if n_found == 0:
        parts_wrong_pdf.append(part)
        for f in findings:
            field = f["field"]
            our = our_fields.get(field, "")
            if str(our).strip():
                stats_wrong_pdf["ours_filled"] += 1
            else:
                stats_wrong_pdf["ours_blank"] += 1
        continue

    parts_in_pdf.append(part)
    for f in findings:
        if f.get("confidence") == "notfound":
            continue
        field = f["field"]
        truth = f["value"]
        our = our_fields.get(field, "")
        field_total[field] = field_total.get(field, 0) + 1
        if values_match(truth, our):
            stats_in_pdf["correct"] += 1
            field_correct[field] = field_correct.get(field, 0) + 1
        else:
            if not normalize(our):
                stats_in_pdf["ours_blank_truth_known"] += 1
            elif not normalize(truth):
                stats_in_pdf["ours_known_truth_blank"] += 1
            else:
                stats_in_pdf["wrong"] += 1
            errors_to_show.append((part, field, truth, our))

print("=" * 70)
print("HELD-OUT VALIDATION RESULTS (30 parts, ~262 field lookups)")
print("=" * 70)

print(f"\nWRONG-PDF rate (verifier couldn't find ANY field for the part):")
print(f"  Parts NOT in their assigned PDF: {len(parts_wrong_pdf)} / {len(parts_wrong_pdf)+len(parts_in_pdf)}")
print(f"  ({100*len(parts_wrong_pdf)/(len(parts_wrong_pdf)+len(parts_in_pdf)):.0f}% of held-out parts are wrong-PDF)")

print(f"\nFor the {len(parts_wrong_pdf)} wrong-PDF parts, our vectorizer:")
total_wp = stats_wrong_pdf["ours_filled"] + stats_wrong_pdf["ours_blank"]
print(f"  Returned a value (likely from features parser or family default): {stats_wrong_pdf['ours_filled']} / {total_wp}")
print(f"  Returned blank (correct behavior — no real data): {stats_wrong_pdf['ours_blank']} / {total_wp}")
print(f"  → For wrong-PDF parts, we falsely 'extract' values {100*stats_wrong_pdf['ours_filled']/total_wp:.0f}% of the time")

print(f"\nCELL ACCURACY ON PARTS WITH CORRECT PDF ({len(parts_in_pdf)} parts):")
total = sum(stats_in_pdf.values())
print(f"  Correct:                         {stats_in_pdf['correct']:>4} / {total}  ({100*stats_in_pdf['correct']/total:.1f}%)")
print(f"  Wrong (we said X, datasheet says Y): {stats_in_pdf['wrong']:>4} / {total}  ({100*stats_in_pdf['wrong']/total:.1f}%)")
print(f"  Ours blank, truth known (miss):  {stats_in_pdf['ours_blank_truth_known']:>4} / {total}  ({100*stats_in_pdf['ours_blank_truth_known']/total:.1f}%)")
print(f"  Ours known, truth blank (false): {stats_in_pdf['ours_known_truth_blank']:>4} / {total}  ({100*stats_in_pdf['ours_known_truth_blank']/total:.1f}%)")

print(f"\nPER-FIELD ACCURACY (parts with correct PDF only):")
for field in sorted(field_total.keys(), key=lambda f: -field_total[f]):
    cor = field_correct.get(field, 0)
    tot = field_total[field]
    bar = "#" * int(cor/tot * 30)
    print(f"  {field:<28} {cor:>3}/{tot:<3} ({100*cor/tot:>5.1f}%)  {bar}")

print(f"\nWRONG VALUES (sample):")
for part, field, truth, our in errors_to_show[:20]:
    print(f"  {part:<25} {field:<25} truth={truth!r}  ours={our!r}")

print(f"\nWRONG-PDF PARTS:")
for p in parts_wrong_pdf:
    print(f"  {p}")
