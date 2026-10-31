# MediBuy — Contract Pricing & Retroactive Rebate Engine

## Project overview

MediBuy is a contract-pricing and retroactive-rebate verification application for
medical-manufacturing procurement. It combines a SQLite persistence layer,
deterministic Python pricing engine, FastAPI REST API and a responsive
React frontend. The backend recalculates stored purchase orders chronologically;
the frontend only displays and submits API data and never reimplements financial
rules.

## Business problem

Medical manufacturers may buy the same material under annual supplier agreements
that change price mid-year, apply quantity discounts by calendar quarter and award
a retroactive rebate only after an annual target is reached. Manually choosing the
correct dated amendment, cumulative tier and rebate base is error-prone. MediBuy
keeps each amendment under its parent agreement and produces an auditable pricing
result for every purchase order line.

## Features

- Dated agreement versions and version-specific quarterly price tiers.
- Chronological PO verification with contract price, signed variance and status.
- Retroactive annual rebate qualification across all versions of an agreement.
- Transactional, idempotent loading of the supplied synthetic fixture.
- Dashboard, agreement history, PO search/detail and earned-rebate views.
- Consistent typed API responses and errors, including validation and conflicts.
- Isolated SQLite tests and frontend contract tests aligned with OpenAPI.

## Technology stack and architecture

| Layer          | Technology                                                      | Responsibility                                                                  |
| -------------- | --------------------------------------------------------------- | ------------------------------------------------------------------------------- |
| Frontend       | React 19, TypeScript, Vite, TanStack Router/Query, Tailwind CSS | Dashboard, agreement/version explorer, PO verification and earned-rebate report |
| API            | FastAPI, Pydantic, Uvicorn                                      | Typed REST contract, validation, CORS and consistent errors                     |
| Business logic | Python `Decimal` services                                       | Chronological tier pricing, variance and retroactive annual rebates             |
| Persistence    | SQLAlchemy 2 and SQLite                                         | Five related tables and transactional seed loading                              |

`frontend/src/lib/api/client.ts` is the frontend's single API gateway. Route
handlers in `app/api.py` delegate calculation to `app/services.py`; ORM models
remain in `app/models.py`. Money is stored and calculated without binary
floating-point arithmetic.

## Run locally (PowerShell)

Run commands from the cloned repository root. Activation is optional when using
the virtual environment interpreter directly.

Install and seed the backend from PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m app.seed
```

Install the frontend from its existing Bun lockfile. With Bun installed:

```powershell
Set-Location frontend
bun install --frozen-lockfile
Set-Location ..
```

If Bun is not installed globally, `npx --yes bun@latest install
--frozen-lockfile` performs the same locked install from the `frontend`
directory.

Start the backend in one terminal:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Start the frontend in a second terminal:

```powershell
Set-Location frontend
bun run dev
```

The local frontend configuration is `VITE_API_BASE_URL=http://127.0.0.1:8000`
in `frontend/.env`; local `.env` files are ignored while `.env.example` is
preserved.

Frontend: <http://127.0.0.1:5173>

Health check: <http://127.0.0.1:8000/health>

Interactive API docs: <http://127.0.0.1:8000/docs>

OpenAPI specification: <http://127.0.0.1:8000/openapi.json>

The checked-in OpenAPI handoff package is in `frontend_handoff/`.

On a fresh checkout, first create the environment with a working Python 3.11+
installation: `python -m venv .venv`.

## REST API

| Method | Path                             | Purpose                                     |
| ------ | -------------------------------- | ------------------------------------------- |
| `GET`  | `/health`                        | Service health                              |
| `GET`  | `/suppliers`                     | Supplier and material catalog               |
| `GET`  | `/agreements`                    | Agreements with dated versions and tiers    |
| `GET`  | `/purchase-orders`               | Chronological POs with current verification |
| `GET`  | `/purchase-orders/{po_id}/price` | Full verification for one PO                |
| `POST` | `/purchase-orders`               | Validate, persist and price a PO            |
| `GET`  | `/rebates/{year}`                | Earned annual rebate report                 |
| `GET`  | `/dashboard`                     | Portfolio counts and financial totals       |

Create a purchase order:

```powershell
$body = @{
    po_id = "P16"
    supplier_id = "S1"
    material_code = "RESIN-MED"
    purchase_date = "2025-08-03"
    quantity = 50
    entered_unit_price = "110.00"
    currency = "INR"
} | ConvertTo-Json

Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/purchase-orders `
    -ContentType application/json -Body $body
