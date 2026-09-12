<img src="assets/barq-logo.svg" alt="BARQ Systems" width="180">

# BARQ DevOps Internship Task - Solution

Flask API behind NGINX, with PostgreSQL and Redis, running as two load-balanced backend
instances. This README documents the actual, working setup after fixing the intentionally
broken starter environment (see `troubleshooting.md` for the full investigation).

## Requirements

- Linux or WSL2
- Docker with Compose
- Python 3.12 (for running `validate.py` / `failure_test.py` outside a container)

## Setup

```bash
git clone https://github.com/Habeba-ehab/barq-devops-internship-task.git
cd barq-devops-internship-task
cp .env.example .env
```

## Build and start

```bash
docker compose -p barq-assessment up --build -d
docker compose -p barq-assessment ps -a
```

All 5 containers (`app-01`, `app-02`, `nginx`, `postgres`, `redis`) should show `Up` and
`(healthy)` after a few seconds. If any show `(unhealthy)` or `Exited`, check logs:

```bash
docker compose -p barq-assessment logs --no-color
```

## Verify it's working

```bash
curl -i http://127.0.0.1:8080/health
curl -i http://127.0.0.1:8080/ready
curl -i http://127.0.0.1:8080/instance
curl -H 'Content-Type: application/json' -d '{"title":"example record"}' http://127.0.0.1:8080/records
curl http://127.0.0.1:8080/records
curl http://127.0.0.1:8080/counter
```

## Run the validation suite

Checks public access, all endpoints, both backends, PostgreSQL/Redis readiness, network
isolation, and that Postgres/Redis ports are not published to the host.

```bash
python3 validate.py
echo "Exit code: $?"   # 0 = all checks passed
```

## Run the failure/recovery test

Stops `app-01`, measures traffic/errors while it is down, restores it, and proves it
resumes serving requests.

```bash
python3 failure_test.py
echo "Exit code: $?"   # 0 = failure and recovery both verified
```

## Backup and restore PostgreSQL

```bash
# Create a backup (writes a timestamped .sql file to ./backups/)
./backup.sh

# Restore from a specific backup file
./restore.sh ./backups/backup_<timestamp>.sql
```

To prove persistence across container recreation:

```bash
curl -X POST -H 'Content-Type: application/json' -d '{"title":"persistence check"}' http://127.0.0.1:8080/records
docker compose -p barq-assessment up -d --force-recreate postgres
curl http://127.0.0.1:8080/records   # the record above should still be present
```

## Run the log analysis scripts

Analyzes the three historical logs in `logs/` (see `log_analysis.md` for full findings).

```bash
python3 scripts/q3_status_counts.py
python3 scripts/q4_failures.py
python3 scripts/q5_latency.py
python3 scripts/q6_retries.py
python3 scripts/q7_timeline.py
```

## Stop

```bash
docker compose -p barq-assessment down
```

Do not add `-v` here if you want to keep the Postgres/Redis data volumes between runs.

## Full cleanup (removes all data)

```bash
docker compose -p barq-assessment down -v
```

This removes the named volumes (`postgres-data`, `redis-data`), so all database records and
the Redis counter will be permanently lost. Only run this when you genuinely want a clean
slate.

## Project structure

- `docker-compose.yml`, `Dockerfile`, `app/`, `nginx/nginx.conf` - the environment
- `config/app.env` - non-secret app configuration (real secrets should not live here in
  production, see `security_review.md`)
- `validate.py`, `failure_test.py`, `backup.sh`, `restore.sh` - Part 3 automation
- `.github/workflows/ci.yml` - CI pipeline (checkout, syntax check, build, start, wait,
  validate)
- `logs/`, `log_analysis.md`, `scripts/` - historical log analysis
- `troubleshooting.md`, `decisions.md`, `security_review.md`, `AI_USAGE.md` - reports
- `docs/EVIDENCE_INDEX.md` - requirement-to-evidence mapping

## Documentation

- [troubleshooting.md](troubleshooting.md) - investigation journal for every issue found and fixed
- [log_analysis.md](log_analysis.md) - analysis of the three historical logs
- [decisions.md](decisions.md) - technical decisions, alternatives, and trade-offs
- [security_review.md](security_review.md) - security findings and production follow-ups
- [AI_USAGE.md](AI_USAGE.md) - AI usage disclosure