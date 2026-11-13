# Architecture

How NomadGrid "Build My Holiday" is put together, and why. Companion documents: [`PRD.md`](PRD.md) (what and why),
[`API.md`](API.md) (endpoint reference), [`FRONTEND_HANDOFF.md`](FRONTEND_HANDOFF.md) (for the UI developer),
[`break-it-log.md`](break-it-log.md) (what was attacked and what broke).

## 1. The shape of the system

```
┌──────────────────────┐        ┌────────────────────────────────────────────────────────────┐
│  React frontend      │  JSON  │  FastAPI backend (one container, port 8000)                │
│  (frontend/ — the    │◄──────►│                                                            │
│  teammate's work)    │ /api/* │  api/        routes · request validation · error shape     │
│                      │        │    │                                                       │
│  built into the same │        │    ├─► engine/     build a package (cities, flights,       │
│  container, served   │        │    │               hotels, transfers, attractions)         │
│  by FastAPI          │        │    ├─► changes/    change hotel/flight, add/remove sights, │
└──────────────────────┘        │    │               options with price differences          │
                                │    ├─► validator/  INDEPENDENT rule checker                │
                                │    ├─► export/     package object + shared trip format     │
                                │    └─► store/      SQLite: packages + reservations         │
                                │                                                            │
                                │  catalog/  read-only data/catalog/*.json loaded in memory  │
                                └────────────────────────────────────────────────────────────┘
        Docker volume:  /app/storage  (SQLite, survives restarts)      Baked into the image (read-only): /app/data, /app/images
```

**Three rules shape everything**
1. **The backend owns all logic.** City choice, rules, prices and re-checks live in Python; the frontend only renders what the API returns.
2. **The problem statement is the contract.** Hard rules come only from the statement. Our own comfort preferences never become hard rules.
3. **Budget first.** A package is only shown if it passes every rule *and* fits the budget. Otherwise the traveler is told honestly and shown what *is* possible.

## 2. Modules

