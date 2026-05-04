"""Split clusters into batches for parallel MCP rediscovery."""
import json, math
clusters = json.load(open("part_rediscovery_clusters.json", encoding="utf-8-sig"))
N = 6
size = math.ceil(len(clusters) / N)
for i in range(N):
    chunk = clusters[i * size:(i + 1) * size]
    with open(f"part_redisc_batch{i+1}.json", "w") as f:
        json.dump(chunk, f, indent=2)
    n_parts = sum(c["n_parts"] for c in chunk)
    print(f"Batch {i+1}: {len(chunk)} clusters, {n_parts} parts")
