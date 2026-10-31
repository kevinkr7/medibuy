# React/Vite Integration

## Local configuration

Add this to the frontend's `.env.local`:

```dotenv
VITE_API_BASE_URL=http://127.0.0.1:8000
```

Read it once in the API client:

```ts
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL;

export async function getDashboard() {
  const response = await fetch(`${API_BASE_URL}/dashboard`);
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.error?.message ?? "Request failed");
  return payload;
}
```

After a successful `POST /purchase-orders`, refetch `/purchase-orders`,
`/rebates/2025` and `/dashboard`; a backdated purchase can change later results.

## Start the backend on Windows

From the cloned repository root:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m app.seed
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

Swagger: <http://127.0.0.1:8000/docs>

The default development CORS origins are:

- `http://localhost:5173`
- `http://127.0.0.1:5173`

Override them before launch when necessary:

```powershell
$env:MEDIBUY_CORS_ORIGINS = "http://localhost:3000,http://127.0.0.1:3000"
```

## Remote preview limitation

A hosted frontend preview runs on a remote origin and normally cannot reach a
backend bound to `127.0.0.1` on the developer's PC. For the interview, run the
React/Vite frontend locally alongside local FastAPI. A hosted preview would need
a separately hosted HTTPS backend and that public origin added to
`MEDIBUY_CORS_ORIGINS`; deployment is outside this assessment.

## UI guidance

- Use `/agreements` to show V1 and V2 as versions of the same annual agreement.
- Use server-returned calculations everywhere; never duplicate tier logic in React.
- Keep buyer-entered price, correct contract price and signed variance visible.
- Label rebates as earned or qualified. Do not call them unpaid or claimed.
- Preserve the signs of variance values and format the returned money strings as INR.
