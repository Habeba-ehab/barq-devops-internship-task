# Troubleshooting journal

## Entry 1 / 2026-09-11
- Symptom: docker compose up --build failed entirely, before any containers started, with "failed to fetch anonymous token ... dial tcp [2606:...]:443: connect: network is unreachable" while pulling the python base image.
- Hypothesis: Docker's DNS resolution was returning an IPv6 address for Docker Hub, but the WSL2/host network could not route IPv6 traffic.
- Command or test: Retried docker compose up --build once, same IPv6 error recurred on a different IPv6 address, ruling out a one-off blip.
- Actual output: target app-02: failed to solve: failed to fetch anonymous token ... connect: network is unreachable
- Failed attempt and what changed your thinking: Simply retrying the build did not help, confirming this was a persistent network configuration issue, not a transient failure.
- Root cause: Docker Desktop's DNS resolution mode was returning IPv6 (AAAA) records for Docker Hub, and the environment had no working IPv6 route to the internet.
- Fix: In Docker Desktop Settings > Resources > Network, changed "Inhibit DNS resolution for IPv4/IPv6" from "Auto" to "Filter IPv6 (AAAA records)".
- Retest evidence: docker compose up --build completed successfully afterward, all 5 images pulled/built and all containers started.
- Related commit: N/A (environment/tooling fix, not a code change).
- Remaining uncertainty: This is a machine-specific Docker Desktop network setting, not something fixed in the repo itself; a different machine with working IPv6 would not need this change.

## Entry 2 / 2026-09-11
- Symptom: app-01 and app-02 both showed status "unhealthy" in docker compose ps, despite the process being up.
- Hypothesis: The Docker healthcheck was targeting the wrong endpoint.
- Command or test: docker compose logs app-01, then manually ran urllib.request against http://127.0.0.1:8080/health from inside the app-01 container.
- Actual output: Logs showed repeated {"path": "/healthz", "status": 404} every 5 seconds. Direct request to /health (no "z") returned 200 with {"status":"alive"}.
- Failed attempt and what changed your thinking: Initially assumed the app itself was broken since /ready also failed at the time; checking /health directly proved the process was fine and isolated the problem to the healthcheck configuration specifically, not the app.
- Root cause: docker-compose.yml's healthcheck for the shared app anchor targeted /healthz, but the application's real liveness endpoint is /health (per assessment/APPLICATION.md).
- Fix: Changed the healthcheck URL from /healthz to /health in docker-compose.yml.
- Retest evidence: After docker compose up -d --force-recreate app-01 app-02 and waiting ~15s, docker compose ps showed both as (healthy).
- Related commit: fix: correct NGINX port mapping, upstream ports, and app bind address (grouped with other fixes; healthcheck path fix committed separately, see git log for exact hash).
- Remaining uncertainty: None, fully proven via logs before and after.

