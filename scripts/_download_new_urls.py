"""Download every distinct URL from new_part_urls.json that we don't already have."""
import json
import os
import sys
sys.path.insert(0, ".")
from _download_datasheets import safe_filename, download, DATASHEETS_DIR


new_part_urls = json.load(open("new_part_urls.json", encoding="utf-8-sig"))
distinct_urls = sorted(set(new_part_urls.values()))

os.makedirs(DATASHEETS_DIR, exist_ok=True)
ok = skipped = failed = 0
failures = []
for i, url in enumerate(distinct_urls, 1):
    fname = safe_filename(url)
    dest = os.path.join(DATASHEETS_DIR, fname)
    if os.path.exists(dest) and os.path.getsize(dest) > 1024:
        skipped += 1
        continue
    try:
        print(f"[{i}/{len(distinct_urls)}] {fname}")
        download(url, dest)
        ok += 1
    except Exception as e:
        failed += 1
        failures.append((url, str(e)))
        print(f"  FAIL: {e}")

print()
print(f"Done. ok={ok} skipped={skipped} failed={failed}")
if failures:
    print("\nFailures:")
    for url, err in failures[:20]:
        print(f"  {err}: {url}")
