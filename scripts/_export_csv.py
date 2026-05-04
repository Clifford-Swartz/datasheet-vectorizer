"""Export vectorized_all.json to a CSV with one row per part."""
import json
import csv

data = json.load(open("vectorized_all.json", encoding="utf-8-sig"))

# Determine union of all field keys (canonical names)
all_fields = set()
for info in data.values():
    all_fields.update(info.get("fields", {}).keys())

# Order: most-common first (rough proxy for which fields people care about)
field_order = sorted(all_fields)
field_order.sort(key=lambda f: -sum(1 for v in data.values() if v.get("fields", {}).get(f)))

cols = ["Part", "Source_PDF"] + field_order

with open("vectorized_all.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(cols)
    for part, info in sorted(data.items()):
        row = [part, info.get("pdf", "")]
        fields = info.get("fields", {})
        for col in field_order:
            row.append(fields.get(col, ""))
        w.writerow(row)

print(f"Wrote vectorized_all.csv with {len(data)} rows and {len(cols)} columns")
