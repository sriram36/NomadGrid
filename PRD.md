# PRD — NomadGrid "Build My Holiday"

| | |
|---|---|
| **Product** | NomadGrid — Build My Holiday (Hackathon Problem 1) |
| **Status** | Draft v1 — for team review |
| **Team / time box** | 2 people, ~9–10 hours build, 12-minute demo |
| **Source of truth** | `problem-1-holiday-package.md`, `DATA_DICTIONARY.md`, `data/catalog/*` (read-only) |

---

## 1. Summary

A traveler enters a trip request (departure city, destination country, start date, nights, adults, children's ages, budget). The app **chooses the cities** and builds **one complete, rule-correct holiday package**: flights, hotels, airport transfers, city-to-city transfers, and a day-by-day attraction plan, priced in INR. The traveler can change a hotel, a flight, or attractions; every change re-validates the whole package. On confirm they get a **10-digit reservation number** that reopens the summary later (also after a backend restart).

**The one principle that drives everything:** *a package that breaks one rule is wrong, even if it looks good.* Correctness beats features. One verified package is worth more than three broken ones.

## 2. Goals, non-goals, success criteria

### Goals
1. Every package the app emits passes every rule in problem §4 — for any valid request, not just the Menon family.
2. Honest failure: invalid input, no possible package, and "possible but over budget" each get a distinct, clear, helpful message.
3. Changes never leave the package in an invalid state — they succeed (re-priced) or are refused with a reason.
4. Reservations persist and are retrievable by number.
5. Clean enough code that both teammates can explain every part and make a small live change (20% of the score).

### Non-goals (this build)
- Real payments, user accounts/login, real inventory booking, deployment online.
- Calling any AI/LLM at runtime (forbidden). AI coding assistants are allowed for development.
- Modifying anything under `data/`.
- Currency conversion (everything is INR).

### Success criteria
| # | Criterion | How we know |
|---|---|---|
| SC1 | Menon request builds a valid package within ₹3,50,000 | Golden test + independent validator passes |
| SC2 | Fuzzed requests (all 4 departure cities × 2 countries × start dates × nights 3–10 × traveler mixes) produce **zero** validator failures | Fuzz test in CI/local |
| SC3 | Out-of-window / impossible / over-budget / malformed requests each return the correct message class | Table-driven tests |
| SC4 | Confirm → restart backend → lookup by number returns the full package | Manual + automated test |
| SC5 | Exported JSON follows the shared trip format and passes our own checker | Export test |

## 3. Users & scenario

**Primary persona — the family planner (Menon family):** first-time international traveler from Bengaluru, wants a ready-made, trustworthy package, wants to tweak hotel/flights/sights, and wants a booking reference to come back to.

**Secondary — the hackathon judge:** enters unseen requests (other cities, UAE, other dates, odd traveler mixes, tiny budgets), loads our exported JSON into a rule checker, asks "why" about code, requests one small live change.

**Golden scenario:** BLR → Japan, 10 Apr 2027 (Saturday), 6 nights (return Fri 16 Apr), 2 adults + 1 child (6), budget ₹3,50,000.
Data facts for this scenario: arrival options are `FL-401` (NRT, 9 seats), `FL-405` (NRT), `FL-740` (KIX); `FL-403` (HND) is **unusable** (2 seats left < 3 travelers). Return options on 16 Apr are `FL-412` (HND → last city must be Tokyo) and `FL-411` (KIX → last city Osaka or Kyoto).

---

## 4. Feature scope at a glance

| Tier | Features | Rule |
|---|---|---|
| **Core (must ship, must be correct)** | Request form + validation · city planner · package builder · rules engine · day-by-day plan · totals/budget · JSON export · change hotel/flight/attractions · confirm + reservation lookup · budget-too-small handling | Nothing from lower tiers starts until all of Core works end-to-end |
| **Stretch** | Cascading-change fixes/warnings · price diff per option · change cities · three packages (cheapest/fastest/best-rated) · quick plain-text request · booking consumes seats/rooms · own idea | Built in priority order below, only after Core is solid |
| **Future** | Beyond the event — see §10 | Not built now |

---

## 5. Functional requirements

IDs map to the problem statement (M = Must, G = Good-to-have, S = Stretch). "FR-x" are our own supporting requirements.

### 5.1 CORE features

#### M1 — Request form & validation
| Field | Validation → message |
|---|---|
| Departure city | Dropdown from `destinations.json` `departure_cities` (Bengaluru, Delhi, Mumbai, Chennai) |
| Destination country | Dropdown from `countries[].name` (Japan, United Arab Emirates) |
| Start date | Valid date; first night ≥ 2027-04-01 |
| Nights | Integer 3–10; return day = start + nights ≤ 2027-04-20 |
| Adults | Integer ≥ 1 |
| Children's ages | List of integers 0–17 (count = number of children) |
| Budget | Positive integer INR |

- Validation runs on the **backend** (frontend mirrors for UX). Each error names the field and the allowed range, e.g. "Nights must be between 3 and 10", "Return date 22 Apr 2027 is after the last available flight date (20 Apr 2027)".
- Dropdown values are served by `GET /api/meta` (frontend never reads catalog files).
- Child = age 0–17; adults = everyone else. Total travelers = adults + children.

#### M2 — Build one package (incl. city planning)
The app chooses the city plan, flights, hotels, transfers, and attractions.

**City plan rule (documented in README, "our city rule"):**
- Candidate plans = ordered sequences of distinct cities from the chosen country, each with ≥ 2 nights, nights summing to N, consecutive cities connected by a `link`.
- A plan has k cities, 1 ≤ k ≤ min(#cities, ⌊N/2⌋). E.g., 3 nights → single city only; 6 nights in Japan → 1, 2 or 3 cities.
- Enumerate **all** such plans (small space: Japan ≤ 3 cities, UAE ≤ 2) and keep every plan that yields a fully valid package.
- First city must be served by an airport with a valid arrival flight; last city by an airport with a valid return flight.

**Default package selection:** the **cheapest valid** package across all plans (deterministic, most likely within budget). G4 adds the other two objectives.

**Search structure (keeps it fast and correct):** for each plan × arrival flight × return flight → pick per city the cheapest feasible hotel+room (rooms fit, availability on every night); the first and last city's hotel choice is coupled to the airport transfer (area, service hours); middle cities are independent; then schedule transfers and attractions. Discard any combination where a step is infeasible.

**Failure reporting:** track *which stage eliminated candidates* (no flight on that date / seats < travelers / no airport-city match / no room fits or none available on all nights / no transfer in service hours / not enough open attractions for the full days). When nothing builds, report the **furthest stage reached** as the reason, in plain words.

#### M3 — Rules are respected
Every rule in problem §4 is enforced **by construction in the builder and re-checked by an independent validator** (see FR-V). Rule checklist:

| Area | Rule |
|---|---|
| Dates | 3–10 nights; first night ≥ 1 Apr; return ≤ 20 Apr |
| Cities | All in chosen country; each ≥ 2 consecutive nights; each appears once |
| Flights | 1 arrival (lands on start date, local; airport serves first city), 1 return (departs on last day, local; airport serves last city); `seats_left ≥ travelers` (children included) |
| Airport transfers | Arrival: pickup ≥ landing + 60 min. Return: reach airport ≥ 180 min before departure. Transfer matches airport + hotel city + (hotel area or `area: null`). Pickup time inside service window (windows may end `24:00` or run past midnight; both ends inclusive) |
| City transfers | One per city-change day, matching `from_city`→`to_city`, departure in service window (and on the `frequency_minutes` grid for trains/buses) |
| Hotels | One hotel per night; none on last day; one hotel + one room type per city; `k` rooms satisfy `adults ≤ k·max_adults`, `adults+children ≤ k·(max_adults+max_children)`, `adults ≥ k`; `rooms_left ≥ k` every night |
| Attractions | City = that night's hotel city; open that weekday; not in `closed_dates`; whole visit inside opening hours; no overlaps in a day; each at most once; first package: 1–2 on every full day; arrival/city-change days optional and start after reaching the city; none on last day |
| Prices | See M5 formulas |

**Derived timing decisions (assumptions to confirm in §12):**
- Arrival pickup = earliest time ≥ max(landing+60, `service_from`) and ≤ `service_until`; hotel arrival = pickup + duration; arrival-day attractions start after hotel arrival.
- Return pickup = latest time in the service window such that pickup + duration ≤ departure − 180; pickup must be on the last day.
- City-change day: choose the earliest feasible departure on the frequency grid to maximize time in the new city; attractions that day start after arrival. City taxis to stations are not added.
- Insert a 30-minute buffer between attractions (stricter than "no overlap").

#### M4 — Day-by-day plan
- One section per day (date, weekday, city), items in time order: flight, airport transfer, city transfer, hotel check-in/check-out, attractions.
- Each item shows time(s), name, quantity (seats/rooms/vehicles/tickets), price.
- Last day: hotel check-out → transfer → return flight, no attractions.

#### M5 — Total & budget; JSON export
Prices (all INR, integers):

| Part | Price |
|---|---|
| Flight | `price_per_seat × travelers` |
| Hotel | `price_per_night × rooms × nights` |
| Transfer PER_PERSON | `adults × price + children × (child_price ?? price)` |
| Transfer PER_VEHICLE | `price × ceil(travelers / max_passengers)` |
| Attraction | `adults × price_per_person + children × (child_price ?? price_per_person)` |

- `total = Σ item prices` (exact, no rounding drift). UI shows **total, budget, and amount left or over** (clearly colored).
- **Export** (`GET /api/packages/{id}/export`): downloads one JSON file in the **shared trip format** (`DATA_DICTIONARY` §4): `trip_id`, `traveler{name, home_airport, adults, children, child_ages}`, `start_date`, `end_date`, `country`, `budget_inr`, `total_inr`, `items[]` with `item_id, type, name, city, status, catalog_id, start, end, room_id, quantity, price_inr, booking, sources:[], warnings[]`. Hotel items carry `room_id`; after confirm `status = BOOKED` and `booking.reference` = the number as a string.
- Item `quantity`: flights = travelers; hotels = rooms; PER_VEHICLE transfers = vehicles; PER_PERSON transfers and attractions = travelers.

#### M6 — Change the package
| Change | Behavior |
|---|---|
| Change hotel (in a city) | List alternatives in that city that fit the travelers and are available on every night of that stay. On selection: recompute rooms + price; if it is the first/last city, re-resolve the airport transfer for the new area (refuse if no valid transfer) |
| Change flight | List valid alternatives (arrival or return) with enough seats and correct airports. Recompute flight price, airport transfer (timing, service hours, 60/180-min rules); shift arrival-day attractions or flag conflicts |
| Add attraction | Offer attractions valid for a chosen day (city, weekday, closed dates, free time slot). Refuse with reason otherwise |
| Remove attraction | Remove; warn if a full day drops below the recommended 1 |

After **every** change: re-run the full validator, recompute total, return either the updated package or a **refusal with a specific reason** (package unchanged).

**Attraction count rule (decided — follows the problem statement literally):** "1–2 attractions on every full day" applies to the **first (system-built) package** only. User edits are not capped by count; they are checked against every other attraction rule (right city, open that weekday, not a closed date, visit fits inside hours, no overlap on that day, each attraction at most once, none on the last day). The UI shows a non-blocking warning when an edit leaves a full day with 0 or more than 2 attractions.

#### M7 — Confirm & reservation summary
- `POST /api/packages/{id}/confirm` → unique **10-digit** number (first digit non-zero, stored/returned as a string, unique index; retry on collision). Idempotent: confirming the same package returns the same number. Confirmed packages are locked from edits.
- `GET /api/reservations/{number}` → full package summary. Unknown or malformed number → **"Reservation not found"** (HTTP 404, friendly page).
- Persisted in the database; survives page refresh **and backend restart**.

#### M8 — Budget too small
When valid packages exist but all exceed the budget:
- Say so explicitly; show the **cheapest possible total** and the shortfall.
- Suggest concrete changes computed by the backend: raise budget to ₹X; fewer nights (cheapest total at N−1 if valid); fewer cities; try another start date (cheapest nearby date within the window and its total).
- Offer a one-click "Edit the trip" back to the form with the budget prefilled to the cheapest total.
- When **no** package exists at all (M2): show the reason from the failure tracker; never show a budget message in that case.

#### FR-V — Independent rule validator (core engineering requirement)
A separate module that takes a finished package + the raw catalog and re-checks **every rule in §4 from scratch** (does not reuse the builder's helper results). It is used (a) after the build, (b) after every change, (c) on export, (d) in tests. This mirrors the judges' checker and is our main safety net.

#### FR-P — Persistence
- SQLite (or equivalent file DB): tables `packages` (id, request JSON, package JSON, status, created/updated) and `reservations` (number PK, package_id, created, snapshot JSON).
- Catalog loaded read-only into memory at startup; never written. A test hashes the data files to prove they are untouched.

### 5.2 STRETCH features (priority order)

| Priority | # | Feature | Done when / notes |
|---|---|---|---|
| 1 | **G1** | Changes that affect other parts | After a change, auto-fix or warn about dependents: flight change → re-time the airport transfer and shift/drop arrival-day or last-day attractions that no longer fit; hotel change → re-check transfer area and check-in note (display only); attraction add/move → overlap and double-booking detection. Warnings appear in `warnings[]` and in the UI |
| 2 | **G2** | Price difference | Every alternative (hotel, flight, attraction) shows `+₹X / −₹X` vs. the current choice, including knock-on transfer cost changes |
| 3 | **G4** | Three packages | Cheapest (min total), **Fastest** (min Σ flight `duration_minutes` + Σ inter-city transfer `duration_minutes`; airport transfers and city taxis excluded), **Best rated** (max average hotel `stars` per night, within budget; guest `rating` ignored; ties → cheaper). Traveler picks one |
| 4 | **G3** | Change cities | UI lists all valid city plans (with total per plan); selecting one rebuilds the package |
| 5 | **S2** | Booking uses up seats and rooms | Own `inventory_used` table subtracts from catalog `seats_left` / `rooms_left`; confirm is refused (with reason) if the same last seats/rooms are gone; applies to all later builds |
| 6 | **S1** | Quick request (rule-based, no AI) | Regex/keyword parser: "Japan 10 Apr 6 nights 2 adults 1 child 6 from Bengaluru 3.5 lakh" → fills the form for review. Supports city aliases, `lakh/k/₹`, month names, "kid aged N" |
| 7 | **S3** | Own idea | Candidate: *Trip rationale* — a one-line "why this plan" per city and an "alternative cities" comparison; or *Photo credits page* using `ATTRIBUTIONS.md` (required if photos shown) |

### 5.3 Screens (frontend)

1. **Enter the trip** — form (M1), inline validation.
2. **Package view** — city plan strip, totals/budget bar, day-by-day timeline (M4/M5), change buttons, Export JSON, Confirm.
3. **Change drawer/modal** — alternatives list (+ price diffs when G2 done), refusal messages.
4. **No package / over budget** — reason, cheapest total, suggestions, "Edit the trip" (M8/M2).
5. **Reservation summary** — number lookup box + read-only summary; "not found" state (M7).
6. (Stretch) Three-package chooser (G4), city plan chooser (G3), quick-request box (S1), photo credits.

### 5.4 API surface (proposed)

| Method & path | Purpose |
|---|---|
| `GET /api/meta` | Departure cities, countries, rules (min/max nights, window) |
| `POST /api/packages` | Validate request, build package → `{package}` or `{status: "no_package"/"over_budget", reason, cheapest_total, suggestions}` |
| `GET /api/packages/{id}` | Fetch a saved package |
| `GET /api/packages/{id}/options?type=hotel&city=…` | Alternatives for a change (with diffs) |
| `POST /api/packages/{id}/changes` | Apply `{op: "change_hotel"|"change_flight"|"add_attraction"|"remove_attraction"|"change_cities", …}` → updated package or `{refused, reason}` |
| `GET /api/packages/{id}/export` | Download shared-format JSON |
| `POST /api/packages/{id}/confirm` | Create reservation number |
| `GET /api/reservations/{number}` | Reservation summary or 404 |
| `POST /api/parse-request` (S1) | Plain-text → form fields |

---

## 6. Non-functional requirements

| Category | Requirement |
|---|---|
| **Correctness** | Zero rule violations in any emitted package; independent validator (FR-V) gates every build and change; deterministic output (same request → same package) |
| **Performance** | Typical build < 2 s, worst case < 5 s on a laptop (decomposed search, no brute force over all hotel combinations); change operations < 1 s |
| **Reliability / persistence** | Packages and reservations survive refresh and backend restart; writes are transactional; confirm is idempotent; reservation numbers are unique (DB constraint) |
| **Data integrity** | Catalog is read-only; all prices, times, availability come from `data/catalog/`; hash test proves files unchanged |
| **Architecture** | Backend owns all logic (planning, rules, prices); frontend only calls the API. Rules engine is pure functions over catalog data → unit-testable without HTTP |
| **Usability** | Clear, specific error messages (no stack traces); no dead ends — every failure offers a next step; INR formatting with lakh grouping (₹3,50,000); responsive layout; keyboard-accessible controls and sufficient contrast |
| **Security** | Server-side input validation; parameterized SQL; escape all rendered text; no secrets/API keys in repo; reservation lookup accepts digits only |
| **Portability / setup** | Starts in **1 command** (`docker compose up --build`) with a documented no-Docker fallback (2 commands); works on Windows/macOS/Linux; exact commands in README; no `node_modules`, venvs, or build output in the submission zip; container runs as a non-root user; image builds from a clean checkout with no manual steps |
| **Maintainability / quality** | Modular code (catalog loader, time utils, pricing, planner, scheduler, validator, API, storage); typed models; README covers start commands, architecture, city rule, what's finished, known limitations; Git history with commits at least hourly |
| **Compliance** | No LLM/AI calls at runtime; photos (if shown) display attribution from `ATTRIBUTIONS.md`; feature code written during the event |
| **Observability** | Structured logs for each build (plans tried, stage eliminations, chosen plan); failure reasons returned to the UI |
| **Testability** | Golden Menon test, table-driven rule tests, fuzz test across request space, restart-persistence test |

---

## 7. Architecture

**Stack (decided):** Python 3.12 + FastAPI + SQLite (backend) · React + Vite (frontend) · Docker Compose (packaging and run).

| Choice | Why |
|---|---|
| Python | The hard part is the rules engine: date/time arithmetic, joins across JSON files, and search over city plans × flights × hotels. The standard library (`datetime`, `itertools`, `dataclasses`, `json`) covers it with no dependencies; readable code helps the live-explanation score; `pytest` makes fuzz tests easy. Both teammates know it |
| FastAPI | Pydantic request models give M1's clear per-field error messages almost for free; auto-generated `/docs` page documents the API contract for both teammates and the judges |
| SQLite | Single file, no server, transactional; a unique constraint guarantees unique reservation numbers; survives restarts |
| React + Vite | Good fit for a multi-step flow with change dialogs and live totals. Cost: a Node build step, handled inside Docker's multi-stage build so it never reaches the submission zip |
| Docker Compose | Satisfies "start in 1–2 commands"; identical behavior on any machine; catalog mounted read-only enforces "don't change the data files"; a named volume holds the SQLite file so restart-persistence is demonstrable with `docker compose restart` |

### 7.1 Docker & run plan

**Primary start command (README):** `docker compose up --build` → app at `http://localhost:8000`.
**Fallback (no Docker, README):** `pip install -r requirements.txt` then `python -m app` (backend) with the pre-built frontend served by FastAPI; for frontend dev: `npm install && npm run dev`.

| Item | Decision |
|---|---|
| Services | **One container**: multi-stage `Dockerfile` — stage 1 `node:24-alpine` builds the React app; stage 2 `python:3.12-slim` installs backend deps, copies the build output, and FastAPI serves both `/api/*` and the static frontend. One port, no CORS, simplest demo |
| Catalog | Bind-mounted read-only: `./hackathon-problem-1-holiday-package/data:/app/data:ro` (and `images/` for photos). Backend reads it at startup |
| Persistence | Named volume `nomadgrid-db:/app/storage` holds `nomadgrid.sqlite`; survives `docker compose restart`, `down` and `up` (not `down -v`) |
| Config | Environment variables in `docker-compose.yml` (`DATA_DIR`, `DB_PATH`, `PORT`); no secrets exist, none committed |
| Image hygiene | `.dockerignore` excludes `node_modules`, `.venv`, `__pycache__`, build output, `.git`; the **submission zip contains source + Dockerfile + compose file + README only** |
| Dev loop | `docker-compose.dev.yml` override mounts `backend/` for `uvicorn --reload` and runs Vite dev server separately |
| Healthcheck | `GET /api/health` used by Compose `healthcheck` so "app is up" is verifiable before the demo |
| Tests | `docker compose run --rm app pytest` runs the unit, fuzz and restart-persistence tests in the same image |
| Python version | Pinned to 3.12 in the image (local machine has 3.14; pin avoids dependency mismatches) |

**Docker-specific risks:** Docker Desktop must be running on the demo laptop (mitigation: fallback command, and rehearse a cold `docker compose up --build` before the demo; pre-build the image once so the demo start is fast); Windows line endings in shell scripts (mitigation: avoid shell entrypoint scripts, use `CMD ["python","-m","app"]` and a `.gitattributes` with `eol=lf`).

```
frontend (React)  ──HTTP/JSON──►  FastAPI routes
                                      │
              ┌───────────────────────┼───────────────────────┐
              ▼                       ▼                       ▼
        request validator      planner / builder          storage (SQLite)
                                 ├─ city plan generator      packages
                                 ├─ flight selector          reservations
                                 ├─ hotel/room selector      inventory_used (S2)
                                 ├─ transfer scheduler
                                 ├─ attraction scheduler
                                 └─ pricing
                                      │
                              independent rule validator (FR-V)
                                      │
                       catalog (read-only, loaded in memory)
```

**Modules & boundaries**
| Module | Responsibility | Depends on |
|---|---|---|
| `catalog` | Load/index JSON (by city, airport, date) | files only |
| `timeutil` | Parse `HH:MM` (incl. `24:00`, past-midnight windows), day-of-week, minute arithmetic; **local times only, never mix zones** | — |
| `pricing` | The five price formulas, room-fit `k` calculation | catalog |
| `planner` | City-plan enumeration, candidate search, failure tracker | all builders |
| `scheduler` | Airport/city transfer times, attraction placement | catalog, timeutil |
| `validator` | Re-check every rule from raw catalog | catalog, timeutil |
| `changes` | Option listing, apply/refuse, G1 cascades | planner pieces, validator |
| `store` | Persistence, reservation numbers, S2 inventory overlay | SQLite |
| `api` | Routes, serialization, export mapping | everything above |

**Data model (package JSON, stored whole):** `request`, `plan` (ordered `[{city, nights, check_in, check_out}]`), `items[]` (shared trip format + internal `day`, `leg`), `totals{total, budget, left}`, `warnings[]`, `status`, `reservation?`.

---

## 8. Data traps the implementation must handle

| Trap | Handling |
|---|---|
| Kyoto has no airport (served by `KIX`); `ITM` serves nothing | Always match via `airports.serves_cities`, never by airport city name |
| Arrival flights often depart the evening before (Mar 31 → Apr 1 arrival is valid) | Match arrival by **date part of `arrival_local`** |
| Local times in different zones | Use `duration_minutes`; never subtract departure/arrival |
| Service windows `24:00`, `00:30`, both ends inclusive | `timeutil` window check with minutes-since-midnight and wrap |
| `area: null` transfers (KIX→Kyoto, DXB→Abu Dhabi, AUH bus) | Match `area == hotel.area or area is null` |
| Trains/buses need a departure on the frequency grid | `service_from + n·frequency` ≤ `service_until` |
| Children need seats; `seats_left` as low as 1–2 | `seats_left ≥ adults + children` (FL-403 fails for the Menons) |
| `max_children = 0` rooms (TWIN/SINGLE/DOUBLE/TRIPLE) | Use the room-fit formula; capsule hotel (`SINGLE` only) cannot fit a family with a child |
| 61 sold-out room-nights | Check `rooms_left ≥ k` on **every night** of that city's stay; check-out day is not a night |
| Attraction closures | Edo Craft Museum is closed on every date from 10 Apr on (effectively unusable); Disneyland & Heritage Village closed 12 Apr; Museum of the Future closed 14 Apr; Tsukiji closed Wed & Sun; Global Village opens 16:00 |
| Nara attractions | Excluded (no hotels in Nara) |
| `child_price` missing or `0` | Fall back to adult price only when the field is **absent**; `0` is a real free price (e.g., Osaka Castle child) |
| Transfers between cities: door-to-door vs station-to-station | City taxis optional; if added, price them |
| Same flight number repeats on many dates | Key everything on `flight_id` |

---

## 9. Delivery plan (≈ 9–10 h, 2 people)

Split: **A = backend/rules engine**, **B = API contract + frontend + persistence**. Agree on the package JSON + API shapes in hour 0 so both work in parallel. Push to Git hourly.

| Phase | Time | A — engine | B — app | Exit check |
|---|---|---|---|---|
| 0. Setup | 0:00–0:45 | Repo, catalog loader, time utils, models | Scaffold API + frontend, `/api/meta`, form (M1); **Dockerfile (multi-stage), `docker-compose.yml`, `.dockerignore`, `/api/health`** | `docker compose up --build` serves the form; `/api/meta` feeds it; README skeleton with both start paths |
| 1. Core engine | 0:45–3:30 | Pricing + room fit, flight selector, airport transfers, hotels, intercity, city plans, attraction scheduler | Package view skeleton, timeline UI (M4), totals bar (M5) | Menon request builds a package in a test |
| 2. Validator + failures | 3:30–4:30 | Independent validator (FR-V), failure tracker (M2/M8 logic) | Persistence, export mapping, error/over-budget screens | Validator passes Menon; bad requests give right messages |
| 3. Changes + booking | 4:30–6:30 | `changes` module: options, apply/refuse (M6) | Change drawer UI, confirm, reservation page (M7) | End-to-end demo flow works incl. restart test |
| 4. Hardening | 6:30–7:30 | Fuzz tests, fix every validator failure | Polish UX, messages, INR formatting | SC2 and SC3 green |
| 5. Stretch | 7:30–9:00 | G1 → G2 → G4 (as time allows) | UI for diffs, 3-package chooser, G3/S1/S2 | Each stretch merged only if tests stay green |
| 6. Freeze | 9:00–9:45 | README (commands, architecture, city rule, done/limitations), zip check, rehearse demo | Same | Clean-machine start in ≤ 2 commands |

**Demo script (4 min):** empty form → Menon request → show package/day plan/total vs budget → change hotel → change a flight (show re-validation) → add/remove an attraction → export JSON → confirm → open reservation by number. Prepare answers for judge requests: UAE, Delhi departure, tiny budget, out-of-window dates, invalid input.

## 10. Future plans (post-hackathon roadmap)

**Near term**
- Live inventory/pricing from real supplier APIs; real booking, payments, cancellations/refunds and hold-and-expire.
- Accounts, saved trips, share a trip link, email/PDF itinerary.
- More countries, departure cities, and cabins; multi-currency and localization.

**Planning intelligence**
- Smarter optimizer (ILP/constraint solver) with user preferences: pace, interests, kids/seniors/accessibility, hotel area preferences.
- Real travel times between attractions (maps/routing) instead of fixed buffers; opening-hour crowd/season awareness; weather-aware swaps.
- Multiple room types per city, mixed rooms, check-in/out time enforcement, late-arrival handling.
- Day trips (e.g., Nara from Kyoto/Osaka), open-jaw trips, multi-stop country circuits, lowest-fare-per-day date flexibility.
- Recommendation ranking trained on traveler feedback (allowed outside the hackathon's no-AI rule).

**Platform**
- Mobile apps / offline itinerary, notifications for schedule or price changes.
- Group planning with shared edits and voting, split payments.
- Admin console for catalog management and inventory; analytics on drop-off and popular plans.
- Travel extras: visas, insurance, eSIM, airport lounges, local events.

## 11. Risks & mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Timing/window edge cases (past-midnight, 24:00, frequency grid) cause rule violations | Wrong package | Dedicated `timeutil` with unit tests; validator re-checks |
| Search blow-up across plans × flights × hotels | Slow builds | Decompose per city; prune early; cache per (city, dates, travelers) |
| Over-investing in stretch before core is right | Lost score | Hard gate: no stretch until SC1–SC5 pass |
| Builder and validator share a bug | False confidence | Validator written independently, from raw catalog; fuzz test |
| Judge inputs we didn't test (UAE, odd traveler mixes) | Lost correctness points | Fuzz across full request space; manual UAE and Delhi runs |
| Live-code-change question (20%) | Lost points | Both members implement/understand every module; small, readable functions |
| Docker fails or is slow on the demo laptop | Demo can't start | Pre-build the image; documented no-Docker fallback; rehearse a cold start before the slot |
| Edited package fails the judges' checker on attraction count | Lost correctness points | Warn in UI; ask organizers whether 1–2 per day is enforced after edits |

## 12. Open questions / assumptions to confirm

| # | Question | Default we'll use |
|---|---|---|
| Q1 | Backend/frontend stack | **Decided:** Python + FastAPI + SQLite, React + Vite, Docker Compose (one container, with no-Docker fallback) |
| Q2 | Default package when several valid | Cheapest valid (G4 adds fastest and best-rated) |
| Q3 | Attraction count after edits | **Decided:** 1–2 per full day applies to the first package only (as in the problem statement); edits are not count-capped but must satisfy all other attraction rules; UI warns on 0 or >2. Residual risk: if the judges' checker enforces 1–2 on edited packages, an edit that goes beyond 2 would fail — confirm with organizers if possible |
| Q4 | `city` for the **return flight** item | Follow the dictionary literally ("arrival city" = home city); confirm with organizers |
| Q5 | Return pickup must fall on the last day (no pre-midnight pickup the day before) | Yes — safest reading of "no hotel night on the last day" |
| Q6 | Buffer between attractions | 30 minutes (stricter than the rule) |
| Q7 | Soft-filter child-unfriendly attractions (`child_friendly: false`) when children travel | Yes, soft (prefer others, still allowed if user adds) |
| Q8 | Traveler name | Optional field, defaults to "Traveler" in the export |
| Q9 | Reservation number format | 10 digits, first digit 1–9, random, unique |
