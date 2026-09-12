#!/usr/bin/env python3
"""Question 4: which paths, time windows, and backends account for the failures?"""
import json
from collections import Counter

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

failed = [r for r in final_by_rid.values() if int(r["status"]) >= 500]

print(f"Total failed requests: {len(failed)}")

print("\nBy path:")
for path, count in Counter(r["path"] for r in failed).most_common():
    print(f"  {path}: {count}")

print("\nBy backend (final upstream attempted):")
for upstream, count in Counter(r["upstream"].split(",")[-1].strip() for r in failed).most_common():
    print(f"  {upstream}: {count}")

print("\nBy minute (time window):")
by_minute = Counter(r["timestamp"][:16] for r in failed)
for minute, count in sorted(by_minute.items()):
    print(f"  {minute}: {count}")