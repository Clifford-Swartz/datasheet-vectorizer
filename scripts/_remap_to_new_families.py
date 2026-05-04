"""Map the new (finer) families.json to existing PDFs we have.

For each new family, find any part in its parts list that's already mapped to a PDF
(via the OLD part_to_pdf.json). If found, reuse that PDF for the new family.
This avoids re-running 487 MCP queries.
"""
import json
import os

new_fams = json.load(open("families.json", encoding="utf-8-sig"))
# old part_to_pdf has the existing mappings
old_part_to_pdf = json.load(open("part_to_pdf.json", encoding="utf-8-sig"))

# Reverse-map: PDF basename -> URL (from old family_datasheets.json)
old_fds = json.load(open("family_datasheets.json", encoding="utf-8-sig"))
url_by_basename = {}
for v in old_fds.values():
    url = v.get("datasheet_url")
    if url:
        bn = url.rsplit("/", 1)[-1]
        url_by_basename.setdefault(bn, url)

new_fds = {}
n_reused = 0
n_unmapped = 0
unmapped_keys = []

for fk, info in new_fams.items():
    rep = info["representative"]
    n = len(info["parts"])
    # Try every part in this family — first one that has a known PDF wins
    pdf_path = None
    for p in info["parts"]:
        if p in old_part_to_pdf:
            pdf_path = old_part_to_pdf[p]
            break
    if pdf_path:
        bn = os.path.basename(pdf_path)
        url = url_by_basename.get(bn)
        new_fds[fk] = {
            "representative": rep,
            "datasheet_url": url,
            "ds_number": None,
            "n_parts": n,
        }
        n_reused += 1
    else:
        new_fds[fk] = {
            "representative": rep,
            "datasheet_url": None,
            "ds_number": None,
            "n_parts": n,
        }
        n_unmapped += 1
        unmapped_keys.append((fk, rep, n))

with open("family_datasheets.json", "w") as f:
    json.dump(new_fds, f, indent=2)

print(f"New families.json:        {len(new_fams)} families")
print(f"Reused old datasheet URL: {n_reused}")
print(f"Unmapped (need MCP):      {n_unmapped}")
print(f"\nUnmapped families (top 30 by part count):")
unmapped_keys.sort(key=lambda x: -x[2])
for fk, rep, n in unmapped_keys[:30]:
    print(f"  {fk:<28} rep={rep:<25} n={n}")
total_unmapped_parts = sum(n for _, _, n in unmapped_keys)
print(f"\nTotal parts in unmapped families: {total_unmapped_parts}")
