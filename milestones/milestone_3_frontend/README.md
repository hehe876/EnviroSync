# Frontend block — React + Vite dashboard

**Owns:** responsive UI, date filters, multi-region comparisons and SVG charts, real data API client, CSV export, API status and error displays.
This is labeled `milestone_3_frontend` as the next functional block in the repository; it does **not** claim a separately delivered historical milestone 3.

This block **never imports Python, AWS credentials, Boto3, or local historical examples**. It talks to the Milestone 2 read-only HTTP API via `/api/*` (proxied by Vite in development).

## Files

- `src/App.jsx` — interactive page/controller.
- `src/components/` — chart, icon and API-status presentation.
- `src/lib/api.mjs` — HTTP client and error handling.
- `src/lib/dates.mjs` — date validation and period selection.
- `src/lib/format.mjs` — numerical formatting and CSV export.
- `src/lib/*.test.mjs` — Node's built-in offline test runner.
- `src/styles.css` — responsive styling.
- `vite.config.js` — local proxy from port 5173 to FastAPI port 8000.

## Commands (from repository root)

```powershell
.\scripts\setup-frontend.ps1
.\scripts\start-frontend.ps1
```

Open http://127.0.0.1:5173 with the backend running simultaneously.

Offline tests do not require browser or AWS: `npm run test` inside this block. Production build is `npm run build` after npm dependencies have been installed. The dashboard does not pass historical examples off as live data when the backend is unavailable.

After the first successful `npm install`, **commit `package-lock.json`** so GitHub Actions can eventually use `npm ci` for reproducible installations.
