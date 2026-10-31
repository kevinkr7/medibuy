# MediBuy Deployment Readiness Checklist

This document records the Phase 07 audit only. It does not implement deployment,
PostgreSQL support, migrations, authentication, or external infrastructure.

## Current baseline

- [x] FastAPI exposes `GET /health` and generated OpenAPI documentation.
- [x] CORS uses an explicit environment-configurable origin list.
- [x] Frontend reads `VITE_API_BASE_URL` through one API client.
- [x] Backend and frontend dependency versions are locked.
- [x] SQLite seed loading is transactional and idempotent.
- [x] Local databases, environment files, dependencies and build output are ignored.
- [ ] Production deployment is ready. Complete the gaps below first.

## Render backend

Proposed startup command:

```text
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

| Requirement              | Status       | Required follow-up                                                                                                                         |
| ------------------------ | ------------ | ------------------------------------------------------------------------------------------------------------------------------------------ |
| Configurable port        | Partial      | Render can inject `PORT` into the startup command; the application does not read it directly.                                              |
| Python version           | Gap          | Add a supported Python version pin after confirming Render's available runtime. Local development uses Python 3.11.                        |
| Dependencies             | Local-ready  | `requirements.txt` is sufficient for SQLite; Phase 08 must add the selected PostgreSQL driver.                                             |
| `DATABASE_URL`           | Gap          | Current code reads only `MEDIBUY_DATABASE_PATH`. Add URL-based engine configuration in Phase 08.                                           |
| PostgreSQL compatibility | Gap          | Validate SQLAlchemy types and constraints against Neon; do not assume SQLite behavior is identical.                                        |
| Hosted CORS              | Configurable | Set `MEDIBUY_CORS_ORIGINS` to the exact deployed frontend origin. Do not use `*`.                                                          |
| Health check             | Ready        | Configure Render to request `/health`.                                                                                                     |
| Schema initialization    | Gap          | Choose migrations or an explicit one-time initialization command before production. App startup intentionally does not mutate schema/data. |
| Seed strategy            | Gap          | Keep synthetic demonstration seeding explicit and separate from production startup.                                                        |
| Public writes            | Unsafe as-is | `POST /purchase-orders` is unauthenticated. Disable it publicly or add an access policy before exposure.                                   |

## Neon PostgreSQL

- [ ] Create the Neon project and store its connection string only in Render's secret environment.
- [ ] Add `DATABASE_URL` handling without exposing it to the frontend.
- [ ] Add the PostgreSQL driver and connection/SSL settings.
- [ ] Introduce a repeatable schema initialization or migration strategy.
- [ ] Run the full database, pricing, rebate and API suites against temporary PostgreSQL.
- [ ] Decide whether synthetic seed data belongs in the hosted demonstration database.
- [ ] Document backup, reset and least-privilege database credentials.

These tasks belong to Phase 08. No Neon resource or credential exists in this
repository.

## Cloudflare frontend

| Requirement  | Status               | Required follow-up                                                                                                                                      |
| ------------ | -------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Build root   | Ready                | Use `frontend/`.                                                                                                                                        |
| Install      | Ready                | Use `bun install --frozen-lockfile`.                                                                                                                    |
| Build        | Local-ready          | `bun run build` succeeds and currently emits a Nitro `node-server` bundle.                                                                              |
| Pages target | Gap                  | Select and verify an appropriate Cloudflare Pages/Workers or static-SPA target; the current Node server bundle is not a Pages deployment configuration. |
| API URL      | Configurable         | Set `VITE_API_BASE_URL` to the HTTPS Render API during the production build. The source fallback is local development only.                             |
| Secrets      | Ready                | Do not place database URLs, tokens or server credentials in `VITE_*` variables.                                                                         |
| Routing      | Decision required    | The app uses TanStack Start SSR. If converted to a static SPA, configure fallback routing; otherwise deploy a supported Cloudflare server adapter.      |
| CORS         | Pending deployed URL | Add only the final HTTPS frontend origin to `MEDIBUY_CORS_ORIGINS`.                                                                                     |

## Pre-deployment security gate

- [ ] Decide how demonstration users may create purchase orders.
- [ ] Add request rate/size limits appropriate for public access.
- [ ] Restrict CORS to the exact production origin.
- [ ] Store all server secrets in provider secret stores, never Git or frontend variables.
- [ ] Run dependency and secret scanning in CI.
- [ ] Verify logs do not disclose request credentials or database URLs.
- [ ] Confirm synthetic data is clearly labelled and contains no real supplier information.

## Release verification

- [ ] Backend tests pass against PostgreSQL.
- [ ] Dataset validator still passes unchanged.
- [ ] Frontend typecheck, tests, lint and production build pass.
- [ ] Health check, CORS, dashboard, PO verification and rebate endpoints pass over HTTPS.
- [ ] A disposable hosted write test succeeds without mutating the preserved local fixture.
- [ ] Manual desktop and mobile UI verification is complete.
