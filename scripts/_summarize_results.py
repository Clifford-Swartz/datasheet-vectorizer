"""
Analyze vectorized_all.json: field coverage, per-family statistics, and obvious quality flags.
"""
import json
from collections import Counter, defaultdict

data = json.load(open("vectorized_all.json", encoding="utf-8-sig"))

n_parts = len(data)
print(f"Total parts vectorized: {n_parts}")
print()

# Per-field coverage: how many parts have a non-empty value for this canonical field
field_counts = Counter()
fields_per_part = []
for part, info in data.items():
    fields = info.get("fields", {})
    nonempty = [k for k, v in fields.items() if str(v).strip()]
    fields_per_part.append(len(nonempty))
    for k in nonempty:
        field_counts[k] += 1

print(f"Avg fields/part: {sum(fields_per_part)/len(fields_per_part):.1f}")
print(f"Min fields/part: {min(fields_per_part)}")
print(f"Max fields/part: {max(fields_per_part)}")
print()

print("Field coverage (canonical field -> parts with value):")
for field, n in field_counts.most_common():
    pct = n / n_parts * 100
    bar = "#" * int(pct / 2)
    print(f"  {field:<28} {n:>5} ({pct:>5.1f}%)  {bar}")

# Parts with very few fields (<5) — likely failures or not-found-in-table
print()
sparse = [(p, n) for p, n in zip(data.keys(), fields_per_part) if n < 5]
print(f"Parts with fewer than 5 fields: {len(sparse)}")
sparse_by_pdf = defaultdict(int)
for p, _ in sparse:
    pdf = data[p]["pdf"]
    sparse_by_pdf[pdf] += 1
print("PDFs producing sparse results (top 10):")
for pdf, n in sorted(sparse_by_pdf.items(), key=lambda x: -x[1])[:10]:
    print(f"  {n:>4}  {pdf}")
