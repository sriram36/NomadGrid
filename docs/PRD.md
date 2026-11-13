# PRD — NomadGrid "Build My Holiday"

| | |
|---|---|
| **Product** | NomadGrid — Build My Holiday (Hackathon Problem 1) |
| **Version** | v4 — everything delivered and verified: Must-have, Good-to-have and Stretch (status in §0) |
| **Team** | 2 people · ~9–10 h build · 12-minute demo |
| **Backend owner** | **You** (with Claude's help) — rules engine, API, persistence, Docker |
| **Frontend owner** | **Teammate** — UI that talks only to the backend API (see §8) |
| **Source of truth** | `problem-1-holiday-package.md`, `DATA_DICTIONARY.md`, `data/catalog/*` (read-only). `holiday_package_problem1_full_text.md` is a text transcription of the same problem PDF |

**Tags used below:** **[BE]** backend task · **[FE]** frontend task · **[BOTH]** shared.

> **Rule zero — the problem statement is the contract.** We do not edit, reinterpret, shrink or skip anything in it. Every Must-have (M1–M8) and every travel rule (problem §4) is **compulsory** and is built first. Good-to-have and Stretch come only after. Anything we add (alternatives, raise-budget, warnings, undo) is *additive*: it never replaces or weakens a behavior the statement requires. See the traceability matrix in §3A.

---

## 0. Delivery status (wrap-up)

**Delivered and verified:** every Must-have (M1–M8), every Good-to-have (G1–G4), every Stretch feature (S1–S3), plus Undo; the independent validator (FR-V),
persistence (FR-P), JSON export, the budget-first flow, Docker packaging and the backend half of the API contract.

| Requirement | Status | How it was verified |
|---|---|---|
| M1 Request form (7 fields, clear messages) | ✅ Built (API validation; UI is the frontend's) | ~60 invalid-value attacks → per-field 422 |
| M2 Build one package, app chooses cities, explains failures | ✅ | ~9,000 fuzzed requests; 10 failure reasons checked |
| M3 Every rule respected | ✅ | Independent validator on every package; 30+ mutation tests |
| M4 Day-by-day plan in time order | ✅ `days[]` | golden Menon test |
| M5 Total, budget, left/over, JSON export | ✅ | export re-validated; booked export carries the reference |
| M6 Change hotel / flight / attractions | ✅ | every listed option applied or explained; refusal and budget cases |
| M7 Confirm, 10-digit number, summary, restart, "not found" | ✅ | verified inside Docker across a container restart |
| M8 Budget too small | ✅ cheapest total + built alternatives + raise-budget | alternatives re-validated and within budget |
| FR-V Independent validator · FR-P Persistence | ✅ | mutation suite; restart tests (app and container) |
| Docker (1-command start) | ✅ non-root, read-only catalog | cold build + health + restart |
| **G1** Changes that affect other parts | ✅ shifted visits, moved airport pickups ("knock-on"), check-in time, day-load warnings | change and edge tests |
| **G2** Price difference on every option | ✅ `price_delta_inr` | option tests |
| **G3** Change cities | ✅ options for every valid plan, `CHANGE_CITY_PLAN`, the traveler's picks kept | every option applies at exactly its promised price (fuzz) |
| **G4** Three packages | ✅ cheapest / best rated (+ recommended); *fastest dropped by decision* | each wins at its promise; all valid and within budget (fuzz) |
| **S1** Quick request | ✅ rules only, reports what is missing | 60+ phrasings, hostile text, no slow regex |
| **S2** Booking uses up seats and rooms | ✅ atomic in the database | 8-way race → exactly one winner; 70-booking stream never oversold |
| **S3** Own idea | ✅ "Why this plan" on every package | numbers checked against the package |
| Undo (UX extra) | ✅ 20 steps, survives restarts | step-by-step undo tests |
| Frontend (UX §8.4, FE-1…FE-11) | ⏳ the teammate's work | handoff guide + 33 real examples provided |

**Implementation notes that refine this PRD:** out-of-window dates return `NO_PACKAGE` / `OUT_OF_WINDOW` (not a field error); both flight items carry the
arrival city (Q4); the stay-quality and child-friendly scores are nights- and share-weighted (§6.10A); the validator enforces only statement rules.
Supporting documents: `README.md`, `docs/ARCHITECTURE.md`, `docs/API.md`, `docs/FRONTEND_HANDOFF.md`, `docs/break-it-log.md`, `docs/api-examples/`.

---

## Table of contents
1. Summary · 2. Goals & success criteria · 3. Users & golden scenario · 3A. Problem-statement compliance · 3B. Strict-compliance audit · 4. Scope tiers & ownership · 5. Functional requirements · 6. Backend design (algorithms) · 7. API contract · 8. Frontend work package · 9. Non-functional requirements · 10. Architecture, repo layout & Docker · 11. Data traps · 12. Testing strategy · 13. Git & collaboration workflow · 14. Delivery plan · 15. Future plans · 16. Risks · 17. Open questions & assumptions · Appendix A (Menon facts) · Appendix B (glossary)

---

## 1. Summary

A traveler enters a trip request (departure city, destination country, start date, nights, adults, children's ages, budget). The app **chooses the cities** and builds **one complete, rule-correct holiday package**: arrival and return flights, hotels, airport transfers, city-to-city transfers, and a day-by-day attraction plan, priced in INR. The traveler can change a hotel, a flight, or attractions; every change re-validates the whole package. On confirm they get a **10-digit reservation number** that reopens the summary later, also after a backend restart. The package can be exported as JSON in the shared trip format so the judges' checker can verify every rule.

**Guiding principle:** *a package that breaks one rule is wrong, even if it looks good.* Correctness beats features. One verified package is worth more than three broken ones.

## 2. Goals, non-goals, success criteria

### Goals
1. Every package emitted passes every rule in the problem's §4 — for **any** valid request, not just the Menon family.
2. Honest failure: invalid input, no possible package, and "possible but over budget" each give a distinct, clear, helpful message.
3. A change never leaves the package invalid — it succeeds (re-priced) or is refused with a reason.
4. Reservations persist and are retrievable by number, including after restart.
5. Code that both teammates can explain and make a small live change to (20% of score).

### Non-goals (this build)
Real payments, login/accounts, real supplier inventory, online deployment, currency conversion, any runtime AI/LLM call (forbidden), any edit to files under `data/`.

### Success criteria
| # | Criterion | Verified by |
|---|---|---|
| SC1 | Menon request builds a valid package within ₹3,50,000 | Golden test + independent validator |
| SC2 | Fuzzed requests (4 departure cities × 2 countries × all start dates × nights 3–10 × traveler mixes) produce **zero** validator failures | Fuzz suite |
| SC3 | Out-of-window, impossible, over-budget and malformed requests each return the correct outcome class and message | Table-driven API tests |
| SC4 | Confirm → restart backend → lookup by number returns the full package | Automated restart test + manual |
| SC5 | Exported JSON matches the shared trip format and passes our own validator after re-import | Export test |
| SC6 | `docker compose up --build` from a clean checkout serves the working app | Cold-start rehearsal |

## 3. Users & golden scenario

**Primary persona — family planner (Menon family):** first international trip from Bengaluru; wants a trustworthy ready-made package, wants to tweak hotel/flights/sights, wants a booking reference to come back to.
**Secondary persona — judge:** enters unseen requests (other departure cities, UAE, other dates, odd traveler mixes, tiny budgets), loads our JSON into a rule checker, asks about code, requests one small live change.

**Golden scenario:** BLR → Japan, **Sat 10 Apr 2027**, 6 nights (return **Fri 16 Apr**), 2 adults + 1 child (age 6), budget ₹3,50,000. Facts in Appendix A.

---

## 3A. Problem-statement compliance (non-negotiable)

Everything the statement asks for is built exactly as written. This matrix maps each statement item to where this PRD builds it. **Before every push, re-read the statement rows for the features just built and tick them off** (compliance check, alongside the break-it session).

> **Decision (Nov 2026): the *fastest* variant is dropped.** G4 now offers *Cheapest* and *Best rated* plus the *Recommended* package; every later mention of *fastest* in this document is superseded by this note.

| Statement item | What it requires (short) | Built in | Owner |
|---|---|---|---|
| **M1** Request form | The 7 fields; departure cities and countries from `destinations.json`; invalid value → clear message | §5.1 M1, §6.1 · FE-2 | BE + FE |
| **M2** Build one package | App chooses the city plan; builds a complete package; no package possible → says so **and why** | §5.1 M2, §6.3–6.11 · FE-3 | BE + FE |
| **M3** Rules respected | Every rule in problem §4 true for the package | §6.4–6.8, validator §6.13 | BE |
| **M4** Day-by-day plan | Each day in time order: flights, transfers, hotels, attractions | §5.1 M4, §7.4 `days[]` · FE-4 | BE + FE |
| **M5** Total and budget | Total in INR, the budget, amount left **or over**; export JSON (shared trip format) | §5.1 M5, §6.15 · FE-4, FE-7 | BE + FE |
| **M6** Change the package | Change hotel, change flight, add/remove attractions; whole package re-checked; total updated **or** change refused with a reason | §5.1 M6, §6.12 · FE-5. *An over-budget edit is returned as a refusal with a reason (`BUDGET_EXCEEDED`) that the traveler can override only by explicitly raising the budget; the UI still shows "left or over"* | BE + FE |
| **M7** Confirm & summary | Unique 10-digit number; summary by number, also after backend restart; wrong number → "not found" | §5.1 M7, §6.14 · FE-6 | BE + FE |
| **M8** Budget too small | Say so, show the cheapest total, suggest a change | §5.1 M8, §6.11 · FE-3 | BE + FE |
| **G1** Changes affecting other parts | Fix or warn about the other bookings affected | §5.2, §6.12 | BE + FE |
| **G2** Price difference | Each change option shows the difference vs. current | §5.2, §7.5 `price_delta_inr` | BE + FE |
| **G3** Change cities | Choose another valid city plan; app rebuilds | §5.2, §7.5 city-plans | BE + FE |
| **G4** Three packages | Cheapest, fastest (flights + city-to-city transfer minutes), best rated (average `stars`, within budget; guest `rating` ignored); traveler picks one | §5.2, §6.10 | BE + FE |
| **S1** Quick request | Plain-words request read with rules (no AI) fills the form | §5.2 | BE + FE |
| **S2** Booking uses seats/rooms | Confirmed reservation reduces seats and rooms in our own store; same last seats/rooms refused | §5.2, §6.14 | BE + FE |
| **S3** Own idea | Any extra feature | §5.2 | BE + FE |
| Export format | Shared trip format; `country`; hotel items have `room_id`; after confirm `status = BOOKED`, `booking.reference` = number as string | §6.15 | BE |
| Technical rules | Any stack; catalog only (data files unchanged); backend holds the logic; state saved across refresh **and** restart; no AI in the app; start in 1–2 commands; built during the event (Git history) | §9, §10, §13 | BOTH |
| Judging inputs | Unseen requests (other cities, UAE, dates, travelers, budgets) → package / over budget / none / invalid, each handled correctly | §7.3, §12 | BE |
| Demo & submission | README (how to start, architecture, city rule, what is finished, known limitations); zip without `node_modules`/venvs/build output/keys; push to Git | §10.3, §13, §14 | BOTH |
| Photo credits | If photos are shown, also show the credits in `images/ATTRIBUTIONS.md` | §5.2 S3, FE-8 | FE |

**Clarifications we chose (they do not change the statement):** the form shows exactly the 7 fields and no extra required input (traveler name is not asked; the export uses a default); "1–2 attractions on every full day" is applied to the first system-built package, as the statement words it; we never pick something the statement forbids (e.g. Nara attractions, a hotel night on the last day).

### 3B. Final strict-compliance audit (done before build)
Every rule and feature in the problem statement was re-read against this PRD. Result:
| Check | Result |
|---|---|
| All 8 Must-haves (M1–M8) present with behavior exactly as worded | ✅ §3A, §5.1 |
| All 4 Good-to-have and 3 Stretch features present as worded | ✅ §5.2 |
| Every travel rule in problem §4 (dates, cities, flights, airport transfers, city transfers, hotels, attractions, prices) is both built (§6.3–6.9) and validated (§6.13) | ✅ |
| Price formulas and child definition (0–17), 1% tolerance understood | ✅ §6.9 |
| Export format: `country`, hotel `room_id`, `sources: []`, after confirm `BOOKED` + `booking.reference` string | ✅ §6.15 |
| Technical rules: any stack, catalog-only, backend logic, state saved across refresh **and** restart, no AI, start in 1–2 commands, built during the event | ✅ §9, §10, §13 |
| Judges' four outcomes (package / none within budget / no package / invalid value) each handled | ✅ §7.3 |
| Demo: form empty before the slot; Menon request end to end (build, change, confirm, open reservation) | ✅ §8 FE-2, §14 |
| Submission: README contents, zip without `node_modules`/venvs/build output/keys | ✅ §14 README checklist |
| Photos shown ⇒ credits shown | ✅ FE-8 |
| Where we are **stricter** than the statement (never looser) | return pickup on the last day only; 30-min gaps / 08:30–21:30 window only for *system-suggested* visits; over-budget edits need explicit consent. None of these can make a package violate a statement rule |
| Where we **add** to the statement (additive only) | budget alternatives, raise-budget, warnings, pinned items, quality score, undo, UX layer |
| Anything that **contradicts** the statement | **None found.** Two choices are interpretations of ambiguous wording and are recorded as decisions: return-flight `city` = last trip city (Q4) and "1–2 attractions" applying to the first package only (Q3) |

---

## 4. Scope tiers & ownership

| Tier | Features | Backend [BE] (you) | Frontend [FE] (teammate) |
|---|---|---|---|
| **Core** | M1 request form · M2 build package · M3 rules · M4 day plan · M5 total/budget/export · M6 changes · M7 confirm/lookup · M8 budget-too-small · FR-V validator · FR-P persistence | Engine, validator, API, DB, export, Docker | Form, package view, change dialogs, confirm/reservation pages, outcome pages |
| **Stretch** (priority order) | G1 knock-on fixes · G2 price diffs · G4 three packages · G3 change cities · S2 inventory use · S1 quick request · S3 own idea | Engine/API support per feature | UI for each: warning badges, diff chips, variant tabs, city-plan chooser, quick-request box, credits page |
| **Future** | See §15 | — | — |

**Hard gate:** no stretch work starts until SC1–SC5 pass. **Build order:** (1) the compulsory Must-haves M1–M8 exactly as the statement words them, (2) the independent validator and tests, (3) Good-to-have, (4) Stretch. Customer-friendly UX (§8.4) is part of the Must-haves' definition of done on the frontend side, not an afterthought.

---

## 5. Functional requirements

Each requirement lists what the **backend** must do, what the **frontend** must do, and how we know it's done.

### 5.1 CORE

#### M1 — Request form & validation
| Field | Rule → error message (examples) |
|---|---|
| `departure_city` | One of `destinations.json` `departure_cities[].city` (Bengaluru, Delhi, Mumbai, Chennai) → "Choose a departure city from the list" |
| `country` | One of `countries[].name` (Japan, United Arab Emirates) |
| `start_date` | A real date (`YYYY-MM-DD`) → "Enter the first day of the holiday as a real date" |
| `nights` | Whole number 3–10 → "Nights must be a whole number between 3 and 10" |

*A valid date whose trip falls outside the data window (first night before 1 Apr 2027, or return after 20 Apr 2027) is **not** a field error: per the data dictionary ("a request outside the window has no package: say so") the app answers `NO_PACKAGE` / `OUT_OF_WINDOW` with a plain explanation.*
| `adults` | Integer ≥ 1 |
| `child_ages` | List of integers 0–17 (children count = list length) → "Child age must be between 0 and 17" |
| `budget_inr` | Positive integer |

- **[BE]** Validates every field server-side with per-field messages (`fields[]` in the error response, §7.1). Serves dropdown values and rules at `GET /api/meta`.
- **[FE]** Renders the 7 fields; dropdown values come **only** from `/api/meta`; mirrors validation for instant feedback; maps server `fields[]` errors to inputs. Form is empty on first load.
- The form shows **exactly these 7 fields** (as the statement requires) — no extra required input.
- **Done when:** every invalid value shows a clear message next to the field; valid input proceeds.

#### M2 — Build one package (the app chooses the cities)
- **[BE]** Generates all valid city plans (§6.3), searches flights/hotels/transfers/attractions (§6.4–6.10), returns one of three outcomes: `PACKAGE`, `OVER_BUDGET`, `NO_PACKAGE` (§7.3). `NO_PACKAGE` carries the *reason* from the failure diagnostics (§6.11).
- **[FE]** Calls `POST /api/packages`; on `PACKAGE` routes to `/packages/:id`; on the other two shows the dedicated pages (§8).
- **Our city rule (README text):** a plan is an ordered list of distinct cities of the chosen country, each ≥ 2 nights, nights summing to the trip length, consecutive cities linked in `countries[].links`; first city reachable from an arrival airport that serves it, last city from a return airport that serves it. **Default plan choice is constraint-first, then time-based (see §6.10 and Q2):** only plans that satisfy every hard rule *and* the traveler's budget are eligible; among them the app suggests the plan that best fits the **time available** (preferred number of cities ≈ one per 3 nights, least time lost in transit). The traveler can then edit (G3) and the app raises warnings, e.g. "rushed: 3 cities in 6 nights". Within the chosen plan the app builds the **best recommended package**: it spends the budget on quality (better hotels, direct flights, 2 attractions a day) and lands near the budget instead of defaulting to the cheapest (§6.10A).
- **Done when:** any valid request yields a validator-clean package, or a correct explanation.

#### M3 — Rules are respected
Enforced **by construction** in the builder **and re-checked by an independent validator** (FR-V, rule catalogue in §6.13). Full rule list is in the problem's §4; our derived timing decisions are in §6.6–6.8.

#### M4 — Day-by-day plan
- **[BE]** Returns `days[]`: for each date a `kind` (`ARRIVAL`, `FULL`, `CITY_CHANGE`, `LAST`), the city, and chronologically ordered `events` referencing items (flight, transfers, hotel check-in/out, attractions) with local start/end times.
- **[FE]** Renders one section per day in time order with icons/labels; shows quantity (seats/rooms/vehicles/tickets) and price per event; last day shows check-out → transfer → flight with no attractions.
- **Done when:** the timeline matches the exported items one-to-one.

#### M5 — Total, budget, export
- **Prices:** see §6.9. **[BE]** `total = Σ item.price_inr` exactly (integer rupees); returns `pricing{total_inr, budget_inr, remaining_inr, over_budget, breakdown{flights,hotels,transfers,attractions}}`.
- **Export:** `GET /api/packages/{id}/export` returns the shared trip format (§6.15) with `Content-Disposition: attachment`.
- **[FE]** Shows total, budget, and amount left/over (color **and** text, e.g. "₹42,300 left" / "₹8,900 over"); Export button downloads the file.
- **Done when:** exported file re-imported into our validator passes (SC5).

#### M6 — Change the package
| Change | Backend behavior | Frontend behavior |
|---|---|---|
| **Change hotel** (a city) | Lists alternatives (hotel+room) in that city that fit travelers and have rooms every night; apply recomputes rooms, price, and re-resolves airport transfer if first/last city | Hotel picker per city; shows result or refusal reason |
| **Change flight** (arrival or return) | Lists valid alternatives (airport serves city, enough seats); apply recomputes flight price, airport transfer timing/service hours, arrival-day/last-day consequences | Flight picker per leg |
| **Add attraction** | Lists attractions valid for a chosen day (city, weekday, not closed, fits hours, free slot, not already used) and valid start times; apply inserts | Add dialog by day, pick attraction + start time |
| **Remove attraction** | Removes; warns if a full day is left with 0 | Remove button on each attraction card |

- After **every** change **[BE]** re-runs the full validator, recomputes total, and returns `APPLIED` (+ new package), `REFUSED` (a hard rule would break; specific reason; package unchanged), or `BUDGET_EXCEEDED` (the change is legal but the new total would exceed the budget; nothing is applied until the traveler agrees to raise the budget) (§6.12, §7.5).
- **Attraction count rule (decided):** "1–2 per full day" applies to the **first system-built package** only (literal reading of the problem statement). Edits are not count-capped, but must satisfy all other attraction rules; the response includes a non-blocking warning when a full day ends with 0 or >2 attractions.
- A confirmed (BOOKED) package is locked: all changes return `REFUSED` with `PACKAGE_LOCKED`.
- **Done when:** each change type works, totals update, and every invalid change is refused with a readable reason.

#### M7 — Confirm & reservation summary
- **[BE]** `POST /api/packages/{id}/confirm` creates a unique **10-digit** number (random, first digit 1–9, stored as string, DB unique constraint, retry on collision); idempotent (same package → same number); sets items `status = BOOKED` and `booking.reference`. `GET /api/reservations/{number}` returns the stored package snapshot; unknown or malformed → 404 `RESERVATION_NOT_FOUND`.
- **[FE]** Confirm dialog (shows total) → success page with the number prominent + copy button; lookup page with a number field; "Reservation not found" state; read-only summary reusing the timeline.
- **Done when:** confirm → restart backend → lookup works (SC4); wrong number shows "not found".

#### M8 — Budget too small
**Budget is the first constraint.** If the request can't be done within the budget, the app says so honestly, then shows what *is* possible, or lets the traveler raise the budget.
- **[BE]** When valid packages exist but all exceed budget, returns `OVER_BUDGET` with: a plain statement that the trip is not possible within the budget as entered, `cheapest_total_inr`, `over_by_inr`, and `alternatives[]` — up to 4 **fully built, validated packages that fit the budget** (drop a city, fewer nights, shift the start date, or a combination), each with a description of what changed, its total, and a draft `package_id`; plus a `RAISE_BUDGET` option stating the extra amount needed. Algorithm in §6.11.
- **[FE]** Page states the problem, shows the cheapest total and shortfall, then shows the alternatives as cards ("Drop Kyoto: Tokyo only, 6 nights — ₹3,41,000, ₹9,000 left") that open the package on click, a clear "Increase budget to ₹4,12,000 (+₹62,000)" button, and an "Edit the trip" button that returns to the form with the previous values.
- **Done when:** a request with a too-small budget never shows an over-budget package as the answer; always shows the cheapest total; every alternative offered is valid and within budget; raising the budget builds the original request.

#### FR-V — Independent validator [BE]
A separate module that takes a package + raw catalog and re-checks **every** rule from scratch (catalogue in §6.13). It does not call the builder's helpers. Runs after build, after every change, on export, and inside fuzz tests. Violations are structured: `{rule_id, severity, item_id?, message}`.

#### FR-P — Persistence [BE]
SQLite on a Docker named volume. Tables: `packages`, `reservations`, (S2) `inventory_used`. Catalog loaded read-only into memory at startup. A test hashes the `data/` files to prove they are untouched.

### 5.2 STRETCH (priority order) — ✅ delivered
| Pri | # | Feature | Backend | Frontend |
|---|---|---|---|---|
| 1 | **G1** | Changes that affect other parts | After a change: re-time transfers; shift attractions that no longer fit (things the traveler chose are never dropped silently — user priority, §6.12); detect overlaps/double bookings; warn that a flight change moves hotel check-in time (display only). Warnings in `warnings[]` (package + item level) | Warning banner + per-item badges; show what was auto-fixed |
| 2 | **G2** | Price difference | Every option returned by `/options/*` carries `price_delta_inr` vs. current (including knock-on transfer changes) | `+₹X`/`−₹X` chips on every option |
| 3 | **G4** | Three packages | `POST /api/packages/variants` returns `cheapest`, `fastest`, `best_rated` (§6.10) each saved with its own id | Tabs/cards to compare and pick; picked id continues the normal flow |
| 4 | **G3** | Change cities | `GET /options/city-plans` lists valid plans with totals; `CHANGE_CITY_PLAN` rebuilds | City-plan chooser with totals |
| 5 | **S2** | Booking uses seats/rooms | `inventory_used` overlay; confirm refuses on conflict (`INVENTORY_CONFLICT`, 409) and every later build/option uses effective availability | Conflict message with "choose another" action |
| 6 | **S1** | Quick request (rules, no AI) | `POST /api/parse-request` parses e.g. "Japan 10 Apr 6 nights 2 adults 1 child 6 from Bengaluru 3.5 lakh" with regex/keyword rules and aliases; returns fields + which were understood | Text box on the form, fills fields for review, highlights unparsed parts |
| 7 | **S3** | Own idea | *Trip rationale*: one-line "why this plan" and an alternative-cities comparison; plus photo-credits data endpoint | Rationale panel; credits page and footer link whenever photos are shown (required by `ATTRIBUTIONS.md`) |

---

## 6. Backend design [BE]

### 6.1 Conventions
- **Times:** local time of the place; no UTC conversion anywhere. Represent a time as minutes since midnight; a datetime as (date, minutes).
- **Windows:** `HH:MM` strings; `24:00` = 1440. A window `from..until` where `until < from` wraps midnight (e.g. `06:00–00:30`). Both ends inclusive. `in_window(t)` = `from ≤ t ≤ until` (non-wrapping) or `t ≥ from or t ≤ until` (wrapping).
- **Money:** integers (INR). Percentage tolerance (1%) exists only on the judges' side; we compute exact integers.
- **Travelers:** `adults`, `children = len(child_ages)`, `travelers = adults + children`.
- **Day kinds:** day 0 = `ARRIVAL`; days where the city changes = `CITY_CHANGE`; the last day = `LAST` (return flight, no hotel night); all other days = `FULL`.
- **"That night's city":** the city of the hotel night starting on that date (arrival day → first city; change day → the new city).

### 6.1A Time model & time-based planning
"Time" appears in five different ways in this product. Each has a precise meaning and a place where it is used:

| # | Time notion | Definition | Used for |
|---|---|---|---|
| **T1** | **Trip length** | Number of nights `N` (3–10) | Preferred number of cities `k* = clamp(⌊N/3⌋, 1, #cities)`: 3–5 nights → 1 city, 6–8 → 2, 9–10 → 3 (Japan) or 2 (UAE) |
| **T2** | **Transit time** | `transit_minutes` = Σ flight `duration_minutes` (both flights) + Σ intercity transfer `duration_minutes`. Airport transfers and city taxis excluded (same as the G4 "fastest" definition) | "Fastest" variant; time-equal band in the default ranking; shown to the traveler |
| **T3** | **Usable ground time** | `usable_ground_minutes` = Σ over days of the minutes inside the activity window 08:30–21:30 that the traveler can actually use: arrival day from (hotel arrival + 30 min); city-change day from (arrival in the new city + 30 min); full day = 780; last day = 0 | Tie-breaker in the default ranking; `LONG_TRANSIT_DAY` warning; displayed in the package metrics |
| **T4** | **Time-of-day feasibility** *(hard)* | Landing + 60 ≤ pickup; pickup + duration ≤ departure − 180; pickups/departures inside service windows (incl. wrap and `24:00`); frequency grid; visits inside opening hours | Validator rules A4–A7, T3, X3–X5, X8 — never relaxed |
| **T5** | **Time per city** | ≥ 2 consecutive nights *(hard)*; ≥ 3 nights on average *(recommended, soft)* | City-plan generator; `RUSHED_PLAN` warning |

**Default ranking (after constraints — hard rules and budget — are satisfied):**
1. Closeness to `k*` cities (exact `k*`, else `k*−1`, else `k*+1`, with an explanatory warning).
2. **Time-equal band:** among those plans, any plan whose `transit_minutes` is within `TIME_TOLERANCE_MIN` (default **120**, configurable) of the best is treated as equal on time. Beyond the band, less transit wins.
3. **Highest quality score within the budget** (§6.10A) — the app spends the budget on quality instead of defaulting to the cheapest package.
4. Most `usable_ground_minutes`.
5. Most balanced nights, then deterministic IDs (`flight_id`, `hotel_id`, `transfer_id`).

**Why a tolerance band (evidence from the data, Menon trip, 6 nights, 3 travelers — flights + intercity only):**
| Plan (nights) | Best flights | `transit_minutes` | Flight cost (3 seats) |
|---|---|---|---|
| Osaka ⇄ Kyoto | `FL-740` in, `FL-411` out | **1,075** | ₹1,81,440 |
| Tokyo → Kyoto | `FL-401` in, `FL-411` out | 1,135 | ₹1,53,720 |
| Tokyo → Osaka | `FL-401` in, `FL-411` out | 1,150 | ₹1,53,720 |
| Tokyo / Kyoto / Osaka (2,2,2) | `FL-401` in, `FL-411` out | 1,150 | ₹1,53,720 |
| Kyoto → Tokyo | `FL-740` in, `FL-412` out | 1,225 | ₹1,83,960 |

A strict "least transit" rule would pick Osaka ⇄ Kyoto: it saves only **60 minutes** but costs **₹27,720 more** in flights, and skips Tokyo. With the 120-minute band the Tokyo → Kyoto and Tokyo → Osaka plans count as time-equal, so the quality score (§6.10A) then decides. (Under the "6–8 nights → 2 cities" rule, the 3-city plans are only a fallback.)

### 6.2 Pipeline
```
request → validate → candidate plans → per plan: flights × hotels × transfers → attractions
        → price → rank by objective → independent validation → persist → response
```

### 6.3 City plans
1. Take the country's cities and `links`.
2. For k = 1 … min(#cities, ⌊N/2⌋): all ordered k-permutations of cities where each consecutive pair has a link.
3. For each permutation: all compositions of N into k parts, each ≥ 2.
4. Keep plans whose first city has ≥ 1 airport that serves it **and** last city ditto. **A city is therefore only ever suggested as the last city if a valid return flight exists for it** (right date, an airport that serves that city, enough seats); the same filter applies to the city plans listed for G3 and to every alternative.
Japan ≤ 3 cities, UAE ≤ 2 → small, enumerate everything. 3 nights ⇒ single city only.

### 6.4 Flights
- **Arrival candidates:** `from = dep airport`, date part of `arrival_local == start_date`, `to` airport's `serves_cities` contains the first city, `seats_left ≥ travelers`.
- **Return candidates:** date part of `departure_local == start_date + N`, `from` serves the last city, `to = dep airport`, `seats_left ≥ travelers`. (With S2, `seats_left` is the effective value.)
- Key everything on `flight_id`. Never derive duration from local times; use `duration_minutes`.
- **Price:** `price_per_seat × travelers`. **Quantity:** `travelers`.

### 6.5 Hotels & rooms
- `rooms_needed(room)`: smallest k ≥ 1 with `adults ≤ k·max_adults` and `adults+children ≤ k·(max_adults+max_children)`; valid only if `k ≤ adults`. (k = max(⌈A/max_a⌉, ⌈(A+C)/(max_a+max_c)⌉); then check `k ≤ A`.)
- **Availability:** for every night date in the stay, `rooms_left ≥ k` (check-out day excluded).
- **Per city:** one hotel + one room type for all nights. Cost = `price_per_night × k × nights`.
- **Selection by objective:** cheapest → min cost; best-rated → max `stars` (never `rating`), tie → cheaper. Middle cities are independent; first/last cities are coupled to the airport transfer (area + service window) so choose the hotel together with its transfer.
- Soft preference: `family_friendly` hotels first when children travel (tie-breaker only).

### 6.6 Airport transfers
Match: `transfer.airport == flight airport`, `transfer.city == hotel.city`, `transfer.area ∈ {hotel.area, null}`.
**Arrival (airport → first hotel):**
- earliest pickup `P ≥ landing + 60 min` and `in_window(P)`; pick the earliest such `P`. If none, this transfer (or flight) is infeasible.
- arrival at hotel = `P + duration`. Arrival-day attractions start ≥ arrival at hotel + 30 min.
- A pickup after midnight (e.g., landing 23:30 + 60) is allowed when the window wraps; the datetime is on the next date.

**Departure (last hotel → airport):**
- must satisfy `P + duration ≤ departure − 180 min` (reach airport ≥ 180 min before) and `in_window(P)`; choose the **latest** such `P` on the **last day** (pickup the day before is not allowed — we read "no hotel night on the last day" strictly).
- **Price:** PER_PERSON → `adults×price + children×(child_price ?? price)`; PER_VEHICLE → `price × ⌈travelers / max_passengers⌉`.
- **Choice among options:** cheapest feasible (taxi vs bus vs van); deterministic tie-break by `transfer_id`.

### 6.7 Transfers between cities
- For each city-change day pick a transfer from `link.transfer_ids`.
- Departure times: for trains/buses with `frequency_minutes`: `service_from + n·frequency ≤ service_until`; for taxis (no frequency): any minute in window.
- Choose the **earliest** departure on the day (maximizes time in the new city); arrival = departure + duration.
- City taxis to/from stations are **not added** (optional by rule).
- **Price:** same formulas as §6.6. **Fastest objective** sums these transfers' `duration_minutes` (airport transfers and city taxis excluded).

### 6.8 Attractions
- **Pool per day:** attractions where `city = that night's city`, weekday ∈ `open_days`, date ∉ `closed_dates`, and `visit_minutes` fits the opening window. Nara is automatically excluded (no hotels).
- **Statement rules vs. comfort rules.** *Statement rules* are the only **hard** checks (validator and user edits): the visit is inside the attraction's opening hours on an open day, visits on a day do not overlap, each attraction is used at most once, and on arrival/city-change days a visit starts after the traveler reaches the city. *Comfort rules* apply **only when the system suggests visits** for the Recommended package, and never to user edits or the validator:
  - **Day activity window (config):** 08:30–21:30.
  - **Gap between visits:** ≥ 30 min.
  - **Settling time:** first visit on an arrival/change day starts ≥ 30 min after reaching the hotel/city.
  A user may therefore add, say, Dotonbori at 10:00 pm (open until 11:00 pm) or schedule two visits back to back, as long as the statement's rules hold.
- **Uniqueness:** each attraction at most once in the whole package.
- **First package:** `FULL` days get 1–2 attractions (target 2, minimum 1); `ARRIVAL`/`CITY_CHANGE` days optional (add one if time allows and budget remains); `LAST` day none.
- **Selection order:** *min-cost mode* (Cheapest variant, over-budget feasibility): cheapest first (free first). *Recommended mode:* a varied mix (different categories on different days), `child_friendly` when children travel (soft), `accessible`, up to 2 per full day, paid attractions allowed while the budget permits. Ties by catalog order for determinism. Choose the set that guarantees every full day ≥ 1 first (matching problem: if a city lacks enough open attractions for its full days, that plan is infeasible → try next plan).
- **Price:** `adults×price_per_person + children×(child_price ?? price_per_person)`. `child_price = 0` is a real free price; only an **absent** field falls back to the adult price.

### 6.9 Pricing summary
| Part | Formula | Quantity |
|---|---|---|
| Flight | `price_per_seat × travelers` | travelers |
| Hotel | `price_per_night × rooms × nights` | rooms |
| Transfer PER_PERSON | `adults×price + children×(child_price ?? price)` | travelers |
| Transfer PER_VEHICLE | `price × ⌈travelers / max_passengers⌉` | vehicles |
| Attraction | `adults×price_per_person + children×(child_price ?? price_per_person)` | travelers |

`total = Σ price_inr` over all items.

### 6.10 Search, objectives & default package
Search per plan (small): arrival flights × return flights × hotel+room options for each city × transfers × attractions. For each city keep only options not dominated on (price, stars, family-friendly, guest rating), which keeps the search to a few thousand combinations per plan. **Recommended mode** maximizes the quality score (§6.10A) within the budget; **min-cost mode** minimizes cost (used for the Cheapest variant and to decide whether anything fits the budget).
Two cost notions (used by min-cost mode, the Cheapest variant and the over-budget check):
- **Base cost** = flights + hotels + transfers + *minimum* attractions (1 per full day, cheapest eligible).
- **Total** = base + any extra optional attractions.

| Package | Objective | Notes |
|---|---|---|
| **Default — Best recommended** | **Step 1 — constraints first:** keep only candidates that pass every hard rule and have total ≤ budget. **Step 2 — time-based suggestion:** preferred city count `k* = clamp(⌊N/3⌋, 1, #cities)` (3 nights→1, 4–5→1, 6–8→2, 9–10→3 in Japan / 2 in UAE); among plans with `k*` cities, treat plans within `TIME_TOLERANCE_MIN` (default 120 min) of the best `transit_minutes` as time-equal, then the highest quality score (§6.10A), then most usable ground time, then balanced nights (full ranking and evidence in §6.1A). If no eligible plan has `k*` cities, fall back to `k*−1`, then `k*+1`, and attach a warning explaining why. **Step 3 — spend the budget on quality:** within the chosen plan, pick the flights, hotels, transfers and attractions with the highest quality score that fit the budget, so the package lands **near the budget** (e.g. a ₹4,00,000 budget gets a ~₹3.6–4.0 lakh holiday with better hotels, direct flights and 2 attractions a day — not a ₹2,00,000 minimum package) | What `POST /api/packages` returns |
| **Cheapest** (G4) | Minimum total with minimum attractions | True lowest total |
| **Fastest** (G4) | Minimize Σ flight `duration_minutes` + Σ intercity transfer `duration_minutes`; among **within-budget** packages; ties → cheaper | If none within budget, omit with note |
| **Best rated** (G4) | Maximize average hotel `stars` per night = Σ(stars×nights)/N, **within budget**; ties → cheaper; `rating` ignored | If none within budget, omit with note |

Deterministic tie-breaks everywhere: higher quality score → closer to (but not over) the budget → lower cost → less travel time → plan order → `flight_id` / `hotel_id` / `transfer_id`. (Variants other than the default keep their own objective first.)

### 6.10A Recommended package — spend the budget on quality
**Principle:** a traveler who gives ₹4,00,000 should get a holiday that uses it well, not a ₹2,00,000 minimum package with ₹2,00,000 unused. The default package maximizes a **quality score (0–100)** among packages that satisfy every hard rule **and** total ≤ budget. The score only chooses between valid packages — it never relaxes a hard rule.

| Component | Points | How it is scored |
|---|---|---|
| **Stay** | 40 | `28 × (average stars per night − 2) / 3` · up to `6` for family-friendly hotels, weighted by nights (full when no children travel) · `6 × (average guest rating − 6.9) / 2.5` |
| **Flights** | 20 | `5` per direct leg (2 legs) · `5` if the arrival lands 06:00–20:00 local · `5` if the return departs 08:00–20:00 local |
| **Experience** | 15 | `9 × attractions on full days / (2 × full days)` · `3 × min(distinct categories, 4) / 4` · `3 × share of child-friendly attractions` (full when no children travel) |
| **Time** | 15 | `9 × (1 − (transit − best transit) / (worst transit − best transit))` across the request's feasible candidates (full 9 if only one) · `6 × usable ground minutes / maximum possible for that plan` |
| **Budget fit** | 10 | `10 × clamp((spend ÷ budget − 0.50) / 0.40, 0, 1)` — 0 at ≤ 50% spent, full points from 90% to 100% |

- **Effect:** at ₹2.5 lakh the app builds a modest package; at ₹4 lakh it moves to 4–5★ family-friendly hotels where affordable, direct flights, sensible arrival times and 2 varied attractions a day (paid ones included); the budget-fit points pull the total toward 90–100% of the budget.
- **When the budget is far above anything the catalog offers**, the app shows the best-quality package available and the money left over; it never pads the price.
- **Guest rating is used here only as a small soft factor.** The G4 "Best rated" variant still ranks by hotel `stars` alone and ignores `rating`, exactly as the statement says.
- **Weights are constants in one config file** (a starting proposal, tuned by tests and by trying real budgets); changing them never affects correctness.
- **Other variants are unchanged:** *Cheapest* = lowest total, *Fastest* = least transit, *Best rated* = highest average stars within budget (§6.10).

### 6.11 Failure diagnostics & over-budget logic
**Stages** (the *furthest stage any candidate reached* explains `NO_PACKAGE`):
1. Date window / nights → `OUT_OF_WINDOW`
2. Arrival flights exist on start date (to an airport serving any city) → `NO_ARRIVAL_FLIGHT`
3. Arrival flights with enough seats → `INSUFFICIENT_SEATS_ARRIVAL`
4. Return flights exist on end date → `NO_RETURN_FLIGHT`; with seats → `INSUFFICIENT_SEATS_RETURN`
5. City plan compatible with flight airports → `NO_CITY_PLAN_FOR_FLIGHTS`
6. Hotel + room that fits and is available all nights in every city → `NO_ROOMS`
7. Airport transfer feasible in service hours → `NO_AIRPORT_TRANSFER`
8. City transfer feasible → `NO_CITY_TRANSFER`
9. Enough open attractions for full days → `NOT_ENOUGH_ATTRACTIONS`
Each reason includes human text plus counts (e.g., "6 flights found on 10 Apr but none has 12 free seats").
**Budget-first flow — the budget is the first constraint we protect:**
1. **Build the request as entered.** A package is shown only if it passes every hard rule **and** `total ≤ budget`.
2. **If valid packages exist but none fits the budget** → outcome `OVER_BUDGET`. The message says plainly that *this trip is not possible within the budget as requested* and gives the cheapest total for the original request (e.g. "The cheapest Tokyo + Kyoto holiday for 6 nights costs ₹4,12,000 — ₹62,000 over your ₹3,50,000 budget").
3. **Show what is possible.** The backend then builds — fully, and validated — up to 4 alternatives that **do** fit the budget, ordered by how little they change the request (one change first, then two combined):
   | Lever | What changes |
   |---|---|
   | `DROP_CITY` | Fewer cities, same nights (e.g. remove Kyoto → Tokyo only) |
   | `FEWER_NIGHTS` | N−1 … 3 nights |
   | `SHIFT_DATE` | Start date ±1…3 days (inside the data window) |
   | Combinations | `DROP_CITY` + `FEWER_NIGHTS`, `DROP_CITY` + `SHIFT_DATE`, `FEWER_NIGHTS` + `SHIFT_DATE` |
   Each alternative is itself built as a **Recommended** package for the changed request, within the budget, so it is a good holiday and not just a cheap one. Each alternative carries a plain description of what changed ("Drop Kyoto: Tokyo only, 6 nights"), its total and remaining budget, and a saved draft `package_id` so the traveler can open it immediately.
4. **Always also offer "raise the budget".** `RAISE_BUDGET` states the extra needed (e.g. "+₹62,000 → ₹4,12,000"); if the traveler agrees, the app builds the original request with the new budget. The app never exceeds the budget silently.
5. **If no lever combination fits**, say so: "even the cheapest possible holiday for these travelers and dates costs ₹Y" and offer only raise-budget and "Edit the trip".
6. The traveler chooses: open an alternative, raise the budget (explicit consent), or edit the trip.

**Edits protect the budget too.** A change whose new total would exceed the budget is **not applied**. The response is `BUDGET_EXCEEDED` with `new_total_inr`, `over_by_inr`, cheaper options for that same slot (options carry `fits_budget` and `budget_needed_inr`), and the choice to re-send the same change with `raise_budget: true` (explicit consent; the budget becomes the new total). Hard-rule breaks are still `REFUSED`.

### 6.12 Changes (apply logic)
Common flow: load package → clone → apply edit → recompute dependents → validate (FR-V) → if violations → `REFUSED` with the first blocking reason; else persist and `APPLIED`.
- **CHANGE_HOTEL(city, hotel_id, room_id):** check hotel in city, room belongs to hotel, fit, availability on every night; if city is first/last, re-resolve airport transfer (area/service window; refuse if none); attractions in that city are unaffected (same city).
- **CHANGE_FLIGHT(leg, flight_id):** check route/date/airport-serves-city/seats; recompute transfer. Arrival leg: re-time arrival-day attractions (G1: shift ones that no longer fit and warn; a traveler-added attraction that cannot be kept makes the change `PINNED_CONFLICT` — the traveler decides — and is never silently dropped; system-suggested ones may be re-chosen with a warning). Return leg: transfer pickup recomputed; if infeasible → refuse.
- **ADD_ATTRACTION(attraction_id, date, start?):** day must not be `LAST`; city = that night's city; open; not closed; fits hours; no overlap/buffer violation; not already used; on arrival/change day start ≥ arrival at city. If `start` omitted, backend picks the earliest free slot.
- **REMOVE_ATTRACTION(item_id):** remove; warning if a full day now has 0.
- **CHANGE_CITY_PLAN(plan[])** (G3): rebuild whole package for the chosen plan, keeping pinned items (hotels, flights and attractions the traveler chose) wherever they are still valid; anything that cannot carry over is listed (`PINNED_CONFLICT`) and the traveler confirms before it is removed.
- **PACKAGE_LOCKED:** any change on a BOOKED package is refused.

**User choices take priority.** Anything the traveler picks (a hotel, a flight, an attraction they added, a city plan) is marked `pinned`. Automatic work never overrides it: a later change keeps pinned items whenever the hard rules still allow. If a pinned item can no longer be kept, the app does **not** silently drop it — it returns `PINNED_CONFLICT`, explains the clash in plain words and gives the traveler the choice (e.g. "The later flight leaves no time for Senso-ji on 10 Apr. Keep the current flight, or take the later flight and remove Senso-ji?"). System-suggested items may be re-chosen automatically, with a warning. The traveler's own additions are not count-capped (Q3).

**Hard rules, budget, and soft checks.** *Hard* travel rules (§6.13) are never broken: a change that would break one is **refused** with a reason. The traveler's **budget** is protected too: a change that would exceed it is **not applied** unless the traveler explicitly agrees to raise the budget (`BUDGET_EXCEEDED`, §6.11). *Soft* concerns never block the traveler; the change is applied and a **warning** is returned (package-level or per item), so the traveler stays in control after the first package has satisfied their constraints:
| Soft warning | When |
|---|---|
| `RUSHED_PLAN` | City plan has fewer than 3 nights per city on average, or more than `k*` cities |
| `LONG_TRANSIT_DAY` | City-change day where transit leaves little time in the new city |
| `ATTRACTION_DAY_LOAD` | A full day ends with 0 or more than 2 attractions |
| `ARRIVAL_SHIFTED` | A flight change moved the transfer and an attraction was shifted or dropped (G1) |
| `CHECKIN_TIME` | New arrival is before the hotel's check-in time or after midnight (display-only per problem FAQ) |
| `NOT_FAMILY_FRIENDLY` | Traveler picked a hotel with `family_friendly: false`, or an attraction with `child_friendly: false`, while children travel |

### 6.13 Validator rule catalogue (FR-V)
| ID | Rule |
|---|---|
| **D1** | nights ∈ [3,10] |
| **D2** | first night ≥ 2027-04-01 |
| **D3** | return date ≤ 2027-04-20 |
| **D4** | plan nights sum = nights; return date = start + nights |
| **C1** | all cities belong to chosen country |
| **C2** | each city ≥ 2 consecutive nights |
| **C3** | each city appears once |
| **C4** | consecutive cities have a link |
| **F1** | exactly one arrival and one return flight, ids exist in catalog |
| **F2** | arrival from departure airport; return to departure airport |
| **F3** | arrival local date = start date |
| **F4** | arrival airport serves first city |
| **F5** | return departure local date = end date |
| **F6** | return airport serves last city |
| **F7** | `seats_left ≥ travelers` for both flights |
| **A1** | exactly one arrival transfer and one departure transfer |
| **A2** | transfer airport = flight airport |
| **A3** | transfer city = hotel city; area = hotel area or null |
| **A4** | arrival pickup ≥ landing + 60 min |
| **A5** | pickup + duration ≤ departure − 180 min |
| **A6** | pickup inside service window (both transfers) |
| **A7** | departure pickup is on the last day |
| **T1** | exactly one transfer on each city-change day, none otherwise |
| **T2** | `from_city`/`to_city` match; transfer id ∈ link's `transfer_ids` |
| **T3** | departure inside window and on frequency grid |
| **H1** | exactly one hotel and one room type per city, all nights |
| **H2** | hotel city = plan city; room belongs to hotel |
| **H3** | every night covered; no hotel on last day |
| **H4** | rooms k fit travelers (3 inequalities) |
| **H5** | `rooms_left ≥ k` on every night (effective availability) |
| **X1** | attraction exists; date within trip days |
| **X2** | city = that night's hotel city |
| **X3** | open that weekday; not in `closed_dates` |
| **X4** | whole visit inside opening hours |
| **X5** | no overlap on a day |
| **X6** | each attraction at most once |
| **X7** | none on last day |
| **X8** | arrival/change-day visits start after reaching the city |
| **X9** | *(build mode only)* 1–2 attractions on every full day |
| **P1** | each item price equals its formula |
| **P2** | `total_inr` = Σ item prices |
| **E1** | export has all required fields; `sources == []` |
| **E2** | after confirm: status BOOKED and `booking.reference` = 10-digit string |

**The validator enforces only the statement's rules** — never our comfort preferences (30-minute gaps, the 08:30–21:30 window, the preferred city count `k*`, quality scoring). It can therefore never reject something the judges' checker would accept, and never accept something it would reject.

### 6.14 Reservations, persistence, inventory
- **DB:** SQLite (WAL). `packages(id TEXT PK, status, request_json, package_json, created_at, updated_at)`, `reservations(number TEXT PK, package_id, snapshot_json, created_at)`, `inventory_used(kind, key, date, qty)` (S2).
- **Reservation number:** `random 10-digit string, first digit 1–9`; insert inside a transaction; on unique violation, regenerate.
- **S2:** effective seats = `seats_left − used(flight_id)`; effective rooms = `rooms_left − used(room_id,date)`; confirm re-checks all items in one transaction and increments usage; any shortfall → 409 `INVENTORY_CONFLICT` naming the item.
- **Restart safety:** no in-memory-only state besides the read-only catalog cache.

### 6.15 Export mapping (shared trip format)
Top level: `trip_id`, `traveler{name, home_airport, adults, children, child_ages}`, `start_date`, `end_date`, `country`, `budget_inr`, `total_inr`, `status`, `items[]`.
Item: `item_id`, `type` (`flight|hotel|transfer|attraction`), `name`, `city`, `status` (`PLANNED|BOOKED`), `catalog_id`, `start`, `end`, `room_id`, `quantity`, `price_inr`, `booking`, `sources` (`[]`), `warnings`.
| Type | `start` | `end` | `city` | `room_id` | `quantity` |
|---|---|---|---|---|---|
| flight | departure (`YYYY-MM-DDTHH:MM`) | arrival | the **arrival city** (city of the arrival airport), exactly as the data dictionary says, for both flights — Q4 | null | travelers |
| hotel | check-in date | check-out date | hotel city | room id | rooms |
| transfer | pickup datetime | arrival datetime (or null) | transfer's city (intercity: destination city) | null | vehicles or travelers |
| attraction | visit start | visit end | attraction city | null | travelers |
After confirm: every item `status = BOOKED`, `booking = {"reference": "<10 digits>"}`.

---

## 7. API contract [BOTH — frozen after Phase 0; changes must be announced]

Base path `/api`. JSON everywhere. Money = integer INR. Dates `YYYY-MM-DD`; datetimes `YYYY-MM-DDTHH:MM` local.

### 7.1 Errors
- **Validation (422):**
```json
{ "error": { "code": "VALIDATION_ERROR", "message": "Please fix the highlighted fields.",
  "fields": [ { "field": "nights", "message": "Nights must be between 3 and 10." } ] } }
```
- **Other errors:** `{ "error": { "code": "...", "message": "..." } }` with 404 (`PACKAGE_NOT_FOUND`, `RESERVATION_NOT_FOUND`), 409 (`INVENTORY_CONFLICT`), 500 (`INTERNAL_ERROR`, no stack traces).

### 7.2 `GET /api/meta`
```json
{ "departure_cities": [{"city":"Bengaluru","airport":"BLR"}],
  "countries": [{"name":"Japan","code":"JP","cities":["Tokyo","Kyoto","Osaka"]}],
  "rules": {"min_nights":3,"max_nights":10,"first_night":"2027-04-01","last_departure":"2027-04-20","child_age_max":17} }
```

### 7.3 `POST /api/packages` — build
Request:
```json
{ "departure_city":"Bengaluru","country":"Japan","start_date":"2027-04-10","nights":6,
  "adults":2,"child_ages":[6],"budget_inr":350000 }
```
Responses (HTTP 200, discriminated by `outcome`):
```json
{ "outcome":"PACKAGE", "package":{ /* §7.4 */ } }
{ "outcome":"OVER_BUDGET", "cheapest_total_inr":412000, "over_by_inr":62000,
  "message":"This trip is not possible within ₹3,50,000 as requested. The cheapest version costs ₹4,12,000 (₹62,000 over).",
  "alternatives":[
    {"id":"alt1","levers":["DROP_CITY"],"label":"Drop Kyoto: Tokyo only, 6 nights",
     "changes":[{"field":"cities","from":["Tokyo","Kyoto"],"to":["Tokyo"]}],
     "total_inr":341000,"remaining_inr":9000,"package_id":"pkg_a1…"},
    {"id":"alt2","levers":["FEWER_NIGHTS"],"label":"5 nights instead of 6",
     "changes":[{"field":"nights","from":6,"to":5}],"total_inr":330000,"remaining_inr":20000,"package_id":"pkg_a2…"},
    {"id":"alt3","levers":["SHIFT_DATE"],"label":"Start on 12 Apr instead of 10 Apr",
     "changes":[{"field":"start_date","from":"2027-04-10","to":"2027-04-12"}],"total_inr":339000,"remaining_inr":11000,"package_id":"pkg_a3…"} ],
  "raise_budget":{ "budget_inr":412000, "extra_needed_inr":62000,
                   "label":"Increase budget to ₹4,12,000 (+₹62,000) and keep your original request" } }
{ "outcome":"NO_PACKAGE", "reason_code":"INSUFFICIENT_SEATS_ARRIVAL",
  "message":"No flight on 10 Apr to Japan has 12 free seats (best has 9).", "details":[ "…" ] }
```

### 7.4 Package object
```json
{ "package_id":"pkg_9f2c…", "status":"PLANNED", "variant":"DEFAULT",
  "request":{ /* echo of request */ },
  "city_plan":[ {"city":"Tokyo","nights":3,"check_in":"2027-04-10","check_out":"2027-04-13"},
                {"city":"Kyoto","nights":3,"check_in":"2027-04-13","check_out":"2027-04-16"} ],
  "pricing":{ "total_inr":311200,"budget_inr":350000,"remaining_inr":38800,"over_budget":false,
              "breakdown":{"flights":156240,"hotels":98000,"transfers":24000,"attractions":32960} },
  "metrics":{ "avg_hotel_stars":3.5, "transit_minutes":1135, "usable_ground_minutes":3960,
              "quality_score":78, "budget_used_pct":89 },
  "items":[ { /* shared-format items + extra: "day":"2027-04-10", "pinned":false, "image":"/images/hotels/…", "details":{…} } ],
  "days":[ { "date":"2027-04-10","weekday":"SAT","city":"Tokyo","kind":"ARRIVAL",
             "events":[ {"item_id":"i1","time":"09:20","label":"…"} ] } ],
  "warnings":[ "…" ],
  "reservation": null }
```
After confirm: `status:"BOOKED"`, `reservation:{"number":"4829105736","confirmed_at":"…"}`.

### 7.5 Other endpoints
| Method & path | Request → Response |
|---|---|
| `GET /api/packages/{id}` | → package, or 404 |
| `GET /api/packages/{id}/export` | → trip-format JSON (attachment) |
| `GET /api/packages/{id}/options/hotels?city=Kyoto` | → `{options:[{hotel_id,room_id,name,stars,rating,area,room_type,rooms_needed,price_inr,price_delta_inr,image,available:true,fits_budget,budget_needed_inr}]}` |
| `GET /api/packages/{id}/options/flights?leg=ARRIVAL\|RETURN` | → `{options:[{flight_id,airline,flight_number,from,to,departure,arrival,stops,duration_minutes,price_inr,price_delta_inr,seats_left,fits_budget,budget_needed_inr}]}` |
| `GET /api/packages/{id}/options/attractions?date=2027-04-12` | → `{options:[{attraction_id,name,category,duration_minutes,price_inr,child_friendly,image,start_choices:["09:00","10:30"]}]}` |
| `GET /api/packages/{id}/options/city-plans` (G3) | → `{options:[{plan:[{city,nights}],total_inr,price_delta_inr}]}` |
| `POST /api/packages/{id}/changes` | body `{op, …, raise_budget?:true}` → `{result:"APPLIED", package, price_delta_inr, warnings:[]}`, or `{result:"REFUSED", reason_code, reason, violations:[{rule_id,message}]}` (hard rule), or `{result:"BUDGET_EXCEEDED", new_total_inr, over_by_inr, message, cheaper_options:[…]}` (legal but over budget — resend with `raise_budget:true` to accept) |
| `POST /api/packages/variants` (G4) | request body as §7.3 → `{cheapest, fastest, best_rated, notes[]}`; each is a package with its own id (or `null`) |
| `POST /api/packages/{id}/confirm` | → `{reservation_number, package}`; 409 on inventory conflict (S2) |
| `GET /api/reservations/{number}` | → package snapshot, or 404 `RESERVATION_NOT_FOUND` |
| `POST /api/parse-request` (S1) | `{text}` → `{fields:{…}, understood:[…], unparsed:[…]}` |
| `GET /api/health` | → `{status:"ok"}` |
| `GET /images/...` | Static catalog images (read-only) |

**Change ops (`POST …/changes`):** `CHANGE_HOTEL {city,hotel_id,room_id}` · `CHANGE_FLIGHT {leg,flight_id}` · `ADD_ATTRACTION {attraction_id,date,start?}` · `REMOVE_ATTRACTION {item_id}` · `CHANGE_CITY_PLAN {plan:[{city,nights}]}` (G3).
**Refusal codes:** `PACKAGE_LOCKED`, `ROOMS_UNAVAILABLE`, `ROOM_DOES_NOT_FIT`, `SEATS_UNAVAILABLE`, `AIRPORT_MISMATCH`, `NO_AIRPORT_TRANSFER`, `ATTRACTION_CLOSED`, `ATTRACTION_OUTSIDE_HOURS`, `ATTRACTION_OVERLAP`, `ATTRACTION_DUPLICATE`, `ATTRACTION_WRONG_CITY`, `INVALID_DAY`, `PINNED_CONFLICT` (response includes `options` for the traveler to choose from), `PRICE_FORMULA_MISMATCH` (internal), `VALIDATION_FAILED`.

### 7.6 Contract handoff [BE]
At the end of Phase 0 the backend commits `docs/api-examples/*.json` (one real example per response above, including the Menon package) and the live OpenAPI at `/docs`, so the frontend can build against fixtures before the engine is finished.

### 7.7 Backend support for a friendly UI [BE → FE]
The frontend should never have to invent wording or guess what changed. The backend therefore also returns:
| Where | Fields |
|---|---|
| Every package item | `title` and `subtitle` in plain words (e.g. "Taxi from Narita Airport to your hotel" / "1 taxi · up to 4 people"), `icon` (`flight`,`hotel`,`taxi`,`bus`,`train`,`attraction`), `badges[]` (e.g. `DIRECT`, `ONE_STOP`, `FREE`, `FAMILY_FRIENDLY`, `CHILD_PRICE`, `CHEAPEST`, `BEST_RATED`), `time_label` (e.g. "9:20 am") |
| Every day | `summary` one-liner (e.g. "Arrive in Tokyo · 2 sights"), `usable_ground_minutes` |
| `POST …/changes` responses | `summary` sentence ("Hotel in Kyoto changed to Gion Corner Hotel. Total is now ₹3,12,400 (−₹2,400).") and `changed_item_ids[]` so the UI can highlight what moved; on refusal/over-budget also `suggestion` (what to do next, in plain words) |
| Options | `reason_unavailable` text for options that can't be chosen (e.g. "Sold out on 14 Apr"), so unavailable choices can be shown greyed-out instead of hidden |
| *(UX extra, after Core)* Undo | Backend keeps the last ≤ 20 versions of a package; `POST /api/packages/{id}/undo` restores the previous version (refused if `BOOKED`) |
All wording is produced by the backend in one place so it stays consistent and testable.

---

## 8. Frontend work package [FE — teammate]

The frontend **only** talks to `/api/*` (and `/images/*`). It never reads catalog files and contains no travel-rule logic; it renders what the backend returns.

### 8.1 Routes (state lives in the URL so a page refresh works)
| Route | Screen |
|---|---|
| `/` | Enter the trip (empty form) |
| `/packages/:id` | Package view (plan, days, totals, change actions, confirm, export) |
| `/packages/:id/variants` | (G4) Cheapest / Fastest / Best-rated chooser |
| `/over-budget`, `/no-package` | Outcome pages (or inline states on `/`) carrying the last request |
| `/reservations` | Lookup by number |
| `/reservations/:number` | Reservation summary (read-only) or "not found" |
| `/credits` | Photo credits from `ATTRIBUTIONS.md` (required if photos shown) |

### 8.2 Deliverables
| ID | Deliverable | Acceptance criteria |
|---|---|---|
| **FE-1** | App shell: Vite + React, router, API client (`/api` base, dev proxy to `localhost:8000`), global error boundary, loading skeletons, toasts | No hard-coded host; failed network shows a retry message |
| **FE-2** | **Trip form (M1)** | 7 fields; dropdowns from `/api/meta`; dynamic child-age inputs (add/remove); date input limited to the data window; budget field with lakh grouping; inline validation + mapping of server `fields[]`; form empty on first load; submit disabled while loading |
| **FE-3** | **Outcome handling (M2/M8)** | `PACKAGE` → navigate to `/packages/:id`; `OVER_BUDGET` page: plain "not possible within your budget" statement, cheapest total + shortfall, **alternative cards** (each opens its draft package), "Increase budget to ₹X (+₹Y)" button, "Edit the trip"; `NO_PACKAGE` page with the reason text and "Edit the trip" |
| **FE-4** | **Package view (M4/M5)** | Header (route, dates, travelers); city-plan strip; total/budget/left-or-over bar with text + color; breakdown by category; day-by-day timeline in time order with event cards (flight, transfer, hotel, attraction) incl. times, quantity, price, photos; warning banner; **Export JSON** button; **Confirm** button |
| **FE-5** | **Change flows (M6)** | Hotel picker per city; flight picker per leg; add-attraction dialog per day (list + start-time choices); remove button per attraction; shows `APPLIED` (updated totals), `REFUSED` reason + violations, or `BUDGET_EXCEEDED` (message, cheaper options, and an explicit "Raise budget to ₹X and apply" button that resends with `raise_budget: true`); options that don't fit the budget are marked "needs +₹X"; disabled when `BOOKED` |
| **FE-6** | **Confirm & reservation (M7)** | Confirm dialog with total; success view with the 10-digit number (large, copy button, link to summary); lookup page; "Reservation not found" state; summary reuses the timeline, shows BOOKED badge |
| **FE-7** | **Export (M5)** | Button downloads `nomadgrid-trip-<id>.json` from the export endpoint |
| **FE-8** | **Stretch UI** | G2 `+₹X/−₹X` chips on options; G1 per-item warning badges and package warnings; G4 variant chooser; G3 city-plan chooser; S1 quick-request box; S2 conflict message; S3 rationale panel; credits page + footer link |
| **FE-9** | **Customer-friendly UX** | Implements everything in **§8.4**: plain language, icons/colors/photos/badges for instant recognition, sticky budget bar, edit drawers with price differences and "what else moves", highlight + undo after every change, friendly errors, responsive, accessible, empty/loading/error states, print-friendly itinerary. **Accepted only when the task-based UX tests in §8.4 pass** |
| **FE-10** | **Build & handoff** | `npm run build` outputs `frontend/dist` (consumed by the Dockerfile); `npm run dev` works against the running backend; lint passes; short `frontend/README.md` |
| **FE-11** | **Demo readiness** | Menon request works end-to-end by clicking only; smoke e2e test (optional Playwright) for build → change → confirm → lookup |

### 8.3 Frontend rules
- Show **exactly** what the backend returns for prices and times (no recomputation).
- After any change, replace local state with the returned package (single source of truth = backend).
- Never display a stack trace or raw error JSON; use `message` / `fields[]`.
- Until the backend is ready, develop against `docs/api-examples/*.json`.

### 8.4 Customer-friendly UX — design principles & edit experience [FE]
The user is a family planner, not a travel agent. **Anyone should be able to build, understand and change a holiday without help, in under two minutes.** How the UI *looks*, how easily things are *identified*, and how easily a package is *edited* are first-class requirements.

**Design principles**
| # | Principle | In practice |
|---|---|---|
| 1 | **One obvious next step** | Each screen has one primary button: "Build my holiday", "Confirm booking" |
| 2 | **Plain language, no jargon** | Never show catalog codes or enums (`PER_VEHICLE`, `AIRPORT_TAXI`, `area: null`). Say "Taxi from Narita Airport to your hotel · 1 taxi (up to 4 people) · ₹13,440". Codes only in a small grey "details" line |
| 3 | **Recognize at a glance** | Distinct icon + color per item type (flight, hotel, taxi/bus/train, attraction); a color per city used on the city strip, day headers and cards; photos for hotels and attractions; badges such as "Direct", "1 stop", "Free", "Family friendly", "Child ₹X" |
| 4 | **Money always visible** | Sticky bar: total · budget · amount left/over with a progress bar. Green = comfortable, amber = under 5% left, red = over. Color is never the only signal (always text too) |
| 5 | **Show consequences before the click** | Every option shows its price change ("+₹2,400"/"−₹1,360") and what else moves ("Your airport pickup moves to 12:10 pm"); buttons say exactly what happens ("Choose this hotel") |
| 6 | **Every edit is visible and reversible** | After a change the touched card is highlighted for a few seconds and a toast says what happened ("Hotel in Kyoto changed · Total ₹3,12,400 (−₹2,400)") with **Undo** |
| 7 | **Helpful, never blaming, errors** | Say what's wrong, why, and what to do: "Tokyo Disneyland is closed on 12 Apr. It's open on 13 Apr — add it there?" |
| 8 | **Progressive disclosure** | Day cards collapse to a one-line summary and expand for details; advanced details stay hidden until asked |
| 9 | **Forgiving** | Nothing lost on refresh (URL holds state); "Edit trip" always available; a clear review step before confirm |
| 10 | **Inclusive** | Mobile-first, tap targets ≥ 44 px, full keyboard use, screen-reader labels, WCAG-AA contrast |

**Visual design system:** neutral background with one brand accent; 6 accessible city colors; 16 px base type and a clear heading scale; 8 px spacing grid; rounded cards with subtle shadows; one icon set (e.g. Lucide). Money in Indian grouping (`₹3,50,000`). Dates like "Sat, 10 Apr". Times in **12-hour with am/pm** and a place label ("9:20 am Japan time" on arrival day). Loading text is honest ("Finding flights, hotels and things to do…"); every list has empty, loading and error states.

**Screen sketches**
Trip form:
```
┌───────────────────────────────────────────────────┐
│ NomadGrid · Build my holiday                      │
│ Flying from        [ Bengaluru        ▾ ]         │
│ Going to           [ Japan            ▾ ]         │
│ First day there    [ 10 Apr 2027 ]                │
│ Nights             [ − 6 + ]   → back home Fri 16 Apr │
│ Adults [ − 2 + ]   Children [ − 1 + ]             │
│   Child 1 age      [ 6 ▾ ]                        │
│ Total budget       ₹ [ 3,50,000 ]                 │
│            [ Build my holiday ]                   │
└───────────────────────────────────────────────────┘
```
Package page:
```
┌ Sticky ─ ₹3,12,400 of ₹3,50,000 · ₹37,600 left ▓▓▓▓▓▓▓▓░░ ─ [Export] [Confirm booking] ┐
│ ■ Tokyo · 3 nights  →  ■ Kyoto · 3 nights        [Edit trip] [Change cities]          │
│ ▾ Sat 10 Apr · Tokyo · Arrival day                                                     │
│   ✈ 9:20 am  Land at Narita · Direct · 7h 10m                    [Change flight]     │
│   🚕 11:30 am Taxi to your hotel · 1 taxi · ₹13,440                                    │
│   🏨 Ginza Pearl Hotel ★★★★ · Family room · 3 nights   [photo]   [Change hotel]       │
│   🎟 3:00 pm Senso-ji · Free                                      [Remove]            │
│   [ + Add something to do ]                                                            │
│ ▸ Sun 11 Apr · Tokyo · 2 sights                                                        │
```
Edit drawer (hotel):
```
┌ Change hotel in Kyoto ────────────────────────── ✕ ┐
│ Sort [Price ▾]   ☐ Family friendly  ☐ 4★ and up    │
│ ● CURRENT  Sakura Garden Hotel ★★★★ 8.7 · Higashiyama│
│            Family room · ₹8,120/night · ₹24,360     │
│ ○ Kyoto Hills Hotel ★★★★ 8.4      +₹2,464 [Choose] │
│ ○ Gion Corner Hotel ★★★ 7.8       −₹1,360 [Choose] │
│ ✕ Gion Moon Ryokan — sold out on 14 Apr  (greyed)  │
└─────────────────────────────────────────────────────┘
```
Over-budget page: a calm headline ("This trip doesn't fit ₹3,50,000 as planned"), the cheapest total, then **alternative cards** with a photo of the first city, what changed, the total and money left, and a prominent "Increase budget to ₹4,12,000 (+₹62,000)" button.

**How editing feels**
| To change… | Experience |
|---|---|
| A hotel | "Change hotel" on the hotel card → drawer; current choice pinned and marked; sort by price/stars/rating; filters; each option shows price difference and fit; unavailable options greyed with the reason |
| A flight | "Change flight" on the flight card → drawer with times, duration, stops, seats, price difference, and "what moves" note |
| Attractions | "+ Add something to do" on any day → list of what is open that day with "fits your day" start-time chips; "Remove" on every attraction card; conflicts explained in words |
| Cities | "Change cities" → cards for each valid plan with total and warnings ("rushed: 2 nights each") |
| Trip details | "Edit trip" → the form prefilled; a notice explains that rebuilding replaces manual edits |
| Over budget | A change that would exceed the budget explains the gap and offers cheaper options or "Raise budget to ₹X and apply" |

**UX acceptance tests (task-based "hallway test").** Ask 3 people who haven't seen the app to do these unaided. A task passes if at least 2 of 3 finish it within the time limit.
| # | Task | Limit |
|---|---|---|
| 1 | Build the Menon holiday from the form | 1 min |
| 2 | Say the total and how much budget is left | 10 s |
| 3 | Change the Kyoto hotel to a cheaper one | 30 s |
| 4 | Remove one attraction | 15 s |
| 5 | Add an attraction on a chosen day | 45 s |
| 6 | Explain why an over-budget request failed and pick an alternative | 30 s |
| 7 | Confirm, then find the reservation by its number | 1 min |
Failed tasks are logged (with the break-it findings) and the UI is revised before the cycle is pushed.

---

## 9. Non-functional requirements

| Category | Requirement |
|---|---|
| **Correctness** | Zero rule violations in emitted packages; validator gates every build and change; deterministic output for identical input |
| **Performance** | Typical build < 2 s, worst case < 5 s; change/option calls < 1 s; per-(city,dates,travelers) hotel results cached within a request |
| **Reliability / persistence** | Packages and reservations survive refresh and backend restart; transactional writes; idempotent confirm; unique reservation numbers via DB constraint |
| **Data integrity** | Catalog read-only; every price/time/availability from `data/`; hash test proves files untouched |
| **Architecture** | Backend owns all logic; frontend only renders API data; engine is pure functions over catalog data (testable without HTTP) |
| **Usability** | Specific error messages; every failure shows a next step; lakh-style INR; responsive; keyboard accessible; sufficient contrast |
| **Security** | Server-side validation; parameterized SQL; escape all rendered text; no secrets in repo; reservation lookup accepts digits only; container runs non-root |
| **Portability** | 1 command (`docker compose up --build`), documented no-Docker fallback (2 commands); Windows/macOS/Linux; no `node_modules`, venvs, or build output in the submission zip |
| **Maintainability** | Modules per §10; typed models; README (start commands, architecture, city rule, done, limitations); small commits (§13) |
| **Compliance** | No AI/LLM at runtime; photo credits shown when photos shown; feature code written during the event |
| **Observability** | Structured logs per build (plans tried, stage eliminations, chosen plan, timings); `/api/health` |
| **Testability** | Golden, table-driven, fuzz, restart-persistence and catalog-hash tests (§12) |

---

## 10. Architecture, repo layout & Docker

### 10.1 Stack (decided) and why
| Choice | Why |
|---|---|
| **Python 3.12** | The hard part is the rules engine: date/time arithmetic, joins across JSON, search over plans × flights × hotels. The standard library (`datetime`, `itertools`, `dataclasses`, `json`) covers it with no dependencies; readable for the live-explanation score; `pytest` for fuzzing; you know it |
| **FastAPI** | Pydantic request models give M1's per-field errors almost for free; auto `/docs` documents the contract for both teammates and the judges |
| **SQLite** | One file, no server, transactional, unique constraints for reservation numbers, survives restarts |
| **React + Vite** | Fits a multi-step flow with dialogs and live totals; the Node build runs inside Docker's multi-stage build so it never reaches the zip |
| **Docker Compose** | One-command start identical on any machine; catalog mounted read-only enforces "don't change data"; named volume proves restart persistence |

### 10.2 Repository layout
```
NomadGrid/
├─ PRD.md · README.md · Dockerfile · docker-compose.yml · docker-compose.dev.yml · .dockerignore · .gitattributes
├─ docs/api-examples/            # JSON fixtures for the frontend [BE]
├─ hackathon-problem-1-holiday-package/   # provided pack (read-only)
├─ backend/
│  ├─ requirements.txt
│  ├─ app/
│  │  ├─ main.py · __main__.py · config.py
│  │  ├─ api/        routes_meta · routes_packages · routes_reservations · schemas · errors
│  │  ├─ catalog/    loader · index
│  │  ├─ core/       timeutil · pricing · roomfit
│  │  ├─ engine/     cityplan · flights · hotels · transfers · attractions · builder · search · diagnostics · variants
│  │  ├─ changes/    options · apply · cascade
│  │  ├─ validator/  rules_* · validate
│  │  ├─ store/      db · repositories · reservation_numbers · inventory
│  │  ├─ export/     trip_format
│  │  └─ quickparse/ (S1)
│  └─ tests/         unit · golden · fuzz · api · persistence
└─ frontend/         # teammate's work: src/ · package.json · vite.config.ts
```

### 10.3 Docker & run
- **Start:** `docker compose up --build` → `http://localhost:8000`. **Fallback:** `pip install -r backend/requirements.txt` then `python -m app` (serves API + prebuilt `frontend/dist`); frontend dev: `npm install && npm run dev`.
- **One container, multi-stage Dockerfile:** stage 1 `node:24-alpine` builds the React app; stage 2 `python:3.12-slim` installs deps, copies `dist`, and FastAPI serves `/api/*`, `/images/*`, and the SPA (fallback to `index.html` for non-API routes).
- **Mounts:** catalog `./hackathon-problem-1-holiday-package/data:/app/data:ro`, images `…/images:/app/images:ro`; named volume `nomadgrid-db:/app/storage` for `nomadgrid.sqlite`.
- **Config via env:** `DATA_DIR`, `IMAGES_DIR`, `DB_PATH`, `PORT` (no secrets exist).
- **Hygiene:** `.dockerignore` excludes `node_modules`, `.venv`, `__pycache__`, `dist`, `.git`; `.gitattributes` forces LF; no shell entrypoint scripts (`CMD ["python","-m","app"]`).
- **Dev loop:** `docker-compose.dev.yml` mounts `backend/` and runs `uvicorn --reload`; Vite dev server runs separately with `/api` proxy.
- **Healthcheck:** Compose polls `GET /api/health`.
- **Tests in container:** `docker compose run --rm app pytest`.
- **Pinning:** Python 3.12 in the image (local machine runs 3.14).

---

## 11. Data traps the implementation must handle
| Trap | Handling |
|---|---|
| Kyoto has no airport (served by `KIX`); `ITM` serves nothing | Always match via `airports.serves_cities` |
| Arrival flights often leave the evening before (31 Mar → 1 Apr arrival is valid) | Match arrival by the **date part of `arrival_local`** |
| Local times in different zones | Use `duration_minutes`; never subtract departure/arrival |
| Service windows `24:00`, `00:30`, both ends inclusive | `timeutil` window logic with wrap |
| `area: null` transfers (KIX→Kyoto, DXB→Abu Dhabi, AUH bus) | Match `area == hotel.area or area is null` |
| Trains/buses depart on a frequency grid | `service_from + n·frequency ≤ service_until` |
| Children need seats; `seats_left` as low as 1–2 | `seats_left ≥ adults + children` (FL-403 fails for the Menons) |
| Rooms with `max_children = 0` | Use the room-fit formulas; capsule hotel (`SINGLE` only) can never fit a family with a child |
| 61 sold-out room-nights | Check `rooms_left ≥ k` every night; check-out day isn't a night |
| Attraction closures | Edo Craft Museum closed every date from 10 Apr; Disneyland & Heritage Village closed 12 Apr; Museum of the Future closed 14 Apr; Tsukiji closed Wed & Sun; Global Village opens 16:00 |
| Nara attractions | Excluded (no hotels in Nara) |
| `child_price` absent vs `0` | Fall back to adult price only when the field is absent; `0` is a real free price |
| Door-to-door vs station transfers between cities | City taxis optional; not added |
| Same flight number repeats on many dates | Key on `flight_id` |
| Windows past midnight for airport shuttles | Pickup datetime may fall on the next calendar date; handle in `timeutil` |

---

## 12. Testing strategy [BE]
| Layer | What | Notes |
|---|---|---|
| Unit | `timeutil` (24:00, wrap, inclusive ends), room-fit (all room types × traveler mixes), pricing (each formula, absent vs zero child price), reservation-number format | Fast, run on every commit |
| Rule tests | One test per validator rule ID with a crafted failing package | Proves the validator catches what it should |
| Golden | Menon request → validator-clean package within budget; expected flights set {FL-401/FL-405/FL-740 in, FL-412/FL-411 out}; FL-403 never used | SC1 |
| Table-driven API | Invalid fields, out-of-window, impossible (e.g. 12 travelers), over-budget, wrong reservation number | SC3 |
| Fuzz | Loop over departure cities × countries × start dates 1–20 Apr × nights 3–10 × traveler mixes (1–4 adults, 0–3 children, ages 0–17); every `PACKAGE` must have **zero** validator violations; log counts of each outcome | SC2 |
| Change tests | Each op: success path, each refusal code, totals updated, locked after confirm | M6 |
| Persistence | Build → confirm → rebuild app instance on same DB → lookup returns identical snapshot | SC4 |
| Catalog immutability | SHA-256 of `data/` files before and after a test run | Data integrity |
| Export | Export → re-import into validator → zero violations | SC5 |
| Docker smoke | `docker compose up --build`, hit `/api/health` and one build call | SC6 |
| **Break-it sessions** | Adversarial testing after **every feature cycle** (see §12.1) | Findings logged and turned into regression tests |

### 12.1 Break-it testing — try to break the product, and learn from it
The goal of testing is to **find failures**, not to confirm success. After each feature cycle (before pushing) run a deliberate attack session, then record and learn from what broke.

**Process**
1. **Attack:** for the feature just built, try to make it fail using the checklist below plus anything creative.
2. **Log:** every failure goes into `docs/break-it-log.md`: *date · feature · what was tried · what happened · root cause · fix · regression test added*.
3. **Fix & lock in:** fix the root cause (not just the symptom) and add a regression test that fails without the fix.
4. **Learn:** if a failure reveals a *class* of bug (e.g. every `24:00` boundary), add a unit-test table for the whole class and, if the validator missed it, add or tighten a validator rule.
5. **Validator mutation test:** take a valid package, corrupt one thing at a time (shift a flight date, change a price by ₹1, swap a room for one that doesn't fit, move an attraction into a closed hour, remove the airport transfer, double an attraction) and assert the validator reports exactly the expected rule ID. A missed mutation is a validator bug.
6. **Unfixed findings** become entries in README "Known limitations" and the PRD risks table.
7. Push only when the cycle's tests pass **and** its break-it session is logged.

**Attack checklist**
| Area | Try |
|---|---|
| Request fields | Missing fields, extra fields, wrong types (`"six"`, `6.5`, `null`), negative/zero/huge numbers (budget 1, 10¹², adults 0, adults 50, 11 children), child ages −1/18/200, nights 2/11/0, impossible dates (30 Feb), start 31 Mar / 20 Apr / 21 Apr, empty/unicode/very long strings, SQL- and HTML-like strings |
| Impossible requests | 12 travelers (seats max 9), a departure/country with no flights on that date, dates where all rooms are sold out, 3 nights with 2 cities requested |
| Budget | Budget exactly equal to the cheapest total (must pass), ₹1 less (must be `OVER_BUDGET`), budget so tiny nothing fits (alternatives empty, message honest), alternative that is secretly over budget, raise-budget flow rebuilds original request |
| Time edges | Landing 23:30 (+60 crosses midnight), flights departing 31 Mar, return flight at 00:30, shuttle window `06:00–00:30`, `24:00` service end, pickup exactly at window start/end, departure − 180 exactly on the boundary, train frequency grid, arrival at 21:30 (`FL-405`) |
| Capacity | Rooms: 1–4 adults × 0–3 children × all room types; capsule/SINGLE-only hotels; sold-out nights in the middle of a stay; `seats_left` exactly equal to travelers |
| Attractions | Add on last day, closed date (Disneyland 12 Apr), Edo Craft Museum, Nara ids, wrong city, overlapping times, same attraction twice, visit crossing closing time, free (`0`) child price vs missing child price, add to a `BOOKED` package |
| Changes | Change to the same hotel/flight (no-op), to a flight with too few seats, wrong leg, stale/unknown ids, remove unknown item, change flight so transfer becomes infeasible, change that exceeds budget, `raise_budget` without consent flag, rapid repeated changes, change after confirm |
| Confirm & reservations | Confirm twice (same number), confirm two different packages at once (distinct numbers), concurrent confirms (race), lookup with 9/11 digits, letters, leading zeros, spaces, SQL strings, restart between confirm and lookup, deleted DB file, corrupted DB row |
| Data & platform | Tampered catalog file (hash test must fail), missing image, Docker volume removed, port in use, cold `docker compose up --build`, Windows line endings |
| Property/fuzz | Random requests across the whole space; every `PACKAGE` must validate; log outcome counts so a sudden jump in `NO_PACKAGE` flags a regression |

---

## 13. Git & collaboration workflow [BOTH]
- **Commit early and often** — after every meaningful chunk (a module, a passing test group, a doc update) so nothing is lost.
- **Commit messages: at most 2 lines, a plain description of the change only.** No attribution or co-author lines. Example: `Add room fit and pricing helpers with tests`.
- **Do not push after every commit. Push only when a cycle of features is done** — i.e. the feature group is complete, its tests pass, and its break-it session (§12.1) is logged. Commit locally as often as needed in between. Remote is `origin` → `https://github.com/sriram36/NomadGrid.git`, branch `main`. (The hackathon asks for roughly hourly pushes, so size feature cycles to finish about every 1–1.5 h. Never push half-finished or untested work just to hit the clock.)
- **Separate folders** (`backend/` vs `frontend/`) so the two of you rarely conflict; pull/rebase before pushing.
- **API changes** are made in §7 first, announced to the other person, then implemented.
- **Feature code is written during the event** (judges read Git history); provided data and docs are the only pre-existing content.
- Never commit: `node_modules`, venvs, build output, `*.sqlite`, `.env`, zips (already in `.gitignore`).

## 14. Delivery plan (≈ 9–10 h) — *original plan; actual status in §0*

| Phase | Time | **[BE] You (+ Claude)** | **[FE] Teammate** | Exit check |
|---|---|---|---|---|
| 0. Setup & contract | 0:00–0:45 | BE-01 skeleton, Dockerfile/compose, `/api/health`, `/api/meta`; commit `docs/api-examples`; freeze §7 | FE-1 shell + router + API client; start FE-2 using fixtures | `docker compose up --build` serves the form |
| 1. Core engine | 0:45–3:30 | BE-02 catalog loader · BE-03 `timeutil` · BE-04 pricing/room-fit · BE-05 request validation · BE-06 city plans · BE-07 flights · BE-08 hotels · BE-09 airport transfers · BE-10 intercity · BE-11 attractions | FE-2 form complete · FE-3 outcome pages · FE-4 package view on fixtures | Menon builds in a test |
| 2. Validator & API | 3:30–4:45 | BE-12 builder/search/diagnostics (M2/M8) · BE-13 validator · BE-14 persistence + packages/export API | Switch from fixtures to live API; FE-7 export | Validator passes Menon; outcomes correct |
| 3. Changes & booking | 4:45–6:30 | BE-15 confirm/reservations · BE-16 options/apply (M6) | FE-5 change flows · FE-6 confirm/reservation | Full demo flow works incl. restart |
| 4. Hardening | 6:30–7:30 | BE-17 golden + fuzz, fix every violation | FE-9 UX polish, error states, responsive | SC1–SC5 green |
| 5. Stretch | 7:30–9:00 | G1 → G2 → G4 → G3 → S2 → S1 → S3 (as time allows) | FE-8 matching UI | Each merged only with tests green |
| 6. Freeze | 9:00–9:45 | BE-19 README, zip hygiene, Docker cold-start rehearsal | FE-10/11 build + demo e2e | Clean-machine start in 1 command |

**Backend task index:** BE-01 skeleton/Docker · BE-02 catalog · BE-03 timeutil · BE-04 pricing/room-fit · BE-05 request validation · BE-06 city plans · BE-07 flights · BE-08 hotels · BE-09 airport transfers · BE-10 intercity · BE-11 attractions · BE-12 builder/search/diagnostics · BE-13 validator · BE-14 storage/API/export · BE-15 confirm/reservations · BE-16 changes · BE-17 tests (golden/fuzz) · BE-18 stretch (G1,G2,G4,G3,S2,S1,S3) · BE-19 README/packaging.

**Demo script (4 min):** empty form → Menon request → package, day plan, total vs budget → change hotel → change flight (re-validation visible) → add/remove an attraction → export JSON → confirm → open reservation by number. Prepare for judge inputs: UAE, Delhi departure, tiny budget, out-of-window dates, invalid input, wrong reservation number.

**Definition of done (per feature):** code + tests passing + validator clean + break-it session run and findings logged (§12.1) + noted in README + committed. A feature cycle is pushed only when every feature in it meets this.

**README checklist (statement §9) — `README.md` must contain:** (1) how to start the app: `docker compose up --build` plus the no-Docker fallback; (2) the architecture (diagram + module list from §10); (3) **our city rule** (§5.1 M2, §6.3, §6.1A); (4) what is finished (Must/Good/Stretch checklist); (5) known limitations (from the break-it log and open risks). The zip contains source, `README.md`, setup scripts, `Dockerfile` and compose files only — no `node_modules`, virtual environments, build output or keys.

## 15. Future plans (post-hackathon)
**Near term:** live supplier inventory and pricing; real booking, payments, cancellations/refunds, hold-and-expire; accounts and saved trips; share link; PDF/email itinerary; more countries, departure cities and cabins; multi-currency and localization.
**Planning intelligence:** constraint-solver optimizer (ILP/CP-SAT) with preferences (pace, interests, kids/seniors/accessibility, hotel area); real inter-attraction travel times via maps/routing; crowd/season/weather-aware planning; multiple room types per city and mixed rooms; check-in/out time enforcement; day trips (e.g., Nara), open-jaw trips, multi-stop circuits, flexible-date lowest-fare search; ML-based recommendations (allowed outside the hackathon's no-AI rule).
**Platform:** mobile apps and offline itinerary; push/email change alerts; group planning with voting and split payments; admin console for catalog and inventory; analytics on drop-off and popular plans; travel extras (visas, insurance, eSIM, lounges, local events).

## 16. Risks & mitigations
| Risk | Impact | Mitigation |
|---|---|---|
| Timing/window edge cases (24:00, wrap, frequency grid) | Rule violations | `timeutil` unit tests; independent validator |
| Search blow-up | Slow builds | Decompose per city; prune early; cache hotel results |
| Over-investing in stretch before core is right | Lost score | Hard gate: SC1–SC5 first |
| Builder and validator share a bug | False confidence | Validator written independently from raw catalog; fuzz |
| Unseen judge inputs (UAE, odd mixes) | Lost correctness points | Fuzz across full request space; manual UAE/Delhi runs |
| Live-code-change question | Lost points | Small, readable functions; both explain every module |
| Docker fails or is slow at the demo | Demo can't start | Pre-build image; no-Docker fallback; rehearse cold start |
| Edited package fails judges' checker on attraction count | Lost points | UI warning; ask organizers whether 1–2/day is enforced after edits |
| Backend/frontend drift | Integration pain | Frozen contract in §7, fixtures in `docs/api-examples`, announce changes |

## 17. Open questions & assumptions
| # | Question | Default we use |
|---|---|---|
| Q1 | Stack | **Decided:** Python + FastAPI + SQLite · React + Vite · Docker Compose (one container, no-Docker fallback) |
| Q2 | Default package city preference | **Decided:** constraints first (hard rules, then budget), then time-based suggestion per §6.1A (`k* = clamp(⌊N/3⌋,1,#cities)`; plans within 120 min of the best transit time count as time-equal; then highest quality score (§6.10A); then most usable ground time); traveler can edit and the app raises warnings. *To confirm: is the 120-minute tolerance acceptable, and does "time" mean T1–T3 as defined in §6.1A?* |
| Q3 | Attraction count after edits | **Decided:** 1–2 per full day applies to the first package only; edits are not count-capped and the **traveler's choices take priority** (pinned items, §6.12); UI warns on 0 or >2. No need to ask the organizers |
| Q4 | `city` on the flight items | **Decided (revised):** the data dictionary says "For a flight: the arrival city", so both flight items carry the city of their arrival airport (the return flight arrives in the home city, e.g. Bengaluru). This replaces the earlier "last trip city" reading. What stays from the original decision: only plans whose last city has a valid return flight are ever suggested (§6.3) |
| Q5 | Return pickup on the last day only | **Decided:** yes (strict reading of "no hotel night on the last day") |
| Q6 | Buffer between attractions / arrival-day settling | 30 min each, **for system-suggested visits only**; user edits and the validator use only the statement's rules (§6.8) |
| Q7 | `child_friendly: false` attractions when children travel | Soft preference only |
| Q8 | Traveler name | **Not a form field** (the statement's form has 7 fields). The API accepts an optional `traveler_name` (not sent by the UI); the export uses `"Traveler"` by default |
| Q9 | Reservation number format | 10 digits, first digit 1–9, random, unique |
| Q10 | Fastest/Best-rated when none within budget | Omit with an explanatory note |
| Q11 | Day activity window | 08:30–21:30 for **system-suggested** visits only; user-added visits may use any time inside the attraction's opening hours |
| Q12 | Pushing to GitHub | **Decided:** commit after every chunk; push only when a cycle of features is done (tests green + break-it session logged) |
| Q13 | Edit that pushes the total over budget | **Decided:** budget comes first. The edit is **not applied**; response `BUDGET_EXCEEDED` with cheaper options and an explicit "raise budget and apply" choice. Hard-rule breaks are `REFUSED` |
| Q14 | Over-budget request | **Decided:** say the trip isn't possible as requested, show the cheapest total, offer fully built within-budget alternatives (drop a city, fewer nights, shift date, combinations) and a raise-budget option |
| Q15 | Default package: cheapest or best? | **Decided:** the **best recommended package built near the budget** (§6.10A) — a ₹4,00,000 budget gets a ~₹3.6–4.0 lakh holiday, not a ₹2,00,000 one. Cheapest stays available as a variant (G4) and for the over-budget check. *Open detail: the quality-score weights are my starting proposal; adjust after trying real budgets* |
| Q16 | User choices vs automatic changes | **Decided:** the traveler's choices take priority; automatic changes never silently remove them (`PINNED_CONFLICT`, §6.12) |

---

## Appendix A — Menon golden case facts (BLR → Japan, 10 → 16 Apr 2027)
| Leg | Flights on the date | Notes |
|---|---|---|
| Arrival (10 Apr local) | `FL-401` BLR→NRT dep 9 Apr 23:50, lands 10:30, ₹25,200/seat, 9 seats · `FL-405` BLR→NRT dep 10 Apr 06:30, lands 21:30, ₹23,940, 9 seats · `FL-740` BLR→KIX dep 9 Apr 21:40, lands 09:20, ₹34,440, 5 seats · ~~`FL-403` BLR→HND~~ lands 08:30, ₹21,420 but **2 seats < 3 travelers** | `FL-405` lands 21:30 → earliest pickup 22:30; NRT taxis run until 23:00 (OK), NRT bus until 22:00 (not OK); no arrival-day attractions |
| Return (16 Apr local) | `FL-412` HND→BLR dep 11:00, ₹26,880, 9 seats (last city must be **Tokyo**) · `FL-411` KIX→BLR dep 12:00, ₹26,040, 9 seats (last city **Osaka or Kyoto**) | Reach airport ≥ 180 min before departure, e.g. FL-412 → be at HND by 08:00 |
- Seat cost examples (×3 travelers): FL-401 ₹75,600 · FL-405 ₹71,820 · FL-740 ₹1,03,320 · FL-412 ₹80,640 · FL-411 ₹78,120.
- Family room: 2 adults + 1 child → 2 TWIN rooms (`max_children 0`) or 1 FAMILY room (`max_adults 2, max_children 2`) or 1 FAMILY_SUITE; capsule (SINGLE-only) hotels never fit.
- Transfers: 3 travelers → 1 taxi (`max_passengers 4`) for PER_VEHICLE; buses charge 2 adults + 1 child price.

## Appendix B — Glossary
**Arrival day** day 0, flight lands · **Change day** day the traveler moves to the next city · **Full day** neither arrival, change, nor last day · **Last day** return flight day, no hotel night · **Night** the date you sleep there (check-out day not a night) · **Base cost** flights + hotels + transfers + minimum attractions · **Variant** Default / Cheapest / Fastest / Best-rated package · **Effective availability** catalog `seats_left`/`rooms_left` minus our own confirmed usage (S2).
