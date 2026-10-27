# Release preservation (v3.1.0 combined image)

**Version:** v3.1.0  
**Issue:** #916  
**Audience:** Developers and later Cursor sessions working on the Build/Plan → Execute split

`v3.1.0` is the last combined Build + Plan + Execute image (immutable tag). Current `main` splits them: Create is Build + Plan (`app.main`); Execute is `app.execute_app`. #916's keep-Execute-on-Create rule was retired in **#938**. Rebuild `v3.1.0` from the tag if you need the old all-in-one app.

---

## Verified v3.1.0 release

| Item | Value |
| --- | --- |
| Git tag | `v3.1.0` (annotated; do not move) |
| Tag object | `1ef3658082a78047ee7842ebef6dc7b6d3bc79b6` |
| Release commit | `d12621d71a0e33e90f2820fb8d04b96d77d59dad` |
| GitHub release | https://github.com/thomjeff/run-density/releases/tag/v3.1.0 |
| Combined entry point | `Dockerfile` → `gunicorn … app.main:app` |
| Compose workflow | `docker-compose.yml` service `create` (`make create`) |
| Skinny Locations image | Separate `Dockerfile.cloud` → `app.cloud_app:app` |

There is **no published combined `v3.1.0` image** in Artifact Registry or Docker Hub. The last-known-good combined application is the **git tag**. After a local verify build, treat the image ID (`sha256:…`) as the immutable digest for that host/architecture. Do not retag or push over any existing published image, including skinny `runflow-cloud:*`.

**Verified 2026-10-22** (this workstation, `linux/arm64`, clean `git archive v3.1.0`):

- Command: `git archive v3.1.0 | docker build -t runflow:v3.1.0-verify -`
- Local image ID: `sha256:03783f2f07f7864d21af06c89d1fc663e002e223e35f7199610ac1d18dd30076`
- `/health` and `/ready` returned 200; Build / Plan / Execute HTML routes returned 303 (password gate) — not 404/500
- Rebuild on the target architecture rather than copying this arm64 digest to amd64 CI or GCP

**Clean build (committed tree only; ignores `dev.env` and other local edits):**

```bash
git archive v3.1.0 | docker build -t runflow:v3.1.0-verify -
```

Or:

```bash
VERIFY_REF=v3.1.0 IMAGE_TAG=runflow:v3.1.0-verify ./scripts/verify_combined_image.sh
```

Optional local archive (do not commit the tarball):

```bash
docker save -o /tmp/runflow-v3.1.0-verify.tar runflow:v3.1.0-verify
```

---

## A. Check out and build original Runflow v3.1.0

```bash
git fetch --tags origin
git rev-parse v3.1.0^{commit}   # must be d12621d71a0e33e90f2820fb8d04b96d77d59dad
VERIFY_REF=v3.1.0 IMAGE_TAG=runflow:v3.1.0-verify VERIFY_PORT=18080 ./scripts/verify_combined_image.sh
```

To run the release interactively without touching the current `main` checkout:

```bash
git worktree add /tmp/runflow-v3.1.0 v3.1.0
cd /tmp/runflow-v3.1.0
# copy a local-only env file if you need the password gate
docker run --rm -p 8080:8080 --env-file /path/to/dev.env runflow:v3.1.0-verify
```

Do **not** `git checkout v3.1.0` on a shared `main` worktree if you have feature-branch work in progress.

Uncommitted files required at **runtime** (not at image build):

- `dev.env` — Compose `env_file` (password, local flags). Tracked, but local edits must stay uncommitted.
- Host `.env` — optional `RUNFLOW_ROOT` for Compose volume interpolation. Copy from `.env.example`.
- `./runflow` — analysis and Execute JSON. Not baked into the combined image.

The image **build** copies only committed `app/`, `data/`, `config/`, `frontend/static`, and `frontend/templates`.

---

## B. Build and run the current combined application from `main`

```bash
git checkout main
git pull origin main
make create         # Create (Build + Plan) on http://localhost:8080
make execute        # optional: Execute + Postgres on http://localhost:8081
```

Equivalent committed-tree verify (no Compose bind-mounts):

```bash
IMAGE_TAG=runflow:dev-$(git rev-parse --short HEAD) ./scripts/verify_combined_image.sh
```

`make create` bind-mounts source for hot reload. That is the daily authoring workflow. A `git archive` verify build is what proves the **committed** tree still produces the combined Create image.