## Entry 3 / 2026-09-11
- Symptom: GET /ready returned 503 with {"dependencies":{"postgres":"unavailable","redis":"unavailable"}}.
- Hypothesis: config/app.env had incorrect connection details for Postgres and/or Redis.
- Command or test: Raw TCP socket connection test from inside app-01 to postgres on ports 5433 and 5432, and to redis on ports 6380 and 6379.
- Actual output: port 5433 FAILED: Connection refused; port 5432: CONNECTED. Same pattern for redis (6380 refused, 6379 connected).
- Failed attempt and what changed your thinking: Initially suspected only the password (which also turned out to be wrong, docker-compose.yml's POSTGRES_PASSWORD ended in "...8c", config/app.env had "...8d"), but the raw socket test proved the port alone was already causing connection refusal, before authentication was ever attempted.
- Root cause: config/app.env specified the wrong ports for both Postgres (5433 instead of 5432) and Redis (6380 instead of 6379), and a mismatched Postgres password.
- Fix: Corrected both ports and the password in config/app.env.
- Retest evidence: After recreating app-01/app-02, GET /ready returned 200 with {"postgres":"ready","redis":"ready"}.
- Related commit: fix: correct Postgres/Redis ports and DB password in config/app.env
- Remaining uncertainty: None, isolated and proven via independent raw socket tests before fixing.

## Entry 4 / 2026-09-11
- Symptom: curl http://127.0.0.1:8080/health returned a 302 redirect from a Jetty server, then later "Failed to connect... Couldn't connect to server", neither response came from our own NGINX.
- Hypothesis: something else on the host/WSL machine was already using port 8080.
- Command or test: sudo lsof -i :8080
- Actual output: java 164 jenkins ... LISTEN on port 8080. A pre-existing Jenkins instance was bound to the same port our NGINX was trying to publish to.
- Failed attempt and what changed your thinking: Initially assumed the Jetty/ngrok response was somehow related to our own stack (a misconfigured proxy), until lsof revealed it was a completely unrelated process (Jenkins) with no connection to this project.
- Root cause: Port collision with a Jenkins instance already running on the host, unrelated to this project.
- Fix: sudo systemctl stop jenkins to free port 8080 for this project's use.
- Retest evidence: After stopping Jenkins, sudo lsof -i :8080 returned nothing, and subsequent requests to port 8080 reached our own NGINX (Server: nginx/1.28.3 in the response headers) instead of Jetty.
- Related commit: N/A (environment/tooling conflict, not a code change).
- Remaining uncertainty: None; this was purely local environment contention, not something in the project's own configuration.

## Entry 5 / 2026-09-11
- Symptom: After fixing Jenkins and Postgres/Redis connectivity, curl http://127.0.0.1:8080/health still failed with "Failed to connect... Couldn't connect to server", now with Jenkins confirmed stopped.
- Hypothesis: NGINX's own port mapping or listen configuration was mismatched.
- Command or test: docker compose exec nginx netstat -tlnp
- Actual output: NGINX was listening only on 0.0.0.0:80 inside its container, but docker-compose.yml mapped the host's 8080 to container port 81, a port nothing was listening on.
- Failed attempt and what changed your thinking: Assumed the fix belonged in nginx.conf (changing "listen 80" to "listen 81") until realizing that would just move the mismatch rather than resolve it; correctly changing the compose file's mapping to point at NGINX's actual listening port (80) was the right side to fix, since 80 is the conventional default and nginx.conf itself was not actually wrong.
- Root cause: docker-compose.yml mapped host:8080 to container:81, but NGINX (using its default configuration) listens on port 80 inside the container.
- Fix: Changed the port mapping in docker-compose.yml from "8080:81" to "8080:80".
- Retest evidence: curl -i http://127.0.0.1:8080/health returned a response with Server: nginx/1.28.3 (previously connection refused/wrong service entirely).
- Related commit: fix: correct NGINX port mapping, upstream ports, and app bind address
- Remaining uncertainty: None.

## Entry 6 / 2026-09-11
- Symptom: After fixing the NGINX port mapping, curl to port 8080 returned "502 Bad Gateway" from our own NGINX.
- Hypothesis: NGINX's upstream configuration pointed at the wrong backend port.
- Command or test: docker compose logs nginx --no-color --tail 5
- Actual output: connect() failed (111: Connection refused) while connecting to upstream ... upstream: "http://172.23.0.3:8081/health" (app-01's real internal IP, but on port 8081, an incorrect port).
- Failed attempt and what changed your thinking: N/A, error.log immediately pointed to the exact wrong port.
- Root cause: nginx.conf's upstream block specified "server app-01:8081" instead of "server app-01:8080" (app-02's entry was already correct at 8080).
- Fix: Corrected app-01's port from 8081 to 8080 in nginx.conf's upstream block.
- Retest evidence: After recreating nginx, the same request still returned 502, but the logged upstream address changed to the correct IP:8080 and still showed "Connection refused", revealing a second, independent problem (see Entry 7).
- Related commit: fix: correct NGINX port mapping, upstream ports, and app bind address
- Remaining uncertainty: None for this specific fix; it was necessary but not sufficient (see Entry 7).

## Entry 7 / 2026-09-11
- Symptom: After fixing both the NGINX port mapping and the upstream port, curl still returned 502, and NGINX's error log now showed "Connection refused" to the correct IP and port (172.23.0.3:8080).
- Hypothesis: The Flask app itself was not accepting connections from outside its own container.
- Command or test: Reviewed app-01's own startup log line: "Running on http://127.0.0.1:8080". Checked docker-compose.yml's APP_HOST value.
- Actual output: APP_HOST was set to "127.0.0.1", meaning Flask only accepted connections originating from inside its own container (loopback), rejecting NGINX's cross-container connection attempts regardless of correct IP/port.
- Failed attempt and what changed your thinking: The two previous fixes (port mapping, upstream port) were both necessary and correct, but neither was sufficient alone; only after both were fixed and the failure persisted did the app's own bind address become the clear remaining suspect.
- Root cause: APP_HOST=127.0.0.1 caused Flask to bind only to the loopback interface, refusing connections from other containers (including NGINX) on the Docker network.
- Fix: Changed APP_HOST from "127.0.0.1" to "0.0.0.0" in docker-compose.yml, so Flask accepts connections on all its network interfaces.
- Retest evidence: curl -i http://127.0.0.1:8080/health returned 200 with the app's real JSON body, routed successfully through NGINX to app-01.
- Related commit: fix: correct NGINX port mapping, upstream ports, and app bind address
- Remaining uncertainty: None; fully proven end-to-end through the real request path (curl -> NGINX -> app -> response).

## Entry 8 / 2026-09-11
- Symptom: GET /instance on app-02 returned instance_id "app-01" instead of "app-02".
- Hypothesis: app-02's environment block in docker-compose.yml had the wrong INSTANCE_ID value.
- Command or test: docker compose exec app-02 python -c "urlopen('http://127.0.0.1:8080/instance')"
- Actual output: {"instance_id":"app-01","service":"barq-api","status":"ok",...}, confirmed directly from app-02 itself, not just inferred from reading the file.
- Failed attempt and what changed your thinking: N/A, reading docker-compose.yml already showed the duplicate value; the test simply confirmed it in practice before fixing.
- Root cause: app-02's service block set INSTANCE_ID: "app-01" instead of "app-02" (likely a copy-paste error from app-01's block).
- Fix: Changed app-02's INSTANCE_ID to "app-02".
- Retest evidence: After recreating app-02, its /instance endpoint returned "app-02". A looped curl (6x) against http://127.0.0.1:8080/instance through NGINX showed a mix of both app-01 and app-02, confirming distinct identities and working load balancing.
- Related commit: fix: correct app-02 INSTANCE_ID (was incorrectly set to app-01)
- Remaining uncertainty: None.

