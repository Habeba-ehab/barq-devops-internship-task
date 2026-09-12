#!/usr/bin/env python3
"""
Stop one backend (app-01), measure traffic/errors while it is down,
restore it, and verify it resumes serving requests.

Usage: python3 failure_test.py [--url http://127.0.0.1:8080] [--container app-01]
Exit code 0 = recovery verified. Non-zero = recovery could not be proven.
"""
import argparse
import json
import subprocess
import sys
import time
import urllib.request
import urllib.error

TIMEOUT = 3
REQUESTS_PER_PHASE = 10
REQUEST_INTERVAL = 0.5
RECOVERY_MAX_WAIT = 20
RECOVERY_POLL_INTERVAL = 1


def http_get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "failure_test.py"})
    start = time.time()
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            elapsed = time.time() - start
            return resp.status, dict(resp.headers), elapsed
    except urllib.error.HTTPError as e:
        elapsed = time.time() - start
        return e.code, dict(e.headers), elapsed
    except Exception as e:
        elapsed = time.time() - start
        return None, {}, elapsed


def send_batch(base_url, path, n, interval):
    results = []
    for _ in range(n):
        status, headers, elapsed = http_get(f"{base_url}{path}")
        results.append((status, headers.get("X-Instance-ID"), elapsed))
        time.sleep(interval)
    return results


def summarize(label, results):
    total = len(results)
    ok = sum(1 for s, _, _ in results if s is not None and s < 500)
    failed = total - ok
    instances = sorted(set(i for _, i, _ in results if i))
    avg_time = sum(e for _, _, e in results) / total if total else 0
    print(f"\n{label}:")
    print(f"  Total requests: {total}")
    print(f"  Succeeded (<500): {ok}")
    print(f"  Failed (>=500 or no response): {failed}")
    print(f"  Instance IDs seen: {instances}")
    print(f"  Avg response time: {avg_time:.3f}s")
    return {"total": total, "ok": ok, "failed": failed, "instances": instances}


def docker(*args):
    result = subprocess.run(["docker", *args], capture_output=True, text=True)
    return result.returncode, result.stdout.strip(), result.stderr.strip()


def container_status(name):
    rc, out, err = docker("inspect", "-f", "{{.State.Status}}", name)
    return out if rc == 0 else None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8080")
    parser.add_argument("--container", default="app-01", help="backend container to stop/restore")
    args = parser.parse_args()
    base_url = args.url.rstrip("/")
    container = args.container

    print(f"=== Failure/recovery test: stopping and restoring '{container}' ===\n")

    baseline = send_batch(base_url, "/instance", REQUESTS_PER_PHASE, REQUEST_INTERVAL)
    baseline_summary = summarize("Phase 1: Baseline (before failure)", baseline)
    if len(baseline_summary["instances"]) < 2:
        print("\nFAIL: baseline did not show both backends responding; "
              "cannot meaningfully test failover. Aborting.")
        sys.exit(1)

    print(f"\nStopping container '{container}' (docker stop)...")
    rc, out, err = docker("stop", container)
    if rc != 0:
        print(f"FAIL: could not stop container: {err}")
        sys.exit(1)
    time.sleep(2)

    during = send_batch(base_url, "/instance", REQUESTS_PER_PHASE, REQUEST_INTERVAL)
    during_summary = summarize("Phase 2: During failure", during)

    availability_during_failure = during_summary["ok"] / during_summary["total"] if during_summary["total"] else 0
    print(f"\n  Availability during failure: {availability_during_failure*100:.0f}% "
          f"of requests still succeeded (via the remaining backend)")

    print(f"\nRestoring container '{container}' (docker start)...")
    rc, out, err = docker("start", container)
    if rc != 0:
        print(f"FAIL: could not restart container: {err}")
        sys.exit(1)

    print(f"Waiting up to {RECOVERY_MAX_WAIT}s for '{container}' to report healthy...")
    start = time.time()
    healthy = False
    while time.time() - start < RECOVERY_MAX_WAIT:
        rc, health, _ = docker("inspect", "-f", "{{.State.Health.Status}}", container)
        if health == "healthy":
            healthy = True
            break
        time.sleep(RECOVERY_POLL_INTERVAL)
    print(f"  Container health after wait: {'healthy' if healthy else 'NOT healthy (timed out)'}")

    after = send_batch(base_url, "/instance", REQUESTS_PER_PHASE, REQUEST_INTERVAL)
    after_summary = summarize("Phase 3: After recovery", after)

    expected_instance_id = container
    recovered_seen = expected_instance_id in after_summary["instances"]

    print(f"\n  '{expected_instance_id}' seen serving traffic after recovery: {recovered_seen}")

    print("\n=== Summary ===")
    checks = [
        ("Baseline showed both backends", len(baseline_summary["instances"]) >= 2),
        ("Traffic continued during failure (>0% availability)", availability_during_failure > 0),
        ("Container reported healthy after restart", healthy),
        (f"'{expected_instance_id}' serving traffic again after recovery", recovered_seen),
    ]
    all_ok = True
    for name, ok in checks:
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}")
        all_ok = all_ok and ok

    if all_ok:
        print("\nOVERALL: PASS (failure and recovery both verified)")
        sys.exit(0)
    else:
        print("\nOVERALL: FAIL")
        sys.exit(1)


if __name__ == "__main__":
    main()