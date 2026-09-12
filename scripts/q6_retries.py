#!/usr/bin/env python3
"""Question 6: which requests retried upstream, and how many succeeded after retrying?"""
import json

retried = []
with open("logs/access.log") as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if "," in obj.get("upstream", ""):
            retried.append(obj)

print(f"Total requests that retried upstream: {len(retried)}\n")

succeeded = [r for r in retried if int(r["status"]) < 400]
still_failed = [r for r in retried if int(r["status"]) >= 400]

print(f"Succeeded after retry (final status < 400): {len(succeeded)}")
print(f"Still failed after retry (final status >= 400): {len(still_failed)}\n")

print("All retried requests (request_id | upstream attempts | upstream_status attempts | final client status):")
for r in retried:
    print(f"  {r['request_id']} | {r['upstream']} | {r['upstream_status']} | final={r['status']}")