---

## C. Build and test a feature branch without affecting the release

1. Branch from current approved `main`: `feat/<issue>-<short-name>`.
2. Keep the change scoped to that issue. No unrelated refactors under #916.
3. Use a **development image tag**, never `v3.1.0`:

   ```bash
   IMAGE_TAG=runflow:dev-feat-917-$(git rev-parse --short HEAD) ./scripts/verify_combined_image.sh
   ```

4. Open a pull request. Do not merge automatically. Do not rebase or force-push `main` or the `v3.1.0` tag.
5. Do not deploy a feature branch to the production GCP skinny Locations service.
6. Do not add PostgreSQL / SQLAlchemy to the combined image until the approved Execute migration stage.

CI on every PR builds the combined image from the PR commit (`git archive`), starts it, checks critical routes, and runs the combined-image plus Execute/Build/Plan regression subset.

---

## D. Create and Execute images (current `main`)

- Create: `Dockerfile` + `app.main:app` — Build + Plan, including Day Plan publish. No Execute operator routes (#938).
- Execute: `Dockerfile.execute` + `app.execute_app:app` — race day.
- Keep `Dockerfile.cloud` as the read-only skinny Locations image until #936 replaces that path.
- Feature-branch tags stay `runflow:dev-…`. Release tags stay immutable. Do not move `v3.1.0`.

---

## E. Recover or redeploy the last known-good release

If a later `main` or feature branch fails:

1. Rebuild from the immutable tag (preferred):

   ```bash
   git archive v3.1.0 | docker build -t runflow:v3.1.0-verify -
   docker run --rm -p 8080:8080 --env-file dev.env runflow:v3.1.0-verify
   ```

2. Or load a local `docker save` archive if you made one after verify.
3. Skinny Locations Cloud Run Make targets were removed in #935. `Dockerfile.cloud` remains until volunteer location sheets in Execute (#936) replace that path. Do not deploy a feature-branch Execute image as the skinny Locations service.

Do not move tag `v3.1.0`. If a later release is needed, cut `v3.1.1` or `v3.2.0`.

---

## Regression baseline (must keep working)

| Area | What must keep working | Automated coverage today |
| --- | --- | --- |
| Combined image | `Dockerfile` + Compose service `create` + `app.main:app` start; **no Execute routes** (#938) | `tests/unit/test_combined_image_preservation.py`; `scripts/verify_combined_image.sh` |
| Build | Legs, courses, runners, packages; Build owns location edits | `test_issue904_build_plan_ownership.py`, config-package / legs / runners unit tests |
| Plan | Analysis launch, Overview / Density / Flow / Junctions / Motion / Progression / Locations; publish Day Plan ZIP | `test_issue798_phase1_routers.py`, analysis / density / flow / progression unit tests; Create UI or Postman |
| Execute | Purpose-built image (`app.execute_app`) | `test_issue893_execute_board.py`, `test_issue911_participants.py`, `test_issue912_incidents.py`, `test_issue914_incidents.py` (against `execute_app`) |
| Workspace chrome | Create: Build \| Plan. Execute image: Plans \| Operations \| Participants \| Incidents | `test_issue878_workspace_nav.py` |
| Skinny cloud | Read-only Locations (`Dockerfile.cloud`) | Docs only; Make wrappers removed in #935; **no automated startup test** |
| Local Docker | `make create` on port 8080; `make execute` on port 8081 | CI combined-image workflow |

**Gaps (do not paper over by changing product code):**

- GitHub Actions `code-quality.yaml` lints **changed `app/` Python files** (flake8 / black / isort). Whole-tree `app/` flake8 still fails on pre-existing style debt and is not the PR gate.
- Combined-image verify (`.github/workflows/combined-image-verify.yaml`) builds, starts, and regresses the combined Create image on every PR via `scripts/verify_combined_image.sh`.
- Saturday/Sunday `tests/e2e.py` is archived under `tests/archive/`. CI runs a unit/regression subset.
- No registry-hosted combined `v3.1.0` digest yet.
- Skinny cloud image is not built on every PR.

---

## Discipline for Epic #916

- One implementation issue per `feat/` branch from current `main`.
- Pull requests into `main`; do not auto-merge.
- Do not rebase or force-push protected release tags or shared branches.
- Do not change existing Reopen / Participants / Incidents behavior to make new tests pass.
- Do not begin #917 until this preservation work has been reviewed.