## Entry 9 / 2026-09-11
- Symptom: Task spec requires blocking direct NGINX access to PostgreSQL/Redis; NGINX was on both the frontend and backend Docker networks.
- Hypothesis: NGINX being on the backend network meant it could connect directly to postgres/redis, bypassing the app entirely.
- Command or test: docker compose exec nginx sh -c "nc -zv postgres 5432; nc -zv redis 6379"
- Actual output: postgres (172.19.0.5:5432) open, redis (172.19.0.4:6379) open, direct connections succeeded.
- Failed attempt and what changed your thinking: N/A, this was a proactive fix based on the explicit requirement, not something reproduced as a live error first.
- Root cause: nginx's networks list in docker-compose.yml included both frontend and backend, when it only needs frontend to reach the app instances.
- Fix: Removed "backend" from NGINX's networks list, leaving only "frontend".
- Retest evidence: The same nc test afterward returned "bad address" for both postgres and redis (NGINX could not even resolve the hostnames). curl to /ready still returned 200, confirming app functionality was unaffected.
- Related commit: fix: remove NGINX from backend network (enforce isolation)
- Remaining uncertainty: None.

## Entry 10 / 2026-09-11
- Symptom: Task spec requires "do not publish app, PostgreSQL or Redis ports"; postgres and redis both had host port mappings (15432, 16379).
- Hypothesis: these host mappings were unnecessary for the application's own functioning and only existed to allow external tools to connect directly.
- Command or test: nc -zv 127.0.0.1 15432 and nc -zv 127.0.0.1 16379 from the host, before and after the fix.
- Actual output: before the fix, both connected successfully from the host (unconfirmed exact "open" wording, but the ports were reachable prior to removal). After removing the ports: line from both services and recreating them, both returned "Connection refused".
- Failed attempt and what changed your thinking: N/A, straightforward removal once the requirement was understood.
- Root cause: postgres and redis service blocks included a ports: mapping to the host, which was never needed for internal container-to-container communication (that uses the internal 5432/6379 ports directly, unaffected by host-side mappings).
- Fix: Removed the ports: entries from both the postgres and redis service blocks entirely.
- Retest evidence: docker compose ps showed no host port mapping for postgres/redis afterward (only bare 5432/tcp and 6379/tcp). nc from the host to both old ports returned Connection refused. curl to /ready still returned 200.
- Related commit: fix: remove host port publishing for Postgres and Redis
- Remaining uncertainty: None.

