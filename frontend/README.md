# normad-grid ✈️

**normad-grid** is an international holiday package builder web application built with **React (Vite + JavaScript)**, **Tailwind CSS v4**, and **Lucide Icons**. It generates, customizes, validates, and books multi-city holiday packages complying 100% with all Problem 1 travel rules.

---

## 🚀 Quick Start (1 Command)

```bash
cd frontend
npm install
npm run dev
```

Open your browser at `http://localhost:5173`.

To build and preview production assets:
```bash
npm run build
npm run preview
```

---

## 🌟 Feature Checklist (All 8 Must-Have Requirements Implemented)

### 1. M1 — 7-Field Trip Request Form (`src/components/RequestForm.jsx`)
- **Direct landing view:** Opens directly to the 7-field builder without any blocking login wall.
- **7 Traveler Fields:**
  1. Departure City (`Bengaluru`, `Mumbai`, `Delhi`, `Hyderabad`, `Chennai`)
  2. Destination Country (`Japan`, `United Arab Emirates`)
  3. Holiday Start Date (`min="2027-04-01"` to `max="2027-04-17"`)
  4. Number of Nights (`min="3"` to `max="10"`)
  5. Adults Count (`min="1"`)
  6. Children Count (`min="0"`) — dynamically renders an age input (`0–17`) for each child added
  7. Total Budget in INR (`min="1"`)
- **Quick-Fill Buttons:**
  - `Fill Sample Trip`: Pre-fills the Menon family trip (Bengaluru → Japan, 10 Apr 2027, 6 nights, 2 adults, 1 child aged 6, ₹3,50,000 budget).
  - `Test Over-Budget`: Tests budget constraint warning (₹1,20,000 budget).
  - `Test Impossible Trip`: Tests rule cutoff and constraint violation explanations.
- **Inline Error Feedback:** Displays clear red validation messages for dates, durations, capacities, and budgets.

### 2. M2 & M3 — Complete Package Generation & Rule Enforcement (`src/data/mockTripData.js`)
- Generates end-to-end multi-city itineraries:
  - Arrival flight from departure city landing on holiday start date
  - Return flight on the last day back to India
  - Airport ground transfers (satisfying the 60-minute post-landing and 180-minute pre-departure buffers)
  - Inter-city bullet trains / transfers on city-change days
  - Hotels & room capacity math: $k$ rooms fit travelers if $\text{adults} \le k \times \text{max\_adults}$, $\text{adults} + \text{children} \le k \times (\text{max\_adults} + \text{max\_children})$, and $\text{adults} \ge k$, with verified availability
  - Non-overlapping daily attractions fitting within operating hours
- **Impossible Trip State:** Explains exact conflict reasons when inputs cannot form a valid package (e.g. Hyderabad route absence, return flight exceeding 20 April 2027).

### 3. M4 — Chronological Day-by-Day Plan (`src/components/Timeline.jsx`)
- Groups the itinerary day-by-day (`Day 1` through `Day N+1`).
- Strict chronological order with connector lines and semantic color coding:
  - 🛫 **Flights:** Sky / Blue (`bg-sky-50 text-sky-700 border-sky-200`)
  - 🚗 **Transfers:** Amber / Orange (`bg-amber-50 text-amber-700 border-amber-200`)
  - 🏨 **Hotels:** Indigo / Purple (`bg-indigo-50 text-indigo-700 border-indigo-200`)
  - ⛩️ **Attractions:** Emerald / Teal (`bg-emerald-50 text-emerald-700 border-emerald-200`)
- Itemized times, durations, quantities, and INR prices.

### 4. M5 — Total Cost, Budget Tracker & JSON Export (`src/components/BudgetSidebar.jsx`)
- Sticky sidebar with itemized subtotals: Flights, Hotels, Ground Transfers, Sightseeing.
- Real-time comparison against budget with green (`₹XX,XXX Remaining`) or red (`₹XX,XXX Over Budget`) badges.
- **Export JSON:** 1-click download of `normad-grid-package.json` conforming strictly to `DATA_DICTIONARY.md` (`country`, `status`, `booking.reference`, `items` with `room_id`, `total_price_inr`).

### 5. M6 — Customize Package with Live Rule Re-Validation (`src/components/SwapModal.jsx`)
- Interactive customization options:
  - `"Change Flight"` on flight cards
  - `"Change Hotel"` on hotel cards
  - `"+ Add Attraction"` and `"Remove"` on sightseeing items
- **Live Rule Re-validation:**
  - If valid: updates the timeline and recalculates total price immediately.
  - If invalid: rejects the edit, preserves existing valid package, and displays a prominent red alert explaining the conflict (e.g., buffer violation, room capacity mismatch, or sightseeing overlap).

### 6. M7 — Confirm Booking & Persistent 10-Digit Reservation Lookup (`src/components/Navbar.jsx` & `BudgetSidebar.jsx`)
- **"Confirm & Book"**: Generates a unique 10-digit numeric reservation number (e.g., `8492017463`), updates package status to `"BOOKED"`, and persists it in `localStorage` under `normad_bookings`.
- **Navbar Lookup Bar:** Entering a valid 10-digit reservation number instantly reopens that full itinerary; unknown numbers display a clear `"Reservation not found"` alert.
- **Confirmation Page:** After booking, a dedicated page shows the 10-digit reservation number with a copy button.

### 7. M8 — Insufficient Budget Handling (`src/App.jsx`)
- When a valid package exists but exceeds target budget, normad-grid displays a prominent warning banner stating no package fits the budget, showing the cheapest compliant total, and suggesting concrete changes (e.g., increase budget by ₹XX,XXX or reduce duration by 1 night).

---

## 🎨 Technology Stack
- **Framework:** React 19 + Vite 6
- **Styling:** Tailwind CSS v4 (using `@import "tailwindcss";` and `@tailwindcss/vite`)
- **Icons:** Lucide React
- **Persistence:** Browser `localStorage` (`normad_bookings`, `normad_users`, `normad_current_user`)
- **Catalog Data:** Bundled from `destinations.json`, `airports.json`, `flights.json`, `hotels.json`, `rooms.json`, `availability.json`, `transfers.json`, `attractions.json`.
