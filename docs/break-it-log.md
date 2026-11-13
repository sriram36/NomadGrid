# Break-it log

Every failure found while trying to break the product: what was tried, what happened, the root cause,
the fix, and the regression test that now guards it. (PRD section 12.1.)

## Cycle 1 — backend core (build, validate, change, confirm)

| # | Area | What I tried | What happened | Root cause | Fix | Regression test |
|---|---|---|---|---|---|---|
| 1 | Build API | First end-to-end smoke through HTTP | `POST /api/packages` crashed with 500 on save | Items carried a `date` object in `day`, which JSON cannot store | Convert to ISO string when items are built | every API test that builds a package |
| 2 | Routing | `GET /api/reservations/..%2F..%2Fetc`, `GET /api/packages/..%2F..%2Fx` | Framework default `{"detail":"Not Found"}`, not our error shape; M7 needs "not found" for ANY wrong number | Encoded slash stops the `{number}` route from matching | Reservation route accepts any path text and rejects it with our `RESERVATION_NOT_FOUND`; one handler gives every other 404/405 our error shape | `test_wrong_reservation_numbers_show_not_found`, `test_unknown_package_is_a_clean_404`, `test_odd_urls_and_methods_get_our_error_format` |
| 3 | Performance | Over-budget request, 10 nights Japan (alternatives search) | Up to **5.5 s** | `departure_pickup` scanned minute by minute: 1.2 M `in_window_dt` calls, 85% of the time | Direct earliest/latest-in-window calculation | `test_window_search_equivalence` (400 random windows vs the old scan) + edge tests; worst case now 2.0 s, normal builds < 0.7 s |
| 4 | Input | Start date `9999-12-31` with 10 nights | **500** (`OverflowError`) | `start + nights` left Python's date range | `end_date` clamps to `date.max`, so the window check answers `OUT_OF_WINDOW` | `test_start_date_at_the_end_of_the_calendar_is_out_of_window_not_a_500` |

### Attacks that did NOT break anything (and are now tests)
- ~60 invalid field values (wrong types, ranges, NaN/Infinity, huge numbers, unicode, SQL/HTML strings) → clean per-field 422.
- Window boundaries (31 Mar, 20 Apr, 3 and 10 nights), 12 and 40 travelers, impossible dates → correct `NO_PACKAGE` reason.
- Budget edges: budget = cheapest total passes, cheapest − 1 is `OVER_BUDGET`; no package ever exceeds the budget.
- Confirm twice, 24 concurrent confirms of one package (one number), 60 distinct reservations (60 distinct 10-digit numbers), restart persistence, corrupted DB row (clean 500, no stack trace), data files untouched.
- 30+ validator mutations (shift a flight, change a price by ₹1, wrong room, remove a transfer, closed attraction, overlap, duplicate, last-day visit …): each caught by exactly the expected rule.
- Brute-force oracle over 442 plan contexts: the cheapest search matched exhaustive search every time.
- ~9,000 fuzzed requests (seeded fuzz in the suite + larger ad-hoc sweeps): 0 crashes, 0 validator failures, 0 over-budget packages.

### Findings that are design decisions, not bugs
- **Budget-fit bonus vs. pruning.** Without pruning, the "uses your budget" bonus lets a *pricier, lower-quality* hotel beat a cheaper, better one (up to 6 score points). Dominated hotels are therefore pruned per city; the quality search is exhaustive over the remaining options.
- **Some "no package" answers are correct but surprising.** 3-night trips allow one city only, so arriving at KIX and leaving from HND has no valid plan. A 10-night Abu Dhabi-only plan needs 9 distinct attractions but the city has 7.
- **Menon default is Osaka (4) + Kyoto (2) via KIX, not Tokyo.** It scores highest under the current quality weights (direct flights, early landing, 5-star family rooms). The score has no "destination appeal" term; Tokyo plans are one change-cities click away (G3, not built yet). Worth a product decision.

### Static analysis pass
- pyright reported 74 type errors (None reaching places that need a value) and ruff 36 findings (unused imports/variables, `zip` strictness, loop variables, `raise from`). All fixed with no behaviour change: now **0 type errors, ruff clean, 255 tests passing**.
- `backend/pyrightconfig.json`, `backend/ruff.toml` and `.vscode/settings.json` point the editor at `backend/.venv` so imports resolve.

### Lessons
- Do not name scratch scripts after standard-library modules (`inspect.py` shadowed `inspect` and broke `dataclasses`).
- Windows consoles cannot print `→`/`·`; set `PYTHONIOENCODING=utf-8` for probes (the API itself is UTF-8 clean).

### Open
- `docker compose up --build` has **not** been run: Docker Desktop was not running on this machine. Needs a cold-start check (PRD X1).
- Not built yet: G3 change cities, G4 three packages, S1 quick request, S2 seat/room consumption, S3.
