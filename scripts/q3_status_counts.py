#!/usr/bin/env python3
"""Question 3: final client status counts and error rate"""
import json
from collections import Counter

final_status = {}
with open("logs/access.log") as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        final_status[obj["request_id"]] = obj["status"]

counts = Counter(final_status.values())
total = len(final_status)

print("Total distinct requests (denominator):", total)
for status in sorted(counts):
    print(f"  status {status}: {counts[status]}")

errors = sum(c for s, c in counts.items() if int(s) >= 500)
print(f"\nErrors (status >=500): {errors}")
print(f"Error rate: {errors}/{total} = {errors/total*100:.2f}%")