```

Example price response fields:

```json
{
  "po_id": "P06",
  "agreement_id": "AGR-001",
  "agreement_version_id": "AGR-001-V2",
  "quarter": "2025-Q2",
  "quarter_quantity_after_po": 700,
  "tier_discount_percent": 5,
  "base_unit_price": "110.00",
  "entered_unit_price": "110.00",
  "correct_unit_price": "104.50",
  "correct_line_amount": "20900.00",
  "variance_amount": "1100.00",
  "status": "OVERCHARGED"
}
```

All monetary response fields are strings with exactly two decimal places. Dates
use `YYYY-MM-DD`. Errors consistently use this shape:

```json
{
  "error": {
    "code": "purchase_order_not_found",
    "message": "Unknown purchase order: UNKNOWN"
  }
}
```

The API returns `404` for missing resources or dated agreements, `409` for
duplicates and conflicting configuration, and `422` for invalid request values,
material mismatches or currency mismatches.

A PO dated outside its agreement's inclusive validity window correctly fails with
`404 agreement_not_found`; it is never priced using an expired or future contract.

The frontend uses port 5173. Development CORS permits both localhost and
127.0.0.1 on that port, using an explicit allowlist rather than a wildcard.
Override the complete list with a comma-separated environment variable before
starting Uvicorn:

```powershell
$env:MEDIBUY_CORS_ORIGINS = "http://localhost:3000,http://127.0.0.1:3000"
```

## Synthetic dataset and validation

The bundled 2025 dataset is synthetic demonstration data. It contains 3 suppliers,
3 agreements, 4 versions, 12 tiers and 15 PO lines; it contains no real supplier
or patient information. Run its independent validator with:

```powershell
.\.venv\Scripts\python.exe contract_pricing_rebate_dataset\validate_dataset.py
```

### Example expected results

Verified portfolio totals (INR):

| Value                        |     Amount |
| ---------------------------- | ---------: |
| Contract-priced purchases    | 391,040.00 |
| Buyer-entered purchases      | 397,500.00 |
| Potential overcharges        |   6,860.00 |
| Potential undercharges       |     400.00 |
| Earned annual rebates        |  11,861.00 |
| Contract value after rebates | 379,179.00 |

The original ZIP and all extracted reference files are preserved unchanged.
`expected_results.json` is a test oracle only and must never supply production
calculation results.

The supplied demonstration data represents calendar year 2025. The frontend's
default annual rebate report therefore requests `/rebates/2025`.

## Database model

| Entity                 | Purpose                                                               |
| ---------------------- | --------------------------------------------------------------------- |
| `suppliers`            | Supplier/material catalog records                                     |
| `agreements`           | Annual commercial agreement, target and rebate percentage             |
| `agreement_versions`   | Dated price amendments that remain children of one annual agreement   |
| `price_tiers`          | Version-specific quarterly quantity ranges and integer discounts      |
| `purchase_order_lines` | Original buyer-entered PO facts; calculated results are not persisted |

Original string IDs and date fields are preserved. Foreign keys connect every
version to its parent agreement, each tier to its version and every PO to its
supplier. SQLite foreign-key enforcement is enabled for every connection.

## Architecture and business rules

The application has four small layers:

1. `app.models` defines suppliers, annual agreements, dated agreement versions,
   version-specific price tiers and purchased PO lines.
2. `app.seed` validates and transactionally loads the five supplied JSON inputs.
3. `app.services` performs all pricing and rebate calculations using `Decimal`.
4. `app.api` maps HTTP requests and responses to the persistence and service layers.

An agreement owns one or more non-overlapping versions. The purchase date selects
the version using inclusive effective dates, while quarterly quantity continues
across version amendments belonging to that same agreement. Thus AGR-001-V1 and
AGR-001-V2 are amendments of AGR-001, not separate annual agreements.

For each PO, the service sorts history by `(purchase_date, po_id)`, adds the full
current quantity to its calendar-quarter total and selects a tier whose minimum is
inclusive and maximum is exclusive. The selected discount applies to the entire
current line; later tier upgrades do not rewrite earlier contract prices.

Annual quantity and eligible contract value accumulate across all versions of an
agreement. Once quantity reaches the annual target, the rebate applies to all
discounted contract value for that year, including earlier purchases. Rebates are
reported as earned qualification; the dataset has no claims, payments or credit
notes.

Key assumptions are completed/received seeded purchases, calendar quarters,
current-line tier pricing, two-place `ROUND_HALF_UP` currency rounding and full
chronological recalculation after backdated inserts. The authoritative details
remain in `contract_pricing_rebate_dataset/BUSINESS_RULES.md`.

## Seed the database

Load missing fixture records into `medibuy.db` from the five files under
`contract_pricing_rebate_dataset/seed_data/`:

```powershell
.\.venv\Scripts\python.exe -m app.seed
```

The command is idempotent. Existing records must exactly match the fixture;
conflicts cause the transaction to roll back. To delete application rows and
restore the original 15-PO demonstration state, use the explicit reset option:

```powershell
.\.venv\Scripts\python.exe -m app.seed --reset
```

The loader validates required fields, foreign-key references, inclusive version
date windows and contiguous non-overlapping price tiers before writing anything.
It reads only the five seed files and never reads `expected_results.json`.

## Pricing and rebate services

`app.services` exposes these Phase 02 functions:

- `resolve_agreement_version(session, purchase_order)`
- `calculate_purchase_history(session, year=None)`
- `calculate_purchase_order_pricing(session, po_id)`
- `calculate_annual_rebates(session, year)`

All monetary results are two-place `Decimal` values rounded with `ROUND_HALF_UP`.
Calculations sort stored POs by `(purchase_date, po_id)` every time, allowing a
backdated insert to update all affected later results without cached or persisted
calculated fields.

## Project layout

```text
MediBuy/
|-- contract_pricing_rebate_dataset.zip
|-- contract_pricing_rebate_dataset/  # Original docs, JSON and validator
|-- frontend/                         # React/TypeScript application
|   |-- src/lib/api/                  # OpenAPI-aligned types and single API client
|   |-- src/components/medibuy/       # Dashboard, agreements, POs and rebates
|   `-- src/test/                     # Vitest routing and API-client checks
|-- frontend_handoff/                 # OpenAPI document, samples and handoff notes
|-- app/
|   |-- __init__.py
|   |-- main.py                      # FastAPI app and CORS configuration
|   |-- api.py                       # REST routes and error mapping
|   |-- database.py                  # SQLite engine, sessions, declarative base
|   |-- models.py                    # Five SQLAlchemy persistence models
|   |-- schemas.py                   # Pydantic API contracts
|   |-- seed.py                      # Validation, idempotent seed and reset CLI
|   `-- services.py                  # Pricing, variance and rebate engine
|-- tests/
|   |-- conftest.py
|   |-- test_api.py
|   |-- test_database.py
|   `-- test_services.py
|-- .venv/                          # Local environment, ignored by Git
|-- .gitignore
|-- pytest.ini
|-- requirements.txt
`-- README.md
```

The database is configured at `medibuy.db` in the project root. Tables are
created by the seed command; application startup does not mutate the database.
Future currency calculations must use Python `Decimal`, with two-decimal
`ROUND_HALF_UP` rounding as specified in the supplied business rules; currency
storage must preserve exact decimal values.

For disposable runs, set `MEDIBUY_DATABASE_PATH` to another SQLite file before
starting Python. The environment variable is read when the application imports.

Run the isolated SQLite tests with:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Run all frontend verification from `frontend`:

```powershell
bun run typecheck
bun run test
bun run lint
bun run build
```

API integration tests replace the database dependency with a temporary SQLite
database. They never modify `medibuy.db`. If local demonstration data is changed
through `POST /purchase-orders`, restore the original 15-PO state with:

```powershell
.\.venv\Scripts\python.exe -m app.seed --reset
```

## Deployment plan

The intended hosted architecture is a Cloudflare frontend, Render FastAPI service
and Neon PostgreSQL database. Phase 07 prepares the repository only; it does not
deploy resources or claim PostgreSQL support. Phase 08 must add `DATABASE_URL`, a
PostgreSQL driver, schema initialization, hosted CORS configuration and a safe
public-write policy. The frontend also needs an explicitly verified Cloudflare
Pages/Workers or static-SPA target and a production `VITE_API_BASE_URL`.

See [DEPLOYMENT_CHECKLIST.md](DEPLOYMENT_CHECKLIST.md) for the audited gaps and
release gates.

## Known limitations

- This assessment uses SQLite and recalculates the small purchase history on each
  request; it is not designed for high-volume concurrent writes.
- Authentication, goods receipts, returns, taxes, freight, multi-currency FX and
  rebate claim/payment tracking are out of scope.
- Agreement/version and tier overlap checks run during seed validation. Direct
  database writes must enforce the same configuration rules.
- A remotely hosted frontend cannot reach a FastAPI server bound only to
  `127.0.0.1`; use local React/Vite with local FastAPI for the interview demo.
- The UI reports rebates as earned qualification only. It does not claim that a
  rebate was paid, received or settled.

## Manual UI verification checklist

After both local servers start, verify these items in a browser:

- Dashboard shows 3 suppliers, 3 agreements, 15 POs and the API-calculated 2025 totals.
- AGR-001 expands as one agreement with V1 ending May 14 and V2 beginning May 15, 2025.
- Searching for P06 shows contract unit price INR 104.50 and version AGR-001-V2.
- A new valid PO submits successfully and refreshes the PO list, dashboard and rebate report.
- Reusing its PO ID displays the backend's readable duplicate error.
- Rebate cards remain labelled **earned** and show their trigger PO/date.
- At approximately 390 px width, PO cards replace the wide table and dialogs remain usable.
- Loading, empty, retry and **Backend unavailable** states remain readable.

Browser rendering and responsive layout are deliberately manual checks; automated
backend, direct-HTTP, API-client, type, lint and production-build checks do not
prove visual correctness.