| Module (`backend/app/…`) | Lines | Responsibility | Depends on |
|---|---:|---|---|
| `config.py` | 26 | Paths (env-overridable), the data window and every tunable constant | — |
| `core/timeutil.py` | 82 | Local-time helpers; service windows (incl. `24:00` and past-midnight); direct earliest/latest-in-window search | — |
| `core/pricing.py` | 54 | The five price formulas and the room-fit rule | — |
| `catalog/loader.py` | 144 | Loads the JSON once, builds indexes; clear error naming `DATA_DIR` if a file is missing; SHA-256 fingerprint to prove the data is untouched | files |
| `interests.py` | 79 | **Interest tags** and the fixed keyword rules that match attractions (category, name, aliases; no AI) | — |
| `engine/cityplan.py` | 39 | Valid city plans (ordered, distinct, ≥ 2 nights each, linked); preferred city count `k*` | catalog |
| `engine/schedule.py` | 75 | When can a transfer actually run: arrival pickup, departure pickup, intercity departure | timeutil |
| `engine/airport.py` | 36 | Cheapest valid airport transfer for a flight + hotel (shared by builder and changes) | schedule, pricing |
| `engine/hotels.py` | 66 | Hotel+room options (fit, availability on every night), stay-quality points, Pareto pruning | pricing |
| `engine/attractions.py` | 164 | Eligible attractions, day placement, full-day assignment (bipartite matching), interest-aware ranking, optional arrival/change-day visits | pricing, timeutil, interests |
| `engine/results.py` | 31 | `BuildResult` and the diagnostics that explain a `NO_PACKAGE` | — |
| `engine/scoring.py` | 33 | The quality score: stay 40, flights 20, experience 15, time 15, budget fit 10 | timeutil |
| `engine/context.py` | 199 | Working data for the search: per-plan candidates (`PlanCtx`) and the per-request session | catalog, attractions |
| `engine/builder.py` | 301 | **The search**: cheapest search, quality search, assembling an itinerary, `build()` | engine modules |
| `engine/alternatives.py` | 109 | Over-budget alternatives (drop a city / fewer nights / shift date, combined) | builder |
| `engine/variants.py` | 222 | **G4** cheapest / best-rated packages; **G3** city-plan options and building a chosen plan | builder |
| `engine/inventory.py` | 17 | Effective seats/rooms = catalog minus our own usage | catalog |
| `engine/models.py` | 94 | `TripRequest` (with `interests`), `Itinerary`, `Leg`, `TransferUse`, `Visit` | — |
| `quickparse/parser.py` | 232 | **S1** plain-words request → form fields and interest tags, with fixed rules | — |
| `export/package.py` | 275 | Itinerary → API package (items with photos and interest marks, day-by-day, pricing, warnings) and → shared trip format | models |
| `export/rationale.py` | 90 | "Why this plan": sentences from the real itinerary, incl. safety margins, rooms and interests | models, export |
| `export/route.py` | 54 | **Journey route**: origin, stops, legs with mode and duration, coordinates | models, catalog |
| `content/` | 41 + 2 JSON | **Pocket city guides** and **nearby dining**: read-only static files outside the catalog | files |
| `validator/validate.py` | 308 | Re-checks every statement rule from the exported trip + raw catalog | catalog only |
| `changes/refusal.py` | 15 | The one exception a change raises when it cannot be done | — |
| `changes/rebuild.py` | 129 | Turn a stored package back into an editable itinerary; recompute derived numbers | engine, export |
| `changes/ops.py` | 282 | The five edits: hotel, flight, add/remove sight, city plan (with the traveler's picks carried over) | rebuild, engine |
| `changes/service.py` | 210 | Apply a change (rebuild → edit → validate → budget check); options with price differences | ops, validator |
| `store/db.py` | 226 | SQLite persistence; atomic idempotent confirm that **uses up seats/rooms**; unique 10-digit numbers; **undo** history | sqlite3 |
| `api/requests.py` | 104 | Per-field validation of the request (7 fields + optional interests) | catalog |
| `api/routes/` | ~370 | HTTP endpoints, one module per area: `meta`, `build`, `packages`, `changes`, `options`, `content`, `reservations` | everything above |
| `api/app.py`, `api/fallback_page.py` | 126 | App factory, error handlers, static files, SPA fallback, "UI not built" page, temp-database fallback | — |

About 4,300 lines of application code and 2,200 lines of tests.

## 3. Life of a "build my holiday" request

```
POST /api/packages
  1. api/requests.py     validate the 7 fields → per-field 422, or a TripRequest
  2. builder.precheck    window (1–20 Apr 2027)? arrival flights that day? seats ≥ travelers? return flights?
                         → NO_PACKAGE with the reason (OUT_OF_WINDOW, NO_ARRIVAL_FLIGHT, INSUFFICIENT_SEATS_…)
  3. cityplan            all valid plans for N nights
  4. PlanCtx.prepare     per plan: hotels (fit + availability), city transfers, attractions for every full day
                         plans that fail record WHY (furthest stage reached explains NO_PACKAGE)
  5. cheapest search     exact minimum total across all plans (separable search)
       cheapest > budget → OVER_BUDGET: cheapest total + built alternatives + raise-budget offer
  6. quality search      k* cities first → plans within 120 min of the best transit time → best quality score
                         that fits the budget (built NEAR the budget, not the cheapest)
  7. finalize            transfers, visits, optional arrival/change-day visit if budget remains
  8. export.to_package   items + day-by-day + pricing + warnings
  9. store.save_package  persisted → {"outcome": "PACKAGE", "package": …}
```

Typical build: 0.04–0.7 s. Worst over-budget request (10 nights, alternatives search): about 2 s.

## 4. Data model

**Catalog** — read-only, in memory: airports, flights (469), hotels (49), rooms (125), availability (2,500), transfers (66),
attractions (56). The Docker bind mount is read-only; a test hashes the files to prove they are never changed.

**Package** (stored whole as JSON; the API returns the same object)

| Field | Meaning |
|---|---|
| `package_id`, `status` (`PLANNED`/`BOOKED`), `variant` | identity and state |
| `request`, `traveler`, `country`, `start_date`, `end_date` | what was asked |
| `city_plan[]` | `{city, nights, check_in, check_out}` in order |
| `pricing` | `total_inr`, `budget_inr`, `remaining_inr`, `over_budget`, breakdown by type |
| `metrics` | `avg_hotel_stars`, `transit_minutes`, `usable_ground_minutes`, `quality_score`, `budget_used_pct` |
| `items[]` | the shared trip format (flight, hotel, transfer, attraction) **plus** UI fields: `title`, `subtitle`, `icon`, `badges`, `image`, `leg`, `day`, `pinned` |
| `days[]` | one entry per date: `kind` (`ARRIVAL`/`FULL`/`CITY_CHANGE`/`LAST`), `city`, `summary`, time-ordered `events` |
| `warnings[]` | soft warnings (rushed plan, check-in time, day load, …) |
| `reservation` | `null` until confirmed, then `{number, confirmed_at}` |

**SQLite** (`/app/storage/nomadgrid.sqlite`, WAL mode)
- `packages(id PK, status, package_json, created_at, updated_at)`
- `reservations(number PK, package_id UNIQUE, snapshot_json, created_at)` — uniqueness enforced by the database.
- `inventory_used(kind, key, day, qty)` — seats per flight and rooms per night used by confirmed bookings (S2).
- `package_history(seq, package_id, package_json, created_at)` — up to 20 previous versions per package, for Undo.

## 5. The two rule engines (why there are two)

| | Builder (`engine/`) | Validator (`validator/`) |
|---|---|---|
| Job | *Construct* a package that obeys the rules | *Check* any package against every rule |
| Input | request + catalog | exported trip (shared format) + raw catalog — the same inputs the judges' checker has |
| Shares code? | uses `core/` helpers | **deliberately none** of the builder's code |
| Enforces | statement rules **and** comfort preferences | **only** the statement's rules |
| Runs | when building | after every change, before confirm, and in all tests |

If the builder has a bug, the validator disagrees and the package is refused instead of shipped. Mutation tests prove each rule fires
when exactly that rule is broken (30+ cases).

**Statement rules vs. comfort rules.** Hard checks: right city, open that weekday, not a closed date, visit inside opening hours,
no overlap, each attraction once, pickup ≥ 60 min after landing, reach the airport ≥ 180 min before departure, service windows,
timetable grid, seats, room fit, availability every night, prices. Comfort (suggestions only, never for user edits or the
validator): 08:30–21:30 day window, 30-min gaps, 30-min settling time, 15-min airport cushion, earliest intercity departure 08:00.

## 6. How the best package is chosen

1. **Constraints first** — only packages that satisfy every hard rule **and** the budget are eligible.
2. **City count by time available** — `k* = clamp(⌊nights/3⌋, 1, #cities)`; fall back to `k*−1`, then `k*+1` with a warning.
3. **Time-equal band** — plans whose flight + city-transfer minutes are within 120 min of the best count as equal on time.
4. **Quality score (0–100)** among those, within budget:

| Component | Points | Scored from |
|---|---:|---|
| Stay | 40 | stars (28) · family-friendly share of nights (6) · guest rating (6) |
| Flights | 20 | direct legs (5 each) · lands 06:00–20:00 (5) · returns 08:00–20:00 (5) |
| Experience | 15 | attraction coverage (9) · category variety (3) · child-friendly share (3) |
| Time | 15 | transit minutes vs. the best/worst candidate (9) · usable sightseeing minutes (6) |
| Budget fit | 10 | 0 at ≤ 50% of budget used, full from 90% to 100% |

5. **Pareto pruning** — per city only hotel options not dominated on (price, stay points) are searched. Without it, the budget-fit bonus lets a
   pricier *and worse* hotel win. Within the kept options the search is exhaustive.
6. **Cheapest search is exact** — verified against a brute-force oracle on 442 plan contexts (0 mismatches).

## 7. Changing a package

```
load stored package ─► rebuild editable Itinerary ─► apply one edit ─► recompute what depends on it
      (airport transfer for the new area/flight; arrival-day visits shifted or flagged)
  ─► validate whole package (independent validator) ─► check budget ─► persist
```

| Outcome | Meaning |
|---|---|
| `APPLIED` | new package, `price_delta_inr`, `summary`, `changed_item_ids`, warnings |
| `REFUSED` | a hard rule would break; plain `reason` + `suggestion`; package unchanged |
| `BUDGET_EXCEEDED` | legal but over budget; nothing applied until the traveler resends with `raise_budget: true`; cheaper options included |
| `PINNED_CONFLICT` | something the traveler chose can't be kept; the traveler decides (`remove_pinned_conflicts: true` to accept) |

**User priority:** anything the traveler picks is `pinned` and is never dropped silently. A `BOOKED` package is locked.

## 8. Confirm and reservations

`store.confirm` runs in one `BEGIN IMMEDIATE` transaction: return the existing reservation if there is one (idempotent), otherwise
generate a random 10-digit number (first digit 1–9), check uniqueness, write the reservation and the `BOOKED` package together.
24 concurrent confirms of one package yield one number; 60 different packages yield 60 different numbers. The validator runs before booking.
Any wrong or malformed number → `404 RESERVATION_NOT_FOUND`.

## 9. Errors

Every error uses one shape: `{"error": {"code", "message", …}}`. Validation → 422 with `fields[]`; unknown id/number → 404; wrong
method → 405; unexpected failure → 500 `INTERNAL_ERROR` with no stack trace. Impossible/over-budget requests are *not* errors: they
are normal `200` outcomes (`NO_PACKAGE`, `OVER_BUDGET`) with an explanation.

## 10. Configuration

Environment variables: `DATA_DIR`, `IMAGES_DIR`, `DB_PATH`, `FRONTEND_DIST`, `HOST`, `PORT` (and `API_TARGET` for the Vite dev server). Planning constants (60/180-minute rules, comfort window,
time tolerance) are in `backend/app/config.py`. No secrets exist anywhere.

## 11. Deployment

**One Dockerfile, one image** (`python:3.12-slim`, non-root). Stage 1 builds the React app (`npm ci`, falling back to `npm install`; `--build-arg WITH_UI=false`
skips it for an API-only image); the runtime stage holds the backend, the catalog and photos (root-owned, so the app can never change them) and the
built UI. FastAPI serves `/api/*`, `/images/*`, the UI and, for client-side routes, `index.html`. `docker-compose.yml` runs it read-only with a tmpfs `/tmp`
and keeps SQLite on the named volume `nomadgrid-db`. Health check: `GET /api/health`. Verified: build, confirm, container restart, lookup, UI served.

**Fallbacks:** no built UI → `/` shows a page saying how to build it and the API keeps working; unwritable database folder → a temporary database with a
warning; missing catalog → an error that names `DATA_DIR`; no Docker → `scripts/start.*`.

**Live editing:** `docker-compose.dev.yml` uses two extra Dockerfile stages (`ui-dev`, `api-dev`), mounts `frontend/` and `backend/app/`, and polls for
changes, so saving a file reloads the API (uvicorn `--reload`) or hot-updates the UI (Vite) without a rebuild.

## 12. Quality gates

| Gate | Result |
|---|---|
| Tests | 435 backend tests passing (Python 3.14 locally, 3.12 in the container): unit, golden Menon, 30+ validator mutations, ~120 API attacks, change/edge cases, seeded fuzz |
| Browser | `e2e/ui_flow.py`: 30 steps through the real UI (Edge), failing on any console or server error |
| Type checking | pyright: 0 errors |
| Lint | ruff: clean |
| Fuzz | ~9,000 random requests: 0 crashes, 0 validator failures, 0 over-budget packages |
| Oracle | cheapest search = brute force on 442 plan contexts |
| Break-it sessions | every bug found was fixed with a regression test or a browser step ([log](break-it-log.md)) |

## 13. Decisions worth remembering

| Decision | Why |
|---|---|
| Independent validator on the export format | A shared bug can't hide; it mirrors the judges' checker |
| Both flight items carry the **arrival city** | The data dictionary says exactly that |
| Statement rules ≠ comfort rules | The validator must never reject what the judges accept |
| Out-of-window dates → `NO_PACKAGE`, not a field error | Data dictionary: "a request outside the window has no package: say so" |
| Default package built near the budget | A ₹4 lakh budget should not return a ₹2 lakh minimum package |
| Direct window arithmetic instead of minute scans | 3× faster over-budget search, proven equivalent by a property test |
| One container, SQLite | One command to start; state survives restarts |

## 14. The extra features and how they work

| Feature | Where | How |
|---|---|---|
| **G4 package variants** | `engine/variants.py` | *Cheapest*: the exact minimum across all plans. *Best rated*: per plan, the most hotel star-nights within budget (Pareto on price vs stars), then the best plan; guest rating is ignored. Best-rated uses two attractions a day when the budget allows. |
| **G3 change cities** | `engine/variants.py`, `changes/service.py` | `plan_options` scores every valid plan (best quality that fits, else cheapest) so an option's price equals what applying it gives. `CHANGE_CITY_PLAN` rebuilds the package for that plan, then **carries over the traveler's pinned hotels, flights and attractions** by re-applying them with the normal change rules; whatever can't carry over raises `PINNED_CONFLICT` instead of vanishing. |
| **S2 seats and rooms used up** | `store/db.py` | `confirm` runs in one `BEGIN IMMEDIATE` transaction: check seats and room-nights against catalog minus `inventory_used`, record the usage, write the reservation. The app's `Inventory` view (catalog minus usage) feeds every build, option list and change, so later travelers never see seats that are gone. |
| **S1 quick request** | `quickparse/parser.py` | Regular expressions and word lists only. Fields are claimed in a fixed order (budget, date, nights, adults, children, cities) and each matched text is blanked so no number is read twice. Unknowns are reported, never guessed; assumptions become `notes`. |
| **S3 why this plan** | `export/rationale.py` | Sentences generated from the itinerary (cities vs nights, travel time, flights, safety margins actually achieved, rooms for the party, stars, budget used, sights, interest matches, what the traveler chose). The UI adds a "rule and trade-off check" worked out from the package. |
| **Interest tags** | `interests.py`, `engine/attractions.py` | A tag matches an attraction by category or a whole-word keyword in its name/aliases. Ranking order for suggested sights: child suitability, then interest match, then variety, then price, so interests never break an opening-hour, overlap or budget rule. Matching sights are marked (`MATCHES_INTEREST`) and listed first when adding a sight. |
| **Pocket city guide / nearby dining** | `content/`, `api/routes/content.py` | Two static JSON files outside `data/catalog/`; dining is looked up by the hotel's city and area, labelled as an estimate and never added to the total or the export. |
| **Journey route** | `export/route.py` | Built from the itinerary on every package, so it always matches the current plan (variant switch, any change). Carries coordinates for drawing. |
| **Undo** | `store/db.py`, `routes.py` | Every applied change first saves the previous version; `undo` pops it (20 deep, survives restarts, cleared on booking). |
| **G1 knock-on** | `changes/service.py` | After a change, old and new transfers are compared and sentences describe what moved ("Your airport pickup on arrival moves from … to …"), on top of the shifted-visit and check-in warnings. |
