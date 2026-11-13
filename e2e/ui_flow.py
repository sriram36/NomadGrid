"""End-to-end test of the real UI against the real backend, in a real browser (Edge via Playwright).

    1. start the app:      docker compose up --build        (or: cd backend && python -m app)
    2. run this test:      python e2e/ui_flow.py [http://localhost:8000]

It walks the whole journey, prints PASS/FAIL for every step, saves screenshots to e2e/screens/ and fails on any
browser console error or server error seen on the way.
"""
import re
import sys
import traceback
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"
SHOTS = Path(__file__).parent / "screens"
SHOTS.mkdir(exist_ok=True)
results = []
problems = []          # console errors, JS exceptions and unexpected HTTP errors seen anywhere
EXPECTED_HTTP = {      # errors this test provokes on purpose
    (404, "/api/packages/pkg_doesnotexist"), (404, "/api/reservations/0000000000"), (422, "/api/packages"),
}


def on_response(r):
    path = "/" + r.url.split("/", 3)[-1]
    if r.status >= 400 and (r.status, path.split("?")[0]) not in EXPECTED_HTTP:
        problems.append(f"HTTP {r.status} {path}")


def step(name):
    class Ctx:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            ok = exc_type is None
            results.append((name, ok))
            print(("PASS  " if ok else "FAIL  ") + name)
            if not ok:
                print("      " + "".join(traceback.format_exception_only(exc_type, exc)).strip().replace("\n", "\n      "))
            return True        # keep going: report every failure, not just the first
    return Ctx()


def snap(page: Page, name: str):
    page.screenshot(path=str(SHOTS / f"{name}.png"), full_page=True)


def total_text(page: Page) -> str:
    return page.locator("span.text-2xl.font-black").first.inner_text()


def rupees(text: str) -> int:
    return int(re.sub(r"[^\d]", "", text))


def field(page: Page, label: str):
    """The select/input that follows a form label (the form has no ids, so we find it by its visible label)."""
    return page.locator(f"xpath=//label[contains(., '{label}')]/following::*[self::select or self::input][1]")


def search(page: Page):
    page.get_by_role("button", name="Search Holiday Packages").click()


def menon(page: Page):
    page.get_by_role("button", name=re.compile("Menon Family Sample")).click()


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="msedge", headless=True)
        ctx = browser.new_context(viewport={"width": 1400, "height": 1000})
        page = ctx.new_page()
        page.on("console", lambda m: problems.append(f"console error: {m.text}")
                if m.type == "error" and not m.text.startswith("Failed to load resource") else None)
        page.on("pageerror", lambda e: problems.append(f"JS exception: {e} | {str(getattr(e, 'stack', ''))[:600]}"))
        page.on("response", on_response)

        # ---------------------------------------------------------------- the form
        with step("home page opens with an EMPTY form and dropdowns from the backend"):
            page.goto(BASE)
            page.get_by_text("Find your next holiday package").wait_for()
            page.wait_for_function("document.querySelector('select').options.length > 1")
            assert field(page, "1. Departure City").input_value() == ""
            assert field(page, "4. Number of Nights").input_value() == ""
            cities = field(page, "1. Departure City").locator("option").all_inner_texts()
            assert any("Bengaluru" in c for c in cities) and not any("Hyderabad" in c for c in cities), cities
            snap(page, "01_home")

        with step("a field the traveler left empty is flagged before anything is sent"):
            search(page)
            assert page.get_by_text("Please select a departure city in India.").is_visible()

        with step("the backend's own message shows next to the field (nights = 2)"):
            menon(page)
            field(page, "4. Number of Nights").fill("2")
            search(page)
            page.get_by_text("Nights must be a whole number between 3 and 10.").wait_for()

        with step("the plain-words request bar is gone; the Menon sample fills the form"):
            page.goto(BASE)
            assert page.get_by_text("Or just type your trip").count() == 0
            assert page.get_by_label("Describe your trip in plain words").count() == 0
            menon(page)
            assert field(page, "1. Departure City").input_value() == "Bengaluru"
            assert field(page, "2. Destination Country").input_value() == "Japan"
            assert field(page, "7. Total Budget").input_value() == "350000"
            assert field(page, "Child #1 Age").input_value() == "6"
            snap(page, "02_menon_sample")

        # ---------------------------------------------------------------- build the Menon holiday
        with step("Menon family: a package is built and opens at /packages/<id>"):
            search(page)
            page.wait_for_url(re.compile(r"/packages/pkg_"))
            page.get_by_text("Why this plan").first.wait_for()
            plan = page.locator("[data-testid=city-plan]").inner_text()
            assert "N)" in plan, plan
            total = rupees(total_text(page))
            assert 200000 < total <= 350000, total
            assert page.get_by_text("Remaining (Within Budget)").is_visible()
            snap(page, "03_package")
        pkg_url = page.url
        first_total = rupees(total_text(page))

        with step("day-by-day plan: a card for each of the 7 days"):
            days = page.locator("span", has_text=re.compile(r"^Day \d+$")).all_inner_texts()
            assert len(days) >= 7, days
            assert page.get_by_text("Day-by-Day Master Itinerary").is_visible()

        with step("'Why this plan' explains the choice with real numbers"):
            why = page.locator("[data-testid=why-panel]").inner_text()
            assert re.search(r"\(\d+%\)", why) and "budget" in why, why

        # ---------------------------------------------------------------- change things (M6, G2)
        with step("change hotel: real options with price differences; the cheapest applies and the total drops"):
            page.get_by_role("button", name="Change Room / Hotel").first.click()
            dlg = page.get_by_role("dialog")
            dlg.locator("[data-testid=options-list] li").first.wait_for()
            assert dlg.get_by_text("Current").first.is_visible()
            assert dlg.locator("text=/[+−]₹/").count() >= 3                    # price differences
            snap(page, "04_hotel_options")
            dlg.locator('button:has-text("Select"):not([disabled])').first.click()      # the first choice that is available
            page.get_by_text(re.compile(r"Hotel in .* changed to")).wait_for()
            assert page.get_by_role("dialog").count() == 0
            assert rupees(total_text(page)) < first_total

        with step("undo last change brings the old total back"):
            page.get_by_role("button", name="Undo Last Change").click()
            page.get_by_text("Your last change was undone.").wait_for()
            assert rupees(total_text(page)) == first_total

        with step("change flight: options listed with seats and reasons for unavailable ones"):
            page.get_by_role("button", name="Change Flight").first.click()
            dlg = page.get_by_role("dialog")
            dlg.locator("[data-testid=options-list] li").first.wait_for()
            assert dlg.get_by_text(re.compile("Seats left")).first.is_visible()
            snap(page, "05_flight_options")
            dlg.get_by_role("button", name="Close").last.click()

        with step("add a sight on a full day, then remove it"):
            added = False
            for i in range(6):                         # find a day that still has something free to add
                page.get_by_role("button", name=re.compile("Add Attraction")).nth(i).click()
                dlg = page.get_by_role("dialog")
                dlg.get_by_text(re.compile("Adding Sightseeing for Date")).wait_for()
                page.wait_for_function("!document.querySelector('[role=dialog] .animate-spin')")
                if dlg.locator("[data-testid=options-list] li").count():
                    snap(page, "05b_add_sight")
                    dlg.get_by_role("button", name="Add").first.click()
                    page.get_by_text(re.compile(r"^Added ")).wait_for()
                    added = True
                    break
                assert dlg.get_by_text("Nothing else is available here.").is_visible()   # an honest empty list
                dlg.get_by_role("button", name="Close").last.click()
            assert added, "no day offered anything to add"
            page.get_by_role("button", name=re.compile("^Remove$")).first.click()
            page.get_by_text(re.compile(r"removed", re.I)).first.wait_for()

        with step("change cities: plans compared with prices; switching to a Tokyo plan works"):
            page.get_by_role("button", name="Compare Other City Plans").click()
            dlg = page.get_by_role("dialog")
            dlg.locator("[data-testid=options-list] li").first.wait_for()
            assert dlg.locator("li").count() >= 8
            snap(page, "06_city_plans")
            dlg.locator("li", has_text="Tokyo").get_by_role("button", name="Use this plan").first.click()
            page.wait_for_timeout(1500)
            if page.get_by_text("This would undo a choice you made").count():
                snap(page, "06b_pinned_conflict")
                page.get_by_role("button", name="Keep my current plan").click()
                assert page.get_by_role("dialog").is_visible()
                dlg.locator("li", has_text="Tokyo").get_by_role("button", name="Use this plan").first.click()
                page.get_by_text("This would undo a choice you made").wait_for()
                page.get_by_role("button", name="Apply anyway and let those go").click()
            page.get_by_text(re.compile("City plan changed to")).wait_for()
            assert "Tokyo" in page.locator("[data-testid=city-plan]").inner_text()

        with step("refreshing the page keeps the holiday (state lives in the URL and on the server)"):
            url_before = page.url
            page.reload()
            page.get_by_text("Why this plan").first.wait_for()
            assert page.url == url_before
            assert "Tokyo" in page.locator("[data-testid=city-plan]").inner_text()

        # ---------------------------------------------------------------- confirm (M7)
        with step("confirm gives a 10-digit number and the holiday becomes read-only"):
            page.get_by_role("button", name=re.compile("Confirm & Book Holiday")).click()
            page.wait_for_url(re.compile(r"/reservations/\d{10}"))
            page.get_by_text("Your holiday is confirmed!").wait_for()
            number = page.locator("[data-testid=reservation-number]").inner_text().strip()
            assert re.fullmatch(r"[1-9]\d{9}", number), number
            snap(page, "07_confirmed")
            page.get_by_role("link", name=re.compile("View my itinerary")).click()
            page.wait_for_url(re.compile(r"/packages/pkg_"))
            page.get_by_text("RESERVATION CONFIRMED").wait_for()
            assert page.get_by_role("button", name="Change Flight").count() == 0
            assert page.get_by_role("button", name=re.compile("Confirm & Book Holiday")).count() == 0
            snap(page, "07_booked")
        state = {"number": number, "url": page.url}

        with step("after a refresh the booking is still there"):
            page.reload()
            page.get_by_text("RESERVATION CONFIRMED").wait_for()
            assert page.locator("span.tracking-widest").inner_text().strip() == state["number"]
            page.goto(BASE + "/reservations/" + state["number"])
            page.get_by_text("Your holiday is confirmed!").wait_for()
            assert page.locator("[data-testid=reservation-number]").inner_text().strip() == state["number"]

        with step("lookup by reservation number from the top bar; a wrong number says 'not found'"):
            page.goto(BASE)
            box = page.get_by_placeholder("Find 10-digit Reservation ID...").first
            box.fill("0000000000")
            page.get_by_role("button", name="Find Trip").click()
            page.get_by_text(re.compile("not found in records")).first.wait_for()
            box.fill(state["number"])
            page.get_by_role("button", name="Find Trip").click()
            page.wait_for_url(re.compile(r"/packages/pkg_"))
            page.get_by_text("RESERVATION CONFIRMED").wait_for()

        with step("the top bar no longer has a My Bookings link"):
            assert page.get_by_role("link", name=re.compile("My Bookings")).count() == 0

        with step("export link downloads the shared-format JSON with the booking reference"):
            href = page.get_by_role("link", name="Export Package JSON").get_attribute("href")
            data = ctx.request.get(BASE + href).json()
            assert data["status"] == "BOOKED" and data["country"] == "Japan"
            assert all(i["booking"]["reference"] == state["number"] for i in data["items"])

        # ---------------------------------------------------------------- budget too small (M8)
        with step("budget too small: honest message, cheapest total, alternatives that fit, raise-budget"):
            page.goto(BASE)
            menon(page)
            field(page, "7. Total Budget").fill("200000")
            search(page)
            page.locator("[data-testid=over-budget]").wait_for()
            assert "not possible within" in page.locator("[data-testid=over-budget]").inner_text()
            snap(page, "09_over_budget")
            alts = page.locator("[data-testid=alternative]")
            if alts.count():
                alts.first.get_by_role("button", name=re.compile("Open this holiday")).click()
                page.wait_for_url(re.compile(r"/packages/pkg_"))
                assert rupees(total_text(page)) <= 200000
                page.go_back()
            page.get_by_role("button", name=re.compile("Increase budget to")).click()
            page.wait_for_url(re.compile(r"/packages/pkg_"))
            assert page.get_by_text("Remaining (Within Budget)").is_visible()

        with step("no package possible: says why, and 'Edit the trip' brings the values back"):
            page.goto(BASE)
            page.get_by_role("button", name=re.compile("Test Impossible Dates")).click()
            search(page)
            page.locator("[data-testid=no-package]").wait_for()
            assert "1 to 20 April 2027" in page.locator("[data-testid=no-package]").inner_text()
            snap(page, "10_no_package")
            page.get_by_role("button", name="Edit the trip").click()
            page.wait_for_url(BASE + "/")
            assert field(page, "4. Number of Nights").input_value() != ""

        # ---------------------------------------------------------------- compare three packages (G4)
        with step("compare: recommended, cheapest and best rated; open the best rated one"):
            page.goto(BASE)
            menon(page)
            page.get_by_role("button", name=re.compile("Compare Cheapest")).click()
            page.wait_for_url(BASE + "/compare")
            for key in ("recommended", "cheapest", "best_rated"):
                page.locator(f"[data-testid=variant-{key}]").wait_for()
            snap(page, "11_compare")
            page.locator("[data-testid=variant-best_rated]").get_by_role("button", name=re.compile("View and customise")).click()
            page.wait_for_url(re.compile(r"/packages/pkg_"))
            page.get_by_text("Best rated").first.wait_for()

        # ---------------------------------------------------------------- the rest
        with step("an unknown package link shows a friendly message, not a crash"):
            page.goto(BASE + "/packages/pkg_doesnotexist")
            page.get_by_text("We couldn't find that holiday").wait_for()

        with step("phone-sized screen: the form and a package are usable"):
            page.set_viewport_size({"width": 390, "height": 844})
            page.goto(BASE)
            menon(page)
            search(page)
            page.wait_for_url(re.compile(r"/packages/pkg_"))
            page.get_by_text("Why this plan").first.wait_for()
            overflow = page.evaluate("document.documentElement.scrollWidth - window.innerWidth")
            assert overflow <= 4, f"page scrolls sideways by {overflow}px"
            snap(page, "13_mobile")

        browser.close()

    print()
    bad = [n for n, ok in results if not ok]
    if problems:
        print("BROWSER/SERVER PROBLEMS SEEN:")
        for line in sorted(set(problems)):
            print("  -", line)
    print(f"{len(results) - len(bad)}/{len(results)} steps passed" + ("" if not problems else f", {len(set(problems))} problem(s) seen"))
    sys.exit(1 if bad or problems else 0)


if __name__ == "__main__":
    main()
