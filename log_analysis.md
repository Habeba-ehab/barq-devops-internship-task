# Log analysis

Use all three supplied logs. Answer every question with commands/scripts and actual output.

1. What UTC interval is covered? How many valid, malformed and duplicate lines are in each file?
2. How many distinct client requests occurred? How did you deduplicate and avoid counting retries twice?
3. What are the final client status counts and error rate? State your denominator.
4. Which paths, time windows and backends account for the failures?
5. What are the median and p95 client latencies? State the percentile method and units.
6. Which requests retried upstream? How many succeeded after retrying?
7. Build an incident timeline using evidence from access, error AND application logs.
8. Show one correlated failed request and one successful request. Include IDs and timestamps.
9. Which errors appear to be proxy/connectivity issues versus dependency/application issues? What proves it?
10. What do the logs not prove? What would you check next in a running environment?

## Commands / scripts

### Question 1

head -1 logs/access.log | python3 -c "import json,sys; print(json.loads(sys.stdin.read())['timestamp'])"
tail -1 logs/access.log | python3 -c "import json,sys; print(json.loads(sys.stdin.read())['timestamp'])"

python3 -c "
import json
bad = 0; total = 0
with open('logs/access.log') as f:
    for i, line in enumerate(f, 1):
        line = line.strip()
        if not line: continue
        total += 1
        try: json.loads(line)
        except json.JSONDecodeError:
            bad += 1
            print(f'Malformed line {i}: {line[:100]}')
print(f'Total: {total}, malformed: {bad}')
"

sed -n '311p' logs/access.log

python3 -c "
import json
bad = 0; total = 0
with open('logs/application.log') as f:
    for i, line in enumerate(f, 1):
        line = line.strip()
        if not line: continue
        total += 1
        try: json.loads(line)
        except json.JSONDecodeError:
            bad += 1
            print(f'Malformed line {i}: {line[:150]}')
print(f'Total: {total}, malformed: {bad}')
"

sort logs/access.log | uniq -d
sort logs/application.log | uniq -d
sort logs/error.log | uniq -d | wc -l

for rid in lab-000121 lab-000241 lab-000361 lab-000481 lab-000601; do
  echo -n "$rid: "; grep -c "$rid" logs/access.log
done

wc -l logs/error.log
grep -cE '^[0-9]{4}/[0-9]{2}/[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2} \[error\]' logs/error.log
grep -vE '^[0-9]{4}/[0-9]{2}/[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2} \[error\]' logs/error.log

### Question 2

python3 -c "
import json
rids = set()
with open('logs/access.log') as f:
    for line in f:
        line = line.strip()
        if not line: continue
        try: obj = json.loads(line)
        except json.JSONDecodeError: continue
        rids.add(obj['request_id'])
print(f'Distinct request_id count: {len(rids)}')
"

python3 -c "
import json
with open('logs/access.log') as f:
    count = 0
    for line in f:
        line = line.strip()
        if not line: continue
        try: obj = json.loads(line)
        except json.JSONDecodeError: continue
        if ',' in obj.get('upstream', ''):
            count += 1
            if count <= 5:
                print(obj['request_id'], '|', obj['upstream'], '|', obj['upstream_status'], '|', obj['status'])
    print('Total with comma-separated upstream:', count)
"
### Question 3

python3 scripts/q3_status_counts.py

### Question 4

python3 scripts/q4_failures.py

### Question 5

python3 scripts/q5_latency.py

# Follow-up: checked what the slow requests (>=1.5s) actually were
python3 -c "
import json
with open('logs/access.log') as f:
    slow = []
    for line in f:
        line = line.strip()
        if not line: continue
        try: obj = json.loads(line)
        except json.JSONDecodeError: continue
        if float(obj['request_time']) >= 1.5:
            slow.append(obj)
print(f'Requests with request_time >= 1.5s: {len(slow)}')
for r in slow[:5]:
    print(r['request_id'], r['status'], r['upstream'], r['request_time'])
"

### Question 6

python3 scripts/q6_retries.py

### Question 7

python3 scripts/q7_timeline.py

### Question 8

grep "lab-000122" logs/error.log
grep "lab-000122" logs/access.log
grep "lab-000124" logs/error.log
grep "lab-000124" logs/access.log

### Question 9

