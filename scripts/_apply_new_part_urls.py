"""Apply new_part_urls.json to part_to_pdf.json by overriding wrong-PDF assignments.
This bypasses family_datasheets.json — we maintain a per-part URL map for the rediscovered set.
"""
import json
import os
import sys
sys.path.insert(0, ".")
from _download_datasheets import safe_filename


new_part_urls = json.load(open("new_part_urls.json", encoding="utf-8-sig"))
audit = json.load(open("wrong_pdf_audit.json", encoding="utf-8-sig"))
wrong_set = set(audit["wrong_pdf_parts"])

# Existing part_to_pdf
ptp = json.load(open("part_to_pdf.json", encoding="utf-8-sig"))

# Add a per-part URL JSON for tracking, and update part_to_pdf for parts whose new URL has a downloaded PDF
n_updated = 0
n_no_local = 0
n_unchanged = 0
for part_upper, url in new_part_urls.items():
    fname = safe_filename(url)
    local = os.path.join("datasheets", fname)
    # Find the part case-insensitively in ptp
    actual_key = None
    if part_upper in ptp:
        actual_key = part_upper
    else:
        for k in ptp:
            if k.upper() == part_upper:
                actual_key = k
                break
    if actual_key is None:
        # Part exists in catalog but isn't currently in ptp — skip (will be regenerated)
        continue
    # Only swap if the local PDF exists; otherwise leave for download pass
    if os.path.exists(local):
        if ptp[actual_key] != local:
            ptp[actual_key] = local
            n_updated += 1
        else:
            n_unchanged += 1
    else:
        n_no_local += 1

with open("part_to_pdf.json", "w") as f:
    json.dump(ptp, f, indent=2)

print(f"Parts with new URL whose PDF was already cached: {n_updated} updated + {n_unchanged} same")
print(f"Parts whose PDF still needs download: {n_no_local}")
print(f"Total parts in part_to_pdf.json: {len(ptp)}")
