#!/usr/bin/env python3
"""
Validate the running environment: public access, all endpoints, both
backends, PostgreSQL/Redis readiness, network isolation, and that
Postgres/Redis ports are not published to the host.

Usage: python3 validate.py [--url http://127.0.0.1:8080]
Exit code 0 = all checks passed. Non-zero = at least one check failed.
"""
import argparse
import json
import socket
import sys
import time
import urllib.request
import urllib.error

TIMEOUT = 3          # seconds per individual HTTP/socket attempt
MAX_WAIT = 15        # total bounded wait per check before giving up
POLL_INTERVAL = 1

results = []  # list of (name, passed: bool, detail: str)


def record(name, passed, detail=""):
    results.append((name, passed, detail))
    status = "PASS" if passed else "FAIL"
    print(f"[{status}] {name}" + (f" - {detail}" if detail else ""))


def wait_for(check_fn, description, max_wait=MAX_WAIT, interval=POLL_INTERVAL):
    """Retry check_fn() until it returns (True, detail) or max_wait elapses."""
    start = time.time()
    last_detail = ""
    while time.time() - start < max_wait:
        ok, detail = check_fn()
        last_detail = detail
        if ok:
            record(description, True, detail)
            return True
        time.sleep(interval)
    record(description, False, f"timed out after {max_wait}s, last: {last_detail}")
    return False


def http_get(url, timeout=TIMEOUT):
    req = urllib.request.Request(url, headers={"User-Agent": "validate.py"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read()
            return resp.status, body, dict(resp.headers)
    except urllib.error.HTTPError as e:
        return e.code, e.read(), dict(e.headers)
    except Exception as e:
        return None, str(e).encode(), {}


def check_public_access(base_url):
    def fn():
        status, body, _ = http_get(f"{base_url}/health")
        if status == 200:
            return True, f"GET /health -> 200"
        return False, f"GET /health -> {status}"
    return wait_for(fn, "Public access (NGINX reachable on public port)")


def check_endpoint(base_url, path, expect_status=200):
    status, body, headers = http_get(f"{base_url}{path}")
    ok = status == expect_status
    record(f"Endpoint {path}", ok, f"expected {expect_status}, got {status}")
    return ok


def check_records_roundtrip(base_url):
    payload = json.dumps({"title": "validate.py check"}).encode()
    req = urllib.request.Request(
        f"{base_url}/records", data=payload,
        headers={"Content-Type": "application/json"}, method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            status = resp.status
            body = json.loads(resp.read())
    except Exception as e:
        record("POST /records", False, str(e))
        return False
    ok = status == 201 and "record" in body
    record("POST /records", ok, f"status={status}")
    if not ok:
        return False

    status, body, _ = http_get(f"{base_url}/records")
    ok = status == 200
    record("GET /records", ok, f"status={status}")
    return ok


def check_counter(base_url):
    status1, body1, _ = http_get(f"{base_url}/counter")
    status2, body2, _ = http_get(f"{base_url}/counter")
    try:
        v1 = json.loads(body1)["counter"]
        v2 = json.loads(body2)["counter"]
        ok = status1 == 200 and status2 == 200 and v2 > v1
        record("Counter increments (Redis-backed)", ok, f"{v1} -> {v2}")
        return ok
    except Exception as e:
        record("Counter increments (Redis-backed)", False, str(e))
        return False


def check_both_backends(base_url, attempts=10):
    seen = set()
    for _ in range(attempts):
        status, body, headers = http_get(f"{base_url}/instance")
        iid = headers.get("X-Instance-ID")
        if iid:
            seen.add(iid)
    ok = len(seen) >= 2
    record("Both backends serve traffic", ok, f"instance_ids seen: {sorted(seen)}")
    return ok


def check_ready(base_url):
    def fn():
        status, body, _ = http_get(f"{base_url}/ready")
        try:
            deps = json.loads(body).get("dependencies", {})
        except Exception:
            deps = {}
        ok = status == 200 and all(v == "ready" for v in deps.values())
        return ok, f"status={status} dependencies={deps}"
    return wait_for(fn, "PostgreSQL/Redis readiness (/ready)")


def check_port_not_published(host, port, name):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(2)
    try:
        s.connect((host, port))
        record(f"Prohibited port closed: {name} ({port})", False, "connection succeeded, port is exposed")
        return False
    except (ConnectionRefusedError, socket.timeout, OSError):
        record(f"Prohibited port closed: {name} ({port})", True, "connection refused/unreachable, as expected")
        return True
    finally:
        s.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8080")
    parser.add_argument("--host", default="127.0.0.1", help="host for port-isolation checks")
    args = parser.parse_args()
    base_url = args.url.rstrip("/")

    print(f"Validating environment at {base_url}\n")

    check_public_access(base_url)
    check_endpoint(base_url, "/", 200)
    check_endpoint(base_url, "/health", 200)
    check_ready(base_url)
    check_endpoint(base_url, "/instance", 200)
    check_both_backends(base_url)
    check_records_roundtrip(base_url)
    check_counter(base_url)
    check_endpoint(base_url, "/does-not-exist", 404)

    for port, name in [(15432, "Postgres (legacy mapped port)"),
                        (5432, "Postgres (default port)"),
                        (16379, "Redis (legacy mapped port)"),
                        (6379, "Redis (default port)")]:
        check_port_not_published(args.host, port, name)

    print()
    failed = [name for name, ok, _ in results if not ok]
    total = len(results)
    passed = total - len(failed)
    print(f"Summary: {passed}/{total} checks passed.")
    if failed:
        print("FAILED checks:")
        for name in failed:
            print(f"  - {name}")
        print("\nOVERALL: FAIL")
        sys.exit(1)
    else:
        print("OVERALL: PASS")
        sys.exit(0)


if __name__ == "__main__":
    main()