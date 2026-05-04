"""For every part flagged as wrong-PDF, replace its extracted fields with null/empty
to stop reporting contaminated outputs as if they were real data.

Writes vectorized_all.json (overwrites). Original is preserved at vectorized_all.contaminated.json.
"""
import json
import shutil
import os

# Backup the contaminated file once (don't overwrite an existing backup)
src = "vectorized_all.json"
backup = "vectorized_all.contaminated.json"
if not os.path.exists(backup):
    shutil.copy(src, backup)
    print(f"Backed up original to {backup}")
else:
    print(f"Backup {backup} already exists — not overwriting")

vec = json.load(open(src, encoding="utf-8-sig"))
audit = json.load(open("wrong_pdf_audit.json", encoding="utf-8-sig"))
wrong_set = set(audit["wrong_pdf_parts"])

n_nulled = 0
n_kept = 0
for part, info in vec.items():
    if part in wrong_set:
        info["fields"] = {}
        info["sources"] = []
        info["wrong_pdf"] = True  # flag explaining why fields are empty
        n_nulled += 1
    else:
        n_kept += 1

with open(src, "w") as f:
    json.dump(vec, f, indent=2)

print(f"Nulled {n_nulled} parts (wrong-PDF). Kept {n_kept} parts intact.")
print(f"Wrote {src}")

# Sanity check: count fields in the new file
total_field_cells = sum(len(info.get("fields", {})) for info in vec.values())
print(f"Total non-null field cells now: {total_field_cells} (was contaminated)")
