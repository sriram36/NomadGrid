# NomadGrid — Build My Holiday

Enter a trip (departure city, country, first day, nights, travelers, budget) and get one complete,
rule-correct holiday package: flights, hotels, airport and city transfers and a day-by-day attraction plan.
Change the hotel, a flight or the attractions; confirm to get a 10-digit reservation number.

## Start

```
docker compose up --build        # app on http://localhost:8000  (API docs at /docs)
```

Without Docker (Python 3.12+):

```
pip install -r backend/requirements.txt
cd backend && python -m app      # API on http://localhost:8000
```

Tests: `cd backend && python -m pytest`

## Architecture

```
React frontend (frontend/, built into the same container)
        │  /api/*
FastAPI  ──  api/ (routes, request validation)
        ├─ engine/    city plans · flights · hotels · transfers · attractions · builder · alternatives
        ├─ changes/   change hotel / flight, add / remove attractions, options with price differences
        ├─ validator/ independent rule checker (works only from the exported trip + raw catalog)
        ├─ export/    package object and the shared trip-format JSON
        ├─ store/     SQLite: packages and reservations (survive restarts)
        └─ catalog/   read-only data/catalog/*.json
```
The backend holds all logic; the frontend only calls the API. The data files are never modified.

## Our city rule
A plan is an ordered list of distinct cities of the chosen country, each ≥ 2 nights, nights summing to the trip
length, consecutive cities linked. The first city must be served by an arrival airport with a valid flight and the
last city by a return airport with a valid flight. The default package keeps the budget first, then prefers about one
city per 3 nights, treats plans within 120 minutes of the best transit time as equal, then picks the best quality
(stars, family fit, direct flights, attractions, time) that fits — built near the budget, not the cheapest.

## Finished
Must-have: M1 request validation, M2 build + reasons, M3 all rules (+ independent validator), M4 day plan,
M5 total/budget/export, M6 change hotel / flight / attractions (price differences included), M7 confirm + lookup
(survives restart, "not found"), M8 budget too small (cheapest total, built alternatives, raise budget).
Also: G2 price difference on every option, G1 warnings (shifted arrivals, check-in time, day load).

## Known limitations
G3 change cities, G4 three packages, S1, S2 and S3 are not built yet. Docker has not been cold-start tested yet.
See `docs/break-it-log.md` for what was attacked and what broke.
