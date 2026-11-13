# Frontend handoff

For whoever builds the UI in `frontend/`. The backend is finished for the core features; this page says how to run it, what to call from
each screen, and what to render. Full reference: [`API.md`](API.md). Real responses: [`api-examples/`](api-examples/). The UX
requirements are in PRD §8.4.

## 1. Run the backend

```
docker compose up --build        # http://localhost:8000   (interactive API docs: /docs)
```
or without Docker: `pip install -r backend/requirements.txt && cd backend && python -m app`.

In development run your dev server separately and proxy `/api` and `/images` to `http://localhost:8000` (Vite: `server.proxy`). Never hard-code
a host. The Dockerfile builds `frontend/` with `npm ci && npm run build` and serves `frontend/dist` from the backend, so **`npm run build` must
produce `frontend/dist/index.html`**. Unknown non-API paths fall back to `index.html`, so client-side routes work on refresh.

## 2. Ground rules

- All data comes from `/api/*`. No catalog files, no travel rules, no price maths in the UI — show exactly what the API returns.
- After any change, **replace your local package with the one returned** (single source of truth).
- Never show raw JSON or a stack trace; use `message`, `reason` and `fields[]`.
- Money is an integer in rupees: format with `Intl.NumberFormat('en-IN')` (₹3,50,000). Times are local to the place; `time_label` is ready to show ("9:20 am").
- Keep state in the URL (`/packages/:id`, `/reservations/:number`) so a refresh keeps working.
- **Re-fetch options after every change** — hotel, flight and city-plan options describe the package as it is now.
- The form has **exactly 7 fields** (departure city, country, first day, nights, adults, children's ages, budget). Fill the dropdowns from `GET /api/meta`.

## 3. Screens → calls

| Screen | Calls | Render |
|---|---|---|
| **Enter the trip** (form, empty at start) | `GET /api/meta` → `POST /api/packages` | On 422, put each `fields[].message` next to its input. Dates outside 1–20 Apr 2027 are *not* a field error — they come back as `NO_PACKAGE`. |
| **Result of a build** | same response | `PACKAGE` → go to `/packages/:id`. `OVER_BUDGET` → over-budget page. `NO_PACKAGE` → show `message` and an "Edit the trip" button with the previous values. |
| **Over-budget page** | `GET /api/packages/{alt.package_id}` | Plain sentence from `message`; cheapest total and shortfall; one card per `alternatives[]` (label, total, money left) that opens its package; a button for `raise_budget.label` that re-posts the request with the new budget; "Edit the trip". |
| **Package page** | `GET /api/packages/{id}` | Sticky bar: `pricing.total_inr` of `budget_inr`, `remaining_inr` (green/amber/red **and** text). City strip from `city_plan`. One section per `days[]` with its `events` in order; card details from the matching `items[]` entry (`title`, `subtitle`, `icon`, `badges`, `image`, `price_inr`, `quantity`). Banner for `warnings[]`. Buttons: Export, Confirm. |
| **Change hotel / flight / sights** | `GET …/options/hotels?city=` · `…/options/flights?leg=` · `…/options/attractions?date=` then `POST …/changes` | Drawer listing options. Pin the `current` one; show `price_delta_inr` as +₹/−₹; grey out `available:false` options and show `reason_unavailable`; mark `fits_budget:false` options "needs +₹{budget_needed_inr}". |
| **After a change** | `POST …/changes` response | `APPLIED` → swap in `package`, toast `summary`, highlight `changed_item_ids`. `REFUSED` → show `reason` + `suggestion`. `BUDGET_EXCEEDED` → show `message`, `cheaper_options`, and a "Raise budget to ₹{raise_budget_to_inr} and apply" button that re-sends the same change with `raise_budget: true`. `PINNED_CONFLICT` → show `reason` and the two `options`; "apply and remove" re-sends with `remove_pinned_conflicts: true`. |
| **Confirm** | `POST …/confirm` | Show `reservation_number` large with a copy button; link to `/reservations/:number`. Booked packages are read-only (`status: BOOKED`). |
| **Reservation lookup** | `GET /api/reservations/{number}` | Read-only summary using the same timeline. 404 → "Reservation not found". |
| **Export** | `GET …/export` | Plain link/button; the response downloads as a file. |
| **Photo credits** | — | The UI currently shows no photos (the API still serves them at `/images/...`). If photos are added, also show the credits from `hackathon-problem-1-holiday-package/images/ATTRIBUTIONS.md`. |

## 4. Reading a package

```
package.days[i]            → what to draw for that date (kind, city, summary, events[])
package.days[i].events[j]  → { item_id, time, time_label, type, icon, label }
package.items[k]           → the full detail for that item_id (title, subtitle, price_inr, image, badges, pinned, …)
```
`kind`: `ARRIVAL` (day 0), `FULL`, `CITY_CHANGE` (moving to the next city), `LAST` (going home, no hotel night, no sights).
The arrival flight departs the evening before the first day, so it shows as "Land at …" on day 0. Item `pinned: true` means the
traveler chose it — you may show a small "your choice" marker.

## 5. Extra features (all available and wired in the UI)

Interest chips (`RequestForm`), the route map (`RouteMap`), the city-guide and dining drawer (`CityInfoDrawer`) and the "Matches your interests" marks are all connected; `e2e/ui_flow.py` covers them (27 steps).

| Feature | Calls | What to render |
|---|---|---|
| **Quick request box** (S1) | `POST /api/parse-request {text}` | A text box above the form. Fill the form from `fields`; highlight `missing` inputs; show `notes` (assumptions) and, when `ready` is false, ask the traveler to check. |
| **Package variants** (G4) | `POST /api/packages/variants` with the 7 fields | Cards/tabs: *Recommended*, *Cheapest*, *Best rated* (`variant`, `pricing`, `metrics.transit_minutes`, `metrics.avg_hotel_stars`, city strip). Picking one opens `/packages/:package_id`. Show `notes`. `OVER_BUDGET`/`NO_PACKAGE` come back as in the normal build. |
| **Change cities** (G3) | `GET …/options/city-plans` → `POST …/changes {op:"CHANGE_CITY_PLAN", plan}` | A plan chooser: each plan's cities, nights, `total_inr`, `price_delta_inr`, `warnings`; mark `current` and `preferred`; grey/flag `fits_budget:false` ("needs +₹…"). Handle `BUDGET_EXCEEDED` and `PINNED_CONFLICT` like any other change. |
| **Undo** | `POST …/undo` | An "Undo" button/toast after every applied change (`undo_available`); replace the package with `package`. |
| **"Why this plan"** (S3) | in the package: `rationale` | A short panel: `headline` and the `reasons` list. |
| **Knock-on notes** (G1) | in `APPLIED` responses: `knock_on[]`, `warnings[]` | Show them in the change toast/banner ("Your airport pickup moves from … to …"). |
| **Interest tags** | `meta.interests` → `interests: [...]` on the build body | Chips on the form. On sights show a "Matches your interests" mark when `badges` has `MATCHES_INTEREST`; in the Add-attraction list matching options come first (`matches_interests`). |
| **Pocket city guide** | `GET /api/cities/{city}/guide` | A read-only drawer per city/hotel section with `getting_around`, `etiquette`, `sightseeing_tips`, `good_to_know`. |
| **Nearby dining** | `GET /api/packages/{id}/dining` | 3–4 spots under each hotel with `dietary_tags` and `price_label`; always show the disclaimer: estimated, **not in the total**. |
| **Route map** | in the package: `route` | Departure hub → cities in order with nights, and each leg's mode and duration (`legs[].mode`, `duration_label`). Redraw on every new package (variant switch, change). |
| **Seats/rooms used up** (S2) | `POST …/confirm` | On `409 INVENTORY_CONFLICT` show `error.message` and offer to rebuild the holiday ("Choose another flight or hotel"). |

## 6. Quick manual check

1. Open the form, submit the Menon request: Bengaluru · Japan · 2027-04-10 · 6 nights · 2 adults · child aged 6 · ₹3,50,000.
2. You should get a `PACKAGE` near ₹3.27 lakh; open it, change a Kyoto hotel, add and remove a sight, confirm, then look the number up again.
3. Try ₹2,00,000 to see the over-budget page, and 2027-04-19 + 5 nights for "no package".