# Confirm error.log has zero entries during Phase 2's window (11:20-11:21)
grep -E "11:20:1[0-9]|11:20:4[0-9]|11:21:1[0-9]|11:21:4[0-9]" logs/error.log


# Follow-up check on the second failure cluster (both instances failing on /records near 11:20-11:21)
python3 -c "
import json
with open('logs/application.log') as f:
    for line in f:
        line = line.strip()
        if not line: continue
        try: obj = json.loads(line)
        except json.JSONDecodeError: continue
        if obj.get('path') == '/records' and obj.get('status') and int(obj['status']) >= 500:
            print(obj['timestamp'], obj.get('instance_id'), obj.get('status'), obj.get('event'))
"


## Results

### Question 1

UTC interval covered: 2026-08-20T11:00:00.015Z to 2026-08-20T11:29:57.578Z (~30 minutes).

access.log:
- 726 non-empty lines total
- 1 malformed line (line 311) - truncated mid-write, cuts off right after "request_id": with no value and no closing braces
- 5 duplicate lines - request_ids lab-000121, lab-000241, lab-000361, lab-000481, lab-000601 each appear exactly twice with identical content. All 5 are exactly 5 minutes apart and all hit path /.

application.log:
- 730 non-empty lines total
- 1 malformed line (line 401) - truncated mid-write, cuts off after "event":
- 2 duplicate lines - request_ids lab-000181 and lab-000421 each appear exactly twice, identical content. Different request_ids than the access.log duplicates, so these are two separate duplication incidents, not the same event duplicated in both files.

error.log:
- 68 non-empty lines total
- 0 malformed lines. One line didn't match the [error] search pattern, but it's a valid [notice] entry ("log collector rotated stream"), not corruption - just a different severity level.
- 0 duplicate lines.

### Question 2

Distinct client requests: 720 (counted by unique request_id in access.log,
excluding the 1 malformed line from Q1 which has no readable request_id).

Deduplication approach: counted distinct request_id values rather than raw
lines. This correctly collapses the 5 exact-duplicate lines found in Q1
(lab-000121, 241, 361, 481, 601 - each logged twice) into single requests.

Retry handling: found 19 requests where the "upstream" field contains a
comma-separated list (the format the logs/README.md describes as multiple
attempts for one client request). Example: lab-000124 shows
upstream="172.23.0.12:8080, 172.23.0.11:8080" with upstream_status="502, 200"
- NGINX tried 172.23.0.12 first (got 502), retried 172.23.0.11 (got 200), and
the client received the final 200. These are still one request_id / one log
line each, so counting by request_id already treats them correctly as single
requests rather than double-counting the retry as two separate requests.

### Question 3

Denominator: 720 (distinct client requests, from Question 2).

Final status breakdown:
- 200 (success): 615
- 404 (not found): 10
- 502 (bad gateway): 40
- 503 (service unavailable): 47
- 504 (gateway timeout): 8

Error definition: status >=500, since these represent genuine
server/infrastructure failures rather than client mistakes (a 404
means the client asked for something that does not exist, which is
not an infrastructure problem).

Errors: 95 (40 + 47 + 8)
Error rate: 95/720 = 13.19%

### Question 4

Total failed requests (status >=500): 95

By path: fairly evenly distributed, no single endpoint stands out
(/records: 26, /counter: 26, /ready: 23, /health: 10, /: 10). This
spread across unrelated endpoints suggests the failure was
infrastructure-level (a backend being unreachable), not a bug in one
specific route.

By backend (final upstream attempted): 172.23.0.12:8080 accounts for
68 of 95 failures (72%). 172.23.0.11:8080 accounts for the remaining
27. This matches the repeated "Connection refused" entries for
172.23.0.12:8080 seen in error.log, and points to that backend being
the primary source of the incident.

By time window: failures occur in distinct bursts rather than one
continuous outage: 11:05-11:09, 11:12-11:15, 11:20-11:21, tapering to
11:25-11:26. This pattern (repeated bursts separated by gaps, rather
than one steady failure) suggests 172.23.0.12 went down and briefly
recovered multiple times, rather than being down continuously for the
whole 30-minute window.

### Question 5

n = 720 (all distinct requests)
Method: linear interpolation between closest ranks (same method used
by numpy's default percentile calculation). Units: seconds
(request_time as logged by NGINX).

median = 0.0540 seconds
p95 = 2.0010 seconds
min = 0.0030 seconds
max = 2.0250 seconds

The large gap between median (54ms) and p95 (2.0s, roughly 37x
slower) indicates the slowdown was not uniform across all traffic.
Checked directly: 39 requests took >=1.5 seconds, and nearly all of
them are 503 responses taking almost exactly 2.025 seconds each
(e.g. lab-000292, lab-000293, lab-000296). That near-identical
duration across many unrelated requests points to a fixed timeout
being hit (the request waited for a connection/response, timed out
at a fixed threshold, then returned 503) rather than genuine gradual
slowness. This is consistent with the earlier finding that
172.23.0.12:8080 was repeatedly unreachable during the incident.

### Question 6

19 requests retried upstream (identified by a comma-separated
"upstream" field, per logs/README.md's description of this format).

All 19 succeeded after retrying (100% recovery rate). Every one
follows the identical pattern: first attempt to 172.23.0.12:8080
returned 502, retry to 172.23.0.11:8080 returned 200, and the client
received the final 200. Full list of the 19 request_ids and their
attempt sequences is in scripts/q6_retries.py output.

This confirms the load balancer's failover mechanism worked correctly
whenever a retry was triggered during this incident. No request was
permanently lost due to a failed retry, the 95 failures counted in
Question 3 are requests where the retry either never happened (both
attempts failed, or no second attempt was made) or a single-attempt
request failed outright.

### Question 9

Two distinct error categories were found in this incident. (See
Question 8 for the exact raw log lines proving the Phase 1
connectivity failure, and Question 7 for the application.log evidence
of Phase 2/3.)

1. Proxy/connectivity issues (Phase 1, approx. 11:05-11:15):
Proof: error.log records "connect() failed (111: Connection refused)"
for 172.23.0.12:8080, meaning NGINX could not even establish a TCP
connection to that backend. This happens at the network layer, before
any HTTP/application logic runs. The corresponding access.log entries
show 502 (bad gateway), NGINX's standard response when it cannot
reach the upstream at all. This category is a proxy/infrastructure
problem, not an application bug, the backend's own code was never
reached or executed for these requests.

2. Dependency/application issues (Phase 2 and 3, approx. 11:20-11:26):
Proof: grepping error.log for the exact timestamps of Phase 2
(11:20:1x, 11:20:4x, 11:21:1x, 11:21:4x) returns zero results, no
connection failures were logged at all during this window. Both
app-01 and app-02 were reachable and did respond (confirmed in
application.log with real instance_id and status entries), but they
responded with 503 (Phase 2) and 504 (Phase 3) specifically on
/records. Since both independent app instances failed the same way at
the same time, on the one endpoint that touches PostgreSQL, and NGINX
never lost connectivity to either of them, this points to a
dependency (most likely PostgreSQL) being slow or unavailable to the
app layer itself, not a proxy/network problem.

Summary: Phase 1 = proxy/connectivity (proven by Connection refused
in error.log). Phase 2/3 = dependency/application (proven by the
absence of any connection errors during that window, combined with
both backends failing identically on the one DB-backed endpoint).


## Timeline and correlated examples

### Question 7 - Incident timeline

Phase 1 (approx. 11:05 to 11:15): repeated connectivity failures to
172.23.0.12:8080 specifically. error.log shows "Connection refused"
for this address roughly every 5 seconds; access.log shows the
corresponding client-facing 502 under the same request_id and
timestamp. NGINX successfully retried the other backend
(172.23.0.11:8080) in every observed case, and the client still
received a 200 (see Question 6, all 19 retries succeeded).

Phase 2 (11:20:12 to 11:21:45): /records fails with 503 on BOTH
backends (172.23.0.11 and 172.23.0.12), confirmed identically in
application.log (both app-01 and app-02 report 503 on /records within
seconds of each other). Immediately before (11:19:xx) and after
(11:22:12 onward) this window, /records succeeds normally on both
backends, so this was a genuine, bounded outage, not a
misconfiguration or a permanently broken endpoint. Since both
independent app instances failed identically at the same time on the
one endpoint that touches PostgreSQL, this strongly suggests a shared
dependency (most likely PostgreSQL) was briefly unavailable to both
instances.

Phase 3 (11:25:14 to 11:26:47): a third, separate failure window,
also on /records on both backends, but this time with 504 (gateway
timeout) instead of 503. The different status code is meaningful:
503 means the app actively responded saying it was not ready (e.g.
its own dependency check failed), whereas 504 means no response was
received at all before NGINX's timeout was reached. This suggests
Phase 3 may be a different symptom or a worsening of the same
underlying issue as Phase 2, rather than a continuation of the exact
same failure mode. No further failures appear after 11:26:47Z through
the end of the log window.

### Question 8 - One correlated failed request, one correlated successful request

FAILED REQUEST: lab-000122, GET /health, at 2026-08-20T11:05:02

error.log:
2026/08/20 11:05:02 [error] 31#31: *122 connect() failed (111:
Connection refused) while connecting to upstream, request_id=lab-000122,
request: "GET /health HTTP/1.1", upstream: "http://172.23.0.12:8080/health"

access.log:
{"timestamp":"2026-08-20T11:05:02.503Z","request_id":"lab-000122",
"method":"GET","path":"/health","status":502,
"upstream":"172.23.0.12:8080","upstream_status":"502",
"request_time":0.003,"client":"192.0.2.24"}

Reading: NGINX tried to open a connection to 172.23.0.12:8080 and the
OS refused it outright (error.log). That single failed connection
attempt is exactly why the client received a 502 (access.log). Same
request_id, same second, no retry was attempted for this one, so the
client got the failure directly.

SUCCESSFUL REQUEST (after retry): lab-000124, GET /ready, at
2026-08-20T11:05:07

error.log:
2026/08/20 11:05:07 [error] 31#31: *124 connect() failed (111:
Connection refused) while connecting to upstream, request_id=lab-000124,
request: "GET /ready HTTP/1.1", upstream: "http://172.23.0.12:8080/ready"

access.log:
{"timestamp":"2026-08-20T11:05:07.620Z","request_id":"lab-000124",
"method":"GET","path":"/ready","status":200,
"upstream":"172.23.0.12:8080, 172.23.0.11:8080",
"upstream_status":"502, 200","request_time":0.12,"client":"192.0.2.24"}

Reading: same failure mode as lab-000122 (172.23.0.12 refused the
connection), but this time NGINX retried the second backend
(172.23.0.11:8080), which responded successfully. The client's final
status was 200, they never saw the failure. The access.log line
captures the whole story of both attempts in one line, error.log only
recorded the one connection that actually failed, since the retry to
172.23.0.11 succeeded and never triggered an error log entry.


## Conclusions and limits

### Question 10 - Limits of the logs, and what to check in a live environment

The logs prove that specific requests failed, when, and which backend
was involved. They do not prove root cause at the infrastructure
level:

1. Phase 2/3 was inferred to be a PostgreSQL issue based on pattern
(both instances failing identically on the one DB-backed endpoint,
with no connectivity error logged), but this was never directly
confirmed. application.log's event name is a generic "http_request"
with no error message or dependency name attached. In a running
environment, I would check PostgreSQL's own logs, active connection
count, and CPU/memory usage during 11:20:12-11:21:45 and
11:25:14-11:26:47 to confirm or rule this out.

2. The cause of 172.23.0.12:8080 becoming unreachable in Phase 1 is
not shown anywhere in these logs, only the symptom (connection
refused) is recorded, not whether the container crashed, was
restarted, or lost network connectivity for some other reason. In a
running environment, I would check container orchestrator events
(e.g. docker events, or Kubernetes pod events), restart counts, and
host-level resource usage for that container around 11:05-11:15.

3. Whether Phase 1 and Phase 2/3 are related (e.g. retries from Phase
1 adding load that contributed to Phase 2) or coincidental cannot be
determined from these logs alone, they involve different backends and
different failure signatures. This would require correlating with
resource/metrics data (e.g. DB connection pool usage over the whole
window), which is not captured in any of the three log files.

4. None of the three logs include resource metrics (CPU, memory,
connection pool state, disk I/O). A 503/504 status code tells us a
request failed, but not the underlying resource condition that caused
it. In a running environment, I would add and check
metrics/monitoring (e.g. Postgres connection pool utilization,
container resource usage) alongside the existing request logs to
distinguish between different possible causes of the same status
code.