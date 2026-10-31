# MediBuy Frontend

React and TypeScript frontend for the MediBuy contract-pricing and earned-rebate
API. Financial calculations remain exclusively in the FastAPI backend.

## Local development

Install dependencies from the checked-in Bun lockfile:

```powershell
bun install --frozen-lockfile
```

Set the API URL in `.env` (see `.env.example`):

```dotenv
VITE_API_BASE_URL=http://127.0.0.1:8000
```

Start the frontend:

```powershell
bun run dev
```

Open <http://127.0.0.1:5173>.

## Verification

```powershell
bun run typecheck
bun run test
bun run lint
bun run build
```

## Stack

- React 19
- TypeScript
- TanStack Start, Router and Query
- Vite
- Tailwind CSS
- Vitest
