# Docker Development Guide

**Last Updated:** 2026-10-26  
**Issue:** #935

Local Runflow is two Docker environments. **Create** is Build + Plan (author a race). **Execute** is race day. Product chrome stays Build | Plan | Execute.

Both can run at once. They do not share a filesystem. Publish a Day Plan ZIP from Create and import it in Execute.

---

## Quick Start

```bash
make create          # Build + Plan on http://localhost:8080 (hot reload)
make execute         # Execute + Postgres on http://localhost:8081
make stop-create     # Create only
make stop-execute    # Execute and Postgres only
```

| Environment | Make | Container | Port | Image |
|-------------|------|-----------|------|--------|
| Create (Build + Plan) | `make create` | `runflow-create` | 8080 | `Dockerfile` → `app.main:app` |
| Execute | `make execute` | `runflow-execute` | 8081 | `Dockerfile.execute` → `app.execute_app:app` |
| Execute Postgres | (with Execute) | `runflow-execute-db` | 5433 | `postgres:15` |

Create bind-mounts `app/`, `frontend/`, `tests/`, and `runflow/`, so Python and UI edits hot-reload.

Execute copies files at image build time into a named volume. After Execute backend or frontend changes, run `make execute` again (it rebuilds).

`make create` and `make execute` are detached and `--build` on start. A separate `make build` is not used.

---

## Health checks

```bash
curl http://localhost:8080/health
curl http://localhost:8080/ready
curl http://localhost:8081/health
curl http://localhost:8081/ready
```

---

## Volume mounts (Create)

| Local Path | Container Path | Purpose |
|------------|---------------|---------|
| `./app` | `/app/app` | Application code (hot-reload) |
| `./frontend/templates` | `/app/frontend/templates` | HTML templates |
| `./frontend/static` | `/app/frontend/static` | CSS / JS |
| `./data` | `/app/data` | Input CSV and GPX files |
| `./config` | `/app/config` | YAML configuration |
| `${RUNFLOW_ROOT:-./runflow}` | `/app/runflow` | Analysis outputs |
| `./tests` | `/app/tests` | Pytest suite |

Copy `.env.example` → `.env` and set `RUNFLOW_ROOT` if analysis data lives outside the repo. Compose uses that value for the volume mount and for `RUNFLOW_ROOT_HOST` path rewrite inside the container.

Changes to `dev.env` or `docker-compose.yml` require `make stop-create` then `make create` (same for Execute).

---

## Other Make targets

```bash
make prune-runs KEEP=n           # prune old analysis run_ids (Create must be up)
make ai-prompt RUN_ID=...        # generate an AI prompt (Create must be up)
```

Saturday/Sunday `tests/e2e.py` is archived under `tests/archive/`. Run new plans from the Create UI or Postman.

Combined-image CI calls `scripts/verify_combined_image.sh` (not a Make target). See [release-preservation.md](release-preservation.md).

Skinny Cloud Run Make targets were removed. `Dockerfile.cloud` remains until volunteer location sheets in Execute (#936) replace that path. See [cloud-container.md](../user-guide/cloud-container.md).

---

## Troubleshooting

**Port in use**

```bash
lsof -i :8080
lsof -i :8081
```

**Logs**

```bash
docker logs runflow-create --tail 100
docker logs runflow-execute --tail 100
docker compose config
```

**Hot reload not working (Create)**

```bash
docker exec runflow-create ps aux | grep uvicorn
docker exec runflow-create ls -la /app/app/
make stop-create && make create
```

**Execute UI or API still old after a code change**

Execute does not bind-mount source. Run `make execute` again so the image rebuilds.

**Create vs Execute data**

Create writes `./runflow` (or `RUNFLOW_ROOT`) on the host. Execute stores imported plans in the `execute-runtime-data` volume. Copying folders between them is not the handoff; the Day Plan ZIP is.
