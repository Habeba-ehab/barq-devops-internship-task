# Technical decisions

## Decision 1: Fix NGINX's port mapping rather than change nginx.conf's listen port
- Choice: When NGINX's host:container port mapping (8080:81) didn't match its actual listen directive (listen 80), fixed the compose file's mapping to 8080:80 rather than changing nginx.conf to listen 81.
- Why: Port 80 is the universal default for HTTP servers; keeping nginx.conf at its conventional default avoids surprising anyone reading the config, and the whole purpose of Docker's host:container port mapping is to expose a standard internal port under a different external port.
- Alternative: Change nginx.conf to listen 81 instead, which would also have made the ports match.
- Trade-off: Either fix makes the ports agree and would technically work; the choice was purely about which side is more conventional and less surprising to a future reader.
- Evidence / commit: fix: correct NGINX port mapping, upstream ports, and app bind address
- Production improvement: None needed; this is now a standard, conventional setup.

## Decision 2: Use APP_HOST=0.0.0.0 instead of a specific container IP
- Choice: Set the Flask app to bind to 0.0.0.0 (all interfaces) rather than any specific IP address.
- Why: Docker assigns container IPs dynamically; they can change when a container is recreated. Binding to 0.0.0.0 means the app accepts connections on whichever interface it actually has, without needing to know or hardcode that address in advance.
- Alternative: Bind to the container's specific internal IP (e.g. 172.23.0.3).
- Trade-off: 0.0.0.0 is slightly less restrictive than binding to one named interface, but in a single-purpose container (this one only runs the Flask app), there is no meaningful additional attack surface from this, and it is the standard approach for containerized services.
- Evidence / commit: fix: correct NGINX port mapping, upstream ports, and app bind address
- Production improvement: None needed for this project's scope; in a multi-homed host with stricter isolation requirements, a more specific bind address combined with host firewall rules could be considered.

## Decision 3: Use mem_limit/cpus instead of deploy.resources.limits for resource limits
- Choice: Set resource limits using the top-level mem_limit and cpus Compose keys.
- Why: deploy.resources.limits is designed for Docker Swarm mode and is silently ignored under plain "docker compose up", which is how this project runs both locally and in CI. mem_limit/cpus are the keys actually enforced in that context.
- Alternative: Use deploy.resources.limits, which is the more "modern"-looking syntax often shown in examples.
- Trade-off: mem_limit/cpus are considered somewhat legacy syntax, and would need to be revisited if this project were ever deployed under Swarm or Kubernetes, where deploy.resources or equivalent orchestrator-native settings would be the correct choice instead.
- Evidence / commit: fix: add CPU and memory limits to all services
- Production improvement: If migrating to Kubernetes or Swarm, resource limits would need to be re-expressed in that platform's native format (e.g. Kubernetes resources.limits in a Pod spec).

## Decision 4: Restart policy of unless-stopped, applied to all 5 services uniformly
- Choice: Set restart: unless-stopped on app-01, app-02, postgres, redis, and nginx, not just the application tier.
- Why: Any of the 5 services can crash, and the task's requirement for "correct restart policies" is not scoped to only the app layer. A database or cache crashing at an inconvenient time with no auto-recovery is exactly the kind of problem this setting exists to prevent.
- Alternative: Use "always" instead of "unless-stopped", or only apply a restart policy to the app containers and leave postgres/redis/nginx unset.
- Trade-off: "unless-stopped" was chosen over "always" specifically so that a deliberate "docker stop" (such as the one used in failure_test.py) is respected and does not immediately get undone by Docker; "always" would fight against that kind of intentional, controlled testing.
- Evidence / commit: fix: set restart: unless-stopped for all services
- Production improvement: In production, this would typically be layered under an orchestrator (Kubernetes, Swarm) with its own reconciliation loop, which offers stronger guarantees than the Docker Engine's own restart policy (see troubleshooting.md Entry 13 for an observed limitation of relying on this alone).

## Decision 5: Remove Postgres/Redis host port publishing entirely, rather than restricting them
- Choice: Removed the ports: entries from postgres and redis entirely, rather than, for example, binding them only to 127.0.0.1 or adding a firewall rule.
- Why: Nothing in this project's actual functionality requires postgres or redis to be reachable from the host at all; all real traffic to them is container-to-container, using their internal default ports (5432, 6379) via Docker's own DNS. The task brief explicitly states "do not publish app, PostgreSQL or Redis ports", and any published port, however restricted, is still a form of "publishing".
- Alternative: Keep the ports but bind them only to 127.0.0.1 (which was already the case) and rely on that restriction as sufficient isolation.
- Trade-off: Removing the ports entirely means a developer can no longer connect a local database tool (e.g. psql, a Redis GUI) directly from the host for convenience during development; they would need to use "docker exec" instead. This trade-off was accepted since it directly satisfies an explicit task requirement.
- Evidence / commit: fix: remove host port publishing for Postgres and Redis
- Production improvement: None needed; this matches production best practice of not exposing datastore ports externally.

## Decision 6: Postgres persistence via a named volume on the real data directory, not tmpfs
- Choice: Mounted the postgres-data named volume to Postgres's actual data directory (/var/lib/postgresql/data), and removed the tmpfs mount that was previously overriding it.
- Why: A named volume is Docker's standard mechanism for persisting data across container recreation; tmpfs is explicitly RAM-backed and non-persistent by design, so it is fundamentally incompatible with the task's requirement that a record "survive" container recreation.
- Alternative: Keep tmpfs for performance (RAM-backed storage is faster than disk) and accept that data does not persist, documenting this as an intentional trade-off for a purely ephemeral/testing environment.
- Trade-off: A named volume backed by disk is slower than tmpfs, but persistence was an explicit, non-negotiable requirement for this project (proving a record survives container recreation), so correctness was prioritized over raw performance.
- Evidence / commit: fix: mount Postgres named volume to the real data directory
- Production improvement: In production, this would typically be paired with a proper managed database backup/replication strategy rather than relying solely on a local Docker volume, which is still a single point of failure on one host's disk.