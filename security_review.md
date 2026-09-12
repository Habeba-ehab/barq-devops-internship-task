# Security and production-readiness review

## Finding 1: Secrets (POSTGRES_PASSWORD, DATABASE_URL) stored in plaintext files
- Risk and evidence: config/app.env and docker-compose.yml both contain the real database password in plaintext (e.g. POSTGRES_PASSWORD: BarqLabOnly_7qN2vK8c, and the matching password embedded directly in DATABASE_URL). These files are committed to git.
- Impact: Anyone with read access to the repository can see the database credentials, even though this is lab/synthetic data, the same pattern in a real project would leak production secrets through version control history permanently, even if later removed.
- Implemented fix / commit: None implemented, this is a structural limitation of the assessment's file layout (config/app.env is explicitly tracked in git per the starter project). The password itself was corrected (see troubleshooting.md Entry 3) but not moved out of plaintext/version control.
- Production follow-up: Use a secrets manager (Docker Secrets, HashiCorp Vault, AWS Secrets Manager, or at minimum an untracked .env file populated at deploy time) rather than committing credentials to the repository. .env.example already demonstrates the pattern of keeping real secrets out of git for the PUBLIC_PORT variable, this should be extended to database/cache credentials in a real deployment.
- How to verify: git log -p -- config/app.env shows the password in plaintext in the commit history.

## Finding 2: Postgres/Redis ports removed from host publishing
- Risk and evidence: Originally, postgres (15432) and redis (16379) were published to the host, meaning anything on the host machine (or, in production, the network) could connect directly, bypassing the application's own logic entirely.
- Impact: Direct, unauthenticated-at-the-network-layer access to the database and cache, allowing data exfiltration or tampering without going through the application at all.
- Implemented fix / commit: fix: remove host port publishing for Postgres and Redis. Verified via nc -zv 127.0.0.1 <port> from the host returning "Connection refused" for both ports afterward.
- Production follow-up: None needed for this specific risk; already resolved. In a cloud deployment, this should be reinforced with security group/firewall rules as defense in depth, not relying on Docker Compose configuration alone.
- How to verify: docker compose ps shows no host-side port mapping for postgres or redis (only bare 5432/tcp, 6379/tcp).

## Finding 3: Container ran as root (Dockerfile)
- Risk and evidence: The Dockerfile created a dedicated non-root "app" user but ended with "USER root", so the container actually ran as root despite that setup.
- Impact: If the application were compromised (e.g. via a code vulnerability), an attacker would have root privileges inside the container, increasing the potential impact of any container breakout or privilege escalation vulnerability.
- Implemented fix / commit: fix: run app container as non-root user; enable NGINX failover. Changed "USER root" to "USER app".
- Production follow-up: None needed for this specific risk; already resolved. Could be further hardened with a read-only root filesystem and dropped Linux capabilities in a production deployment.
- How to verify: docker inspect app-01 --format '{{.Config.User}}' returns "app".

