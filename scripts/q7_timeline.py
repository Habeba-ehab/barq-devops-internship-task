#!/usr/bin/env python3
"""Question 7: build an incident timeline from all three logs."""
import json
import re
from datetime import datetime

def normalize_ts(ts, fmt):
    """Convert any timestamp format to a sortable datetime object."""
    if fmt == "iso":
        return datetime.strptime(ts, "%Y-%m-%dT%H:%M:%S.%fZ")
    elif fmt == "slash":
        return datetime.strptime(ts, "%Y/%m/%d %H:%M:%S")

events = []

with open("logs/access.log") as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        dt = normalize_ts(obj["timestamp"], "iso")
        if int(obj["status"]) >= 500:
            events.append((dt, obj["timestamp"], "access", f"{obj['request_id']} GET {obj['path']} -> {obj['status']} (upstream={obj['upstream']})"))
        elif "," in obj.get("upstream", ""):
            events.append((dt, obj["timestamp"], "access", f"{obj['request_id']} retried and succeeded -> {obj['status']} (upstream={obj['upstream']})"))

with open("logs/error.log") as f:
    for line in f:
        line = line.strip()
        m = re.match(r"(\S+ \S+) \[error\].*?(Connection refused).*?request_id=(\S+),.*?upstream: \"(\S+)\"", line)
        if m:
            ts, kind, rid, upstream = m.groups()
            dt = normalize_ts(ts, "slash")
            events.append((dt, ts, "error", f"{rid} {kind} -> {upstream}"))

with open("logs/application.log") as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if obj.get("level") in ("WARN", "ERROR") and obj.get("status") and int(obj["status"]) >= 500:
            dt = normalize_ts(obj["timestamp"], "iso")
            events.append((dt, obj["timestamp"], "app", f"{obj['request_id']} instance={obj.get('instance_id')} -> {obj['status']}"))

events.sort(key=lambda e: e[0])

print(f"Total timeline events collected: {len(events)}\n")
print("First 15 events (true chronological order):")
for dt, ts, source, desc in events[:15]:
    print(f"  {ts} [{source}] {desc}")

print("\nLast 15 events:")
for dt, ts, source, desc in events[-15:]:
    print(f"  {ts} [{source}] {desc}")