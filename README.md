# NomadGrid — Build My Holiday

Enter a trip — departure city, destination country, first day, nights, adults, children's ages and a budget — and get **one complete,
rule-correct holiday package**: flights, hotels, airport and city transfers, and a day-by-day plan of attractions, priced in INR.
Change the hotel, a flight, the attractions or even the **city plan** and the whole package is re-checked. Compare the **cheapest and
best-rated** packages (the API can also read a trip typed in plain words; the UI no longer shows that box). Confirm to get a **10-digit reservation number** that reopens the summary
later, even after a restart — and booking really **uses up seats and rooms**, so the last seat can't be sold twice.

> Hackathon "Problem 1 — Holiday Package". The problem statement is the contract; every must-have, good-to-have and stretch feature is built and verified
> (the *fastest* variant of G4 was dropped on purpose). On top of that: interest tags, a pocket city guide, nearby dining, a journey route box, photos with credits.

## Start it

```
docker compose up --build          # http://localhost:8000      API docs: http://localhost:8000/docs
docker compose -f docker-compose.dev.yml up --build   # live editing: UI http://localhost:5173, API :8000, both reload on save
```

Without Docker: `scripts/start.sh` (macOS/Linux/git-bash), `scripts/start.ps1` or `scripts/start.bat` (Windows). They create a virtualenv, install the backend,
build the UI if Node.js is present (otherwise the API runs alone and `/` explains how to build it) and start everything on http://localhost:8000.
By hand (Python 3.12+): `pip install -r backend/requirements.txt && cd backend && python -m app`.

Try the Menon family: Bengaluru → Japan · 10 Apr 2027 · 6 nights · 2 adults + 1 child (6) · ₹3,50,000
```
curl -X POST localhost:8000/api/packages -H "content-type: application/json" \
  -d '{"departure_city":"Bengaluru","country":"Japan","start_date":"2027-04-10","nights":6,"adults":2,"child_ages":[6],"budget_inr":350000}'

curl -X POST localhost:8000/api/parse-request -H "content-type: application/json" \
  -d '{"text":"Japan 10 Apr 6 nights 2 adults 1 child 6 from Bengaluru 3.5 lakh"}'
```

## What it does — every statement item

