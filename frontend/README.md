# normad-grid: the web app

React 19 + Vite 6 + Tailwind CSS v4 + lucide icons. The look is a Booking.com-style navy `#003580` / blue `#006ce4` / yellow `#febb02`.
The app has **no business logic of its own**: every package, rule check, price and booking comes from the NomadGrid API (`../backend`).

## Run it

| Way | Command | URL |
|---|---|---|
| Everything in one container | `docker compose up --build` (from the repo root) | http://localhost:8000 |
| Live editing in Docker (auto-reload) | `docker compose -f docker-compose.dev.yml up --build` (repo root) | UI http://localhost:5173, API :8000 |
| Without Docker | `scripts/start.sh` / `scripts/start.ps1` / `scripts/start.bat` (repo root) | http://localhost:8000 |
| UI only, hot reload | `cd frontend && npm install && npm run dev` (needs the API on :8000, `cd backend && python -m app`) | http://localhost:5173 |

`npm run dev` proxies `/api` and `/images` to the API (`API_TARGET` overrides the address, `vite.config.js`). `npm run build` writes `dist/`, which the API serves.

## Screens (`src/pages`, `src/components`)

| Route | What it shows |
|---|---|
| `/` | The request form: 7 fields (departure city, country, start date, nights, adults, children + ages, budget), optional interest chips, a "type your trip in plain words" box, and sample trips. Field messages come from the API. |
| `/packages/:id` | A package: "Your journey" route box, "Why this plan", the day-by-day itinerary with hotel and sight photos, City Guide and Nearby Dining drawers, and the booking summary with total, budget bar, confirm, undo, compare city plans and JSON export. |
| `/compare` | Cheapest, Best rated and Recommended side by side. |
| `/outcome` | "Budget too small" (cheapest total, alternatives that fit, raise-budget button) and "no valid package" with the reason. |
| `/reservations/:number` | The booking confirmation and summary; also opens from the top bar's 10-digit lookup, after a restart. |
| `/credits` | Photo credits, read from the data pack's `images/ATTRIBUTIONS.md` (required when photos are shown). |

## Where things live

- `src/api/client.js`: the only place that calls the API. `src/api/adapt.js`: renames the API package into the shape the screens use.
- `src/lib/request.js`: the only translator between the form's field names and the API's. `src/lib/planInsights.js`: the "rule and trade-off check" text.
- `src/context/AppContext.jsx`: app state (current package, variants, outcome) and every action (build, change, undo, confirm, look up).
- The API contract with examples: `../docs/API.md` and `../docs/api-examples/`. What each screen should call: `../docs/FRONTEND_HANDOFF.md`.

## Test it in a real browser

With the app running on :8000: `python e2e/ui_flow.py http://localhost:8000` (repo root; needs `pip install playwright` and Edge). It walks the whole journey in 30 steps and fails on any console or server error.
