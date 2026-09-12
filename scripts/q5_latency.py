#!/usr/bin/env python3
"""Question 5: median and p95 client latency (request_time, seconds)"""
import json
import statistics

def percentile(data, p):
    """Linear interpolation between closest ranks (same method as numpy's default)."""
    data = sorted(data)
    k = (len(data) - 1) * (p / 100)
    f, c = int(k), min(int(k) + 1, len(data) - 1)
    if f == c:
        return data[f]
    return data[f] + (data[c] - data[f]) * (k - f)

final_by_rid = {}
with open("logs/access.log") as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        final_by_rid[obj["request_id"]] = obj

all_latencies = [float(r["request_time"]) for r in final_by_rid.values()]

print(f"n = {len(all_latencies)} (all distinct requests)")
print(f"median = {statistics.median(all_latencies):.4f} seconds")
print(f"p95    = {percentile(all_latencies, 95):.4f} seconds")
print(f"min    = {min(all_latencies):.4f} seconds")
print(f"max    = {max(all_latencies):.4f} seconds")