| Statement item | Status |
|---|---|
| **M1** Request form with the 7 fields, clear message for every invalid value | ✅ per-field errors |
| **M2** Builds one package; the app chooses the cities; says why when none is possible | ✅ 10 specific reasons |
| **M3** Every travel rule respected | ✅ built in, and re-checked by an independent validator |
| **M4** Day-by-day plan in time order | ✅ `days[]` with sorted events |
| **M5** Total, budget, amount left or over; export as shared-format JSON | ✅ |
| **M6** Change hotel, change flight, add/remove attractions — re-checked or refused with a reason | ✅ |
| **M7** Confirm → unique 10-digit number → summary, survives restart, wrong number = "not found" | ✅ verified inside Docker |
| **M8** Budget too small → say so, show the cheapest total, suggest a change | ✅ plus ready-built alternatives and a raise-budget offer |
| **G1** A change fixes or warns about what else it affects | ✅ shifted arrival visits, moved airport pickups ("knock-on" notes), check-in times, day-load warnings |
| **G2** Price difference on every change option | ✅ `price_delta_inr` on every option |
| **G3** Choose another city plan; the app rebuilds | ✅ compare every valid plan, switch with one call; your own picks are kept |
| **G4** Package variants: cheapest and best rated | ✅ plus the recommended one; you pick (the *fastest* variant was dropped on purpose) |
| **S1** Plain-words request read with rules (no AI) | ✅ understands dates, lakhs, ages, city aliases; says what is missing |
| **S2** Booking uses up seats and rooms in our own store | ✅ atomic; a taken last seat or room gives a clear refusal |
| **S3** Own idea | ✅ "Why this plan" — a plain-language explanation on every package, plus **Undo** for the last change |
| *Own extra* **Interest tags** | ✅ optional tags (History & Culture, Nature, Family, Art, Food & Markets, Views & Adventure); fixed keyword rules prefer matching sights, never at the cost of a rule; also read from the plain-words request |
| *Own extra* **Pocket city guide** | ✅ read-only drawer per city: getting around, etiquette, sightseeing tips (separate static file, not in the catalog or the export) |
| *Own extra* **Nearby dining** | ✅ 3–4 spots per hotel area with dietary tags and estimated prices, clearly **not** in the package total (illustrative data) |
| *Own extra* **Journey box** | ✅ departure hub → cities in order → home, with each leg's mode and duration; redrawn on every change or variant switch |
| *Own extra* **Photos and credits** | ✅ hotel and sight photos from the data pack, with a Photo credits page (required by the pack's licence) |

## How it decides

- **Budget first.** A package is shown only if it passes every rule *and* fits the budget. If the trip can't be done as asked, the app says so,
  shows the cheapest total, offers fully built alternatives (drop a city, fewer nights, shift the date) and an "increase budget" option.
- **Built near the budget.** A ₹4 lakh budget gets a ~₹3.6–4 lakh holiday (better hotels, direct flights, two sights a day), not the cheapest one.
- **Our city rule.** A plan is an ordered list of distinct cities of the country, each at least 2 nights, nights adding up, consecutive cities linked;
  the first city must be served by an arrival airport with a valid flight and the last by a return airport with a valid flight. We prefer about one
  city per 3 nights, treat plans within 120 minutes of the best transit time as equal, then pick the best quality (stars, family fit, direct flights,
  sights, time) that fits the budget.
- **Your choices win.** Anything the traveler picks is never dropped silently — including when switching city plans; conflicts are explained and the traveler decides.
- **Package variants.** *Cheapest* = lowest total. *Best rated* = highest average hotel stars per night within budget (guest rating ignored).

## The API (19 endpoints)

`GET /api/meta` · `POST /api/packages` · `POST /api/packages/variants` · `POST /api/parse-request` · `GET /api/packages/{id}` ·
`GET …/options/hotels|flights|attractions|city-plans` · `POST …/changes` · `POST …/undo` · `GET …/export` · `POST …/confirm` ·
`GET /api/reservations/{number}` · `GET /api/cities/{city}/guide` · `GET /api/cities/{city}/restaurants` · `GET …/guides` · `GET …/dining` · `GET /api/health` — details in [docs/API.md](docs/API.md), real responses in [docs/api-examples/](docs/api-examples).

## Project layout

```
backend/            FastAPI app (api · engine · changes · validator · export · store · quickparse · catalog · content · core), tests, scripts
frontend/           the React UI (built into the same container; wired to the API)
e2e/                a real-browser test of the whole journey (Playwright + Edge)
scripts/            start.sh · start.ps1 · start.bat (run without Docker)
docs/               ARCHITECTURE.md · API.md · FRONTEND_HANDOFF.md · break-it-log.md · api-examples/
hackathon-problem-1-holiday-package/   the provided statement, data dictionary, catalog and photos (read-only)
docs/PRD.md          product requirements, rules and decisions
Dockerfile · docker-compose.yml (production) · docker-compose.dev.yml (live editing with auto-reload)
```

## Documentation

| Document | For |
|---|---|
| [PRD.md](docs/PRD.md) | What we build and why; requirements, decisions, delivery status |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | How it works: modules, data, the search, the two rule engines, changes, extras, deployment |
| [docs/API.md](docs/API.md) | Every endpoint, outcome and error code |
| [docs/FRONTEND_HANDOFF.md](docs/FRONTEND_HANDOFF.md) | How to build the UI against this API |
| [docs/api-examples/](docs/api-examples) | 33 real responses (generated by `backend/scripts/generate_api_examples.py`) |
| [docs/break-it-log.md](docs/break-it-log.md) | What we attacked, what broke, how it was fixed |

## Develop and test

```
pip install -r backend/requirements-dev.txt
cd backend
python -m pytest        # 434 tests
ruff check .            # lint: clean
pyright                 # types: 0 errors
python scripts/generate_api_examples.py    # refresh docs/api-examples
```
Browser test (app running on :8000): `python e2e/ui_flow.py http://localhost:8000` — 30 steps, fails on any console or server error.
Editor setup is in `.vscode/settings.json` (uses `backend/.venv`). Commit messages are short, plain descriptions.

## Quality

434 backend tests (unit, the Menon golden case, 30+ validator mutations, ~120 API attacks, change and edge cases, seeded fuzz for every feature) plus a 30-step real-browser test ·
0 type errors · lint clean · the full suite passes on Python 3.12 and 3.14 · ~9,000 fuzzed requests with 0 crashes and 0 validator failures ·
the cheapest search matches a brute-force oracle · every city-plan option applies at exactly its promised price · a simulated stream of 70 bookings
never oversold a seat or room · Docker verified (build, confirm, container restart, lookup, UI served) · the catalog is baked into the image read-only and never modified.
About 4,300 lines of application code and 2,200 lines of tests.

## Known limitations

- The API serves the built UI itself; if the UI has not been built, `/` shows a page that says how to build it and the API keeps working.
- Options (hotels, flights, city plans) describe the package *as it is now* — fetch them again after every change.
- The quick-request reader uses fixed rules, so unusual phrasings are reported as "missing" rather than guessed; a bare number after "kids" is flagged for the traveler to check.
- The default plan favours the highest quality score, so the Menon family gets Osaka + Kyoto (direct flights, early landing, family rooms); switching to Tokyo is one city-plan change.
- Photos are served from `/images` and shown in the UI with a Photo credits page. Hotel photos are generic room photos (the hotels are fictional).
- The nearby-dining spots are illustrative names with estimated prices, and the city guides are general tips written for this project, not live-checked: verify before travelling.
- The *fastest* variant of G4 is not offered (decision); *cheapest*, *best rated* and *recommended* are.
- All data is synthetic and covers 1–20 April 2027 only; requests outside that window correctly return "no package".
