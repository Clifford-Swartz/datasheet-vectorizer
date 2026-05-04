"""Merge all part_redisc_results_batch*.json into a single per-part-to-PDF map.

For each cluster, expand to all parts in the cluster sharing the same URL.
Then for each part, replace its assignment in part_to_pdf.json with the new URL.
"""
import json
import os
from collections import defaultdict


def basename(url):
    s = (url or "").split("?")[0].split("#")[0]
    return s.replace("\\", "/").rstrip("/").split("/")[-1].replace("%20", " ").strip()


# Build part -> new-URL map
new_part_urls = {}
total_clusters = 0
total_resolved = 0
all_paths = [f"part_redisc_results_batch{i}.json" for i in range(1, 7)] + ["part_redisc_results_retry.json"]
for path in all_paths:
    if not os.path.exists(path):
        continue
    d = json.load(open(path, encoding="utf-8-sig"))
    if isinstance(d, dict):
        d = list(d.values())
    for entry in d:
        url = entry.get("datasheet_url")
        all_parts = entry.get("all_parts") or [entry.get("probe_part")]
        total_clusters += 1
        if not url or not str(url).startswith("http"):
            continue
        total_resolved += 1
        for p in all_parts:
            if p:
                new_part_urls[p.upper()] = url

print(f"Clusters processed:  {total_clusters}")
print(f"Clusters with URL:   {total_resolved}")
print(f"Parts mapped to URL: {len(new_part_urls)}")

with open("new_part_urls.json", "w") as f:
    json.dump(new_part_urls, f, indent=2)

# Show distinct URLs
distinct_urls = set(new_part_urls.values())
print(f"Distinct datasheet URLs: {len(distinct_urls)}")

# Group by which URL we already had downloaded
existing_pdfs = set()
for fname in os.listdir("datasheets"):
    if fname.endswith(".pdf"):
        existing_pdfs.add(fname)

new_to_download = []
for url in distinct_urls:
    bn = basename(url)
    safe_bn = "".join(c if c.isalnum() or c in "._-" else "_" for c in bn)
    if not safe_bn.endswith(".pdf"):
        safe_bn += ".pdf"
    if safe_bn not in existing_pdfs:
        new_to_download.append(url)

print(f"New PDFs to download: {len(new_to_download)}")
print(f"Already cached:       {len(distinct_urls) - len(new_to_download)}")