## Entry 11 / 2026-09-11
- Symptom: A test record created via POST /records disappeared after recreating the postgres container for an unrelated fix.
- Hypothesis: Postgres's real data directory was not actually backed by the named (persistent) volume.
- Command or test: Reviewed docker-compose.yml's postgres volumes: the named volume postgres-data was mounted to /var/lib/postgresql/backup (a path Postgres does not use for its live data), while /var/lib/postgresql/data (the real data directory) was mounted as tmpfs (RAM-backed, non-persistent).
- Actual output: A record created before a postgres container recreation was confirmed gone afterward via GET /records, direct evidence of the persistence failure occurring naturally during unrelated work.
- Failed attempt and what changed your thinking: This bug was discovered as a side effect, not deliberately reproduced first; the natural data loss during an unrelated fix is what revealed it.
- Root cause: The named volume was mounted to the wrong path, and the actual data directory was on non-persistent tmpfs storage.
- Fix: Changed the volume mount to /var/lib/postgresql/data (the real data directory) and removed the tmpfs line entirely.
- Retest evidence: Created a record ("Persistence proof before recreate"), recreated the postgres container, and confirmed via GET /records that the record survived (previously it would not have).
- Related commit: fix: mount Postgres named volume to the real data directory
- Remaining uncertainty: None; directly proven with a real before/after recreate test.

## Entry 12 / 2026-09-11
- Symptom: Task spec requires configuring Redis persistence "where appropriate"; Redis was started with --save "" --appendonly no, explicitly disabling all persistence, and had no volume at all.
- Hypothesis: enabling --appendonly yes plus adding a named volume would allow the /counter value to survive container recreation.
- Command or test: Incremented /counter to a known value, recreated the redis container, checked /counter again.
- Actual output: Before the fix (not directly tested, since persistence was never enabled to test), after the fix: counter reached 3, recreated redis, next call returned 4 (continued, did not reset to 1).
- Failed attempt and what changed your thinking: Initially changed only the command (--appendonly yes) without adding a volume; recognized this would still fail since AOF persistence needs durable storage to write to, and added the redis-data named volume before testing, rather than testing an incomplete fix first.
- Root cause: No persistence mechanism and no volume meant any Redis data was lost on every container recreation.
- Fix: Changed Redis's command to --appendonly yes and added a redis-data named volume mounted to /data.
- Retest evidence: Counter value continued from 3 to 4 across a container recreation, instead of resetting to 1.
- Related commit: fix: enable Redis persistence with a named volume
- Remaining uncertainty: None.

