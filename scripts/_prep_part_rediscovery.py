"""For the 977 wrong-PDF parts, group by representative-part-prefix to minimize MCP queries.
Many parts within the same micro-family will resolve to the same datasheet, so we don't need
977 queries — we can probe a few representative variants per cluster.

Strategy:
  1. Take all 977 wrong-PDF parts
  2. Cluster by 'truer' family stem (whole part minus trailing pin-count digits)
  3. For each cluster, pick the lex-first part as the probe
  4. Spawn agents to query MCP with the probe part name
  5. Apply discovered URL to all parts in the cluster (they'll be re-validated post-download
     by the wrong-pdf grep audit)
"""
import json
import re
from collections import defaultdict


def truer_stem(p):
    """Cluster parts that almost certainly share the same datasheet.
    Conservative: parts only cluster when their characters before the trailing
    pin-code match exactly AND the part's structural shape matches.

    Examples that should cluster together:
      DSPIC33CK32MP102, DSPIC33CK32MP103, DSPIC33CK32MP105 (only pin-count differs)
      PIC24FJ128GA106, PIC24FJ128GA108, PIC24FJ128GA110 (sub-family + memory match)
      ATSAMC20J18A, ATSAMC20J18B (revision differs)

    Examples that should NOT cluster together:
      ATTINY10 vs ATTINY102 vs ATTINY416 (different chip families)
      PIC18F46Q10 vs PIC18F46Q24 vs PIC18F46K22 (different sub-families)

    Strategy: drop only the trailing single revision letter. Don't strip pin codes
    because they often distinguish independent datasheets.
    """
    p = p.upper()
    # Strip trailing single revision letter ONLY when preceded by digits
    if len(p) > 4 and p[-1].isalpha() and p[-2].isdigit():
        return p[:-1]
    return p


audit = json.load(open("wrong_pdf_audit.json", encoding="utf-8-sig"))
wrong_parts = audit["wrong_pdf_parts"]

clusters = defaultdict(list)
for p in wrong_parts:
    clusters[truer_stem(p)].append(p)

# For each cluster, pick the alphabetically-first part as the probe
probes = []
for stem, parts in clusters.items():
    parts_sorted = sorted(parts)
    probes.append({
        "stem": stem,
        "probe_part": parts_sorted[0],
        "all_parts": parts_sorted,
        "n_parts": len(parts_sorted),
    })

probes.sort(key=lambda x: -x["n_parts"])

print(f"977 wrong-PDF parts -> {len(probes)} clusters")
print(f"Will query MCP with {len(probes)} probe parts (one per cluster)")
print()
print("Top 20 clusters:")
for p in probes[:20]:
    print(f"  {p['stem']:<25} probe={p['probe_part']:<22} n={p['n_parts']}")
print()
total_covered = sum(p["n_parts"] for p in probes)
print(f"Total parts in clusters: {total_covered}")

with open("part_rediscovery_clusters.json", "w") as f:
    json.dump(probes, f, indent=2)
print(f"\nWrote part_rediscovery_clusters.json")