## Finding 4: Base images are pinned by digest, but not automatically scanned or updated
- Risk and evidence: All images (python:3.12-slim-bookworm, postgres:16-alpine, redis:7.4-alpine, nginx:1.28-alpine) are pinned by exact SHA256 digest, which is good for reproducibility, but there is no automated process in this project to check those images for newly discovered vulnerabilities over time.
- Impact: A vulnerability disclosed in one of these base images after the digest was pinned would not be caught or flagged by anything in this project.
- Implemented fix / commit: None implemented (marked as optional "extra credit" in the task brief).
- Production follow-up: Add an image/dependency vulnerability scanner (e.g. Trivy, Docker Scout, or GitHub's own Dependabot) to the CI pipeline, and establish a process for periodically re-pinning to updated digests.
- How to verify: grep for "sha256:" in docker-compose.yml confirms digest pinning is in place; absence of any scanning step in .github/workflows/ci.yml confirms scanning is not yet implemented.

## Finding 5: NGINX removed from the backend network (isolation from PostgreSQL/Redis)
- Risk and evidence: NGINX was originally on both the frontend and backend Docker networks, meaning it could connect directly to Postgres/Redis (confirmed via nc -zv from inside the nginx container).
- Impact: If NGINX were compromised (e.g. via a malicious upstream response or a vulnerability in NGINX itself), an attacker would have a direct network path to the database and cache, bypassing the application layer entirely.
- Implemented fix / commit: fix: remove NGINX from backend network (enforce isolation). Verified the same nc test afterward returns "bad address" (NGINX can no longer even resolve postgres/redis by hostname).
- Production follow-up: None needed for this specific risk; already resolved.
- How to verify: docker compose exec nginx sh -c "nc -zv postgres 5432" fails with "bad address".

## Finding 6: PostgreSQL persistence fixed; no backup automation or off-host copy exists
- Risk and evidence: Postgres now correctly persists data via a named Docker volume (fixed from an earlier tmpfs misconfiguration), but backup.sh only writes to a local ./backups/ directory on the same host as the database itself.
- Impact: If the host machine's disk fails or is lost entirely, both the live database volume and all local backups would be lost simultaneously, a single point of failure.
- Implemented fix / commit: fix: mount Postgres named volume to the real data directory (persistence). backup.sh/restore.sh implemented and verified with a real delete-and-restore cycle.
- Production follow-up: Backups should be copied to a separate location (e.g. object storage like S3, or a separate backup server) on a schedule, not left only on the same host as the live database.
- How to verify: ls backups/ after running backup.sh shows the dump file only exists locally; there is no step anywhere in this project that copies it elsewhere.

## Finding 7: No centralized logging or monitoring/alerting
- Risk and evidence: Logs exist per-container (accessible via docker compose logs) but nothing aggregates them centrally, and there is no alerting if a service becomes unhealthy or a dependency fails.
- Impact: In a real incident (like the one analyzed in log_analysis.md), nobody would be automatically notified; someone would need to be actively watching or manually checking before noticing a problem.
- Implemented fix / commit: None implemented (out of scope for this assessment's local Docker Compose setup).
- Production follow-up: Add a log aggregation tool (e.g. Loki, ELK stack, or a managed service) and alerting on health check failures, elevated error rates, or dependency unavailability (e.g. via Prometheus + Alertmanager, or a hosted APM tool).
- How to verify: No monitoring/alerting configuration exists anywhere in this repository; confirmed by searching for any such service in docker-compose.yml.

## Finding 8: Restart policy correctly configured, but not proven to trigger automatically in this environment
- Risk and evidence: All 5 services have restart: unless-stopped configured (verified correct via docker inspect), but a live test (docker kill --signal=SIGKILL app-01) did not result in an automatic restart within 6+ minutes in this specific Docker Desktop/WSL2 environment (see troubleshooting.md Entry 13).
- Impact: If this same daemon-level behavior occurred in a production host running plain Docker Engine (not an orchestrator), a crashed container could remain down until manually restarted, despite the restart policy being correctly configured.
- Implemented fix / commit: fix: set restart: unless-stopped for all services (configuration correct and verified via docker inspect; automatic trigger behavior not fully verified in this environment).
- Production follow-up: In production, rely on an orchestrator (Kubernetes, Docker Swarm) with its own reconciliation loop rather than the Docker Engine's restart policy alone, since the latter's behavior was observed to be environment-dependent here.
- How to verify: docker inspect <container> --format '{{.HostConfig.RestartPolicy.Name}}' confirms the configured policy; troubleshooting.md Entry 13 documents the live test and its result.

## Finding 9: No rate limiting or request throttling at the NGINX layer
- Risk and evidence: nginx.conf has no rate-limiting directives (e.g. limit_req_zone); any client can send unlimited requests to any endpoint.
- Impact: A single client (malicious or misbehaving) could overwhelm the backend or database with requests, since nothing at the proxy layer would throttle or reject excessive traffic.
- Implemented fix / commit: None implemented.
- Production follow-up: Add rate limiting in nginx.conf (e.g. limit_req_zone based on client IP) to protect backend and database resources from abuse or accidental overload.
- How to verify: grep -i "limit_req" nginx/nginx.conf currently returns nothing.