## Entry 13 / 2026-09-11
- Symptom: No service had a working restart policy; app-01/app-02 explicitly set restart: "no", and postgres/redis/nginx had no restart key (defaulting to Docker's global "no").
- Hypothesis: setting restart: unless-stopped on all services would cause automatic recovery from crashes.
- Command or test: docker kill --signal=SIGKILL app-01, then monitored docker compose ps and docker inspect app-01 for several minutes.
- Actual output: docker inspect confirmed the policy was correctly set to unless-stopped, but RestartCount remained 0 and the container stayed Exited for over 6 minutes; docker events showed no restart attempt at all.
- Failed attempt and what changed your thinking: Initially suspected the YAML value needed quotes (like restart: "no" does, since unquoted "no" is a YAML boolean); confirmed via docker inspect that the policy name was already being read correctly as the string "unless-stopped", ruling out a quoting/config problem, and pointing instead at daemon-level behavior in this specific environment.
- Root cause (config): restart: "no" (or the unset default) meant no service would recover automatically from a crash.
- Fix (config): Set restart: unless-stopped on all 5 services.
- Retest evidence: docker inspect confirmed the policy was applied correctly to app-01. Manually recovered the container with docker start after the automatic restart did not trigger as expected.
- Related commit: fix: set restart: unless-stopped for all services
- Remaining uncertainty: The configuration is verified correct, but automatic restart-on-SIGKILL was not observed to trigger within this specific Docker Desktop/WSL2 environment. This appears to be daemon/environment-specific behavior rather than a misconfiguration in the project. In production, this would be mitigated by an orchestrator (Kubernetes/Swarm) with its own reconciliation loop rather than relying solely on the Docker Engine's restart policy.

## Entry 14 / 2026-09-11
- Symptom: No service had any CPU/memory resource limits set.
- Hypothesis: adding mem_limit and cpus to each service would be enforced by Docker under plain docker compose up.
- Command or test: docker inspect app-01/postgres --format '{{.HostConfig.Memory}} bytes | CPUs: {{.HostConfig.NanoCpus}}' after adding limits.
- Actual output: app-01: 268435456 bytes (256m) / 500000000 nanocpus (0.5 CPU); postgres: 536870912 bytes (512m) / 1000000000 nanocpus (1.0 CPU), matching the configured values exactly.
- Failed attempt and what changed your thinking: Initially considered using the deploy.resources.limits syntax, but recognized this is only enforced under Docker Swarm mode and would be silently ignored under plain docker compose up, which is what this project actually runs under locally and in CI; used the top-level mem_limit/cpus keys instead, which are actually enforced in this context.
- Root cause: No resource constraints meant any service could consume unbounded host CPU/memory.
- Fix: Added mem_limit and cpus to all 5 services (app: 256m/0.5, postgres: 512m/1.0, redis: 128m/0.5, nginx: 128m/0.5).
- Retest evidence: docker inspect confirmed the exact configured values were applied at the container level. curl to /ready still returned 200 after applying limits, no functional regression.
- Related commit: fix: add CPU and memory limits to all services
- Remaining uncertainty: None.

## Entry 15 / 2026-09-11
- Symptom: Task spec requires avoiding root/privileged operation "where practical"; the Dockerfile created a dedicated non-root user but the container still ran as root.
- Hypothesis: a stray USER root instruction near the end of the Dockerfile was overriding the earlier non-root user setup.
- Command or test: Reviewed the Dockerfile directly; found "RUN groupadd ... useradd ... app" and "COPY --chown=app:app" followed later by "USER root".
- Actual output: The final effective user directive in the file was "USER root", meaning despite creating the "app" user and chown'ing files to it, the container actually ran as root.
- Failed attempt and what changed your thinking: N/A, the bug was directly visible on reading the file.
- Root cause: "USER root" was the last relevant instruction, discarding the earlier non-root user setup.
- Fix: Changed "USER root" to "USER app".
- Retest evidence: After rebuilding and recreating app-01/app-02, docker inspect app-01 --format '{{.Config.User}}' returned "app" instead of empty/root. curl to /ready still returned 200.
- Related commit: fix: run app container as non-root user; enable NGINX failover
- Remaining uncertainty: None.