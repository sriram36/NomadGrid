"""S1 interests, S2 city guides, S3 dining, S5 explainer additions, S6 route. Includes attempts to break each."""
import copy
import itertools

import pytest

from app import interests as tags
from app.content import Content
from app.export.package import to_trip_format
from app.validator.validate import validate_trip
from tests.conftest import MENON

ALL = [t["id"] for t in tags.tag_list()]


def build(client, **over):
    body = {**copy.deepcopy(MENON), **over}
    r = client.post("/api/packages", json=body)
    assert r.status_code == 200, r.text
    return r.json()


def sights(pkg):
    return [i for i in pkg["items"] if i["type"] == "attraction"]


# ------------------------------------------------------------------ S1: interests
def test_tags_are_accepted_by_id_or_label_in_any_case_and_deduplicated(client):
    for raw in (["ART"], ["art"], ["Art & Design"], ["history-culture"], ["History & Culture", "HISTORY_CULTURE"]):
        out = build(client, interests=raw)
        assert out["outcome"] == "PACKAGE"
    out = build(client, interests=["History & Culture", "HISTORY_CULTURE", "art"])
    assert out["package"]["request"]["interests"] == ["HISTORY_CULTURE", "ART"]


@pytest.mark.parametrize("bad", ["ART", {"ART": 1}, [1], [None], ["nonsense"], [["ART"]], list(range(25)), [""]])
def test_bad_interests_are_a_field_error_not_a_crash(client, bad):
    r = client.post("/api/packages", json={**MENON, "interests": bad})
    assert r.status_code == 422
    assert any(f["field"] == "interests" for f in r.json()["error"]["fields"])


def test_interests_are_optional_and_null_means_none(client):
    assert build(client)["package"]["request"]["interests"] == []
    assert build(client, interests=None)["package"]["request"]["interests"] == []


def test_meta_lists_the_tags(client):
    ids = [t["id"] for t in client.get("/api/meta").json()["interests"]]
    assert ids == ALL and len(ids) >= 5


def test_every_attraction_in_the_catalog_is_classified_without_crashing(cat):
    for a in cat.attractions.values():
        got = tags.tags_of(a)
        assert set(got) <= set(ALL)
    # every tag is actually reachable in each country, so choosing it can matter
    for country in ("Japan", "United Arab Emirates"):
        cities = set(cat.cities_of(country)) | ({"Nara"} if country == "Japan" else set())
        here = {t for a in cat.attractions.values() if a["city"] in cities for t in tags.tags_of(a)}
        assert len(here) >= 4, (country, here)


def test_interests_pull_matching_sights_into_the_package(client):
    plain = {t: 0 for t in ALL}
    for i in sights(build(client)["package"]):
        for t in i["details"]["interestTags"]:
            plain[t] += 1
    gained = 0
    for tag in ALL:
        pkg = build(client, interests=[tag], budget_inr=450000)["package"]
        mine = [i for i in sights(pkg) if tag in i["details"]["matchedInterests"]]
        assert all("MATCHES_INTEREST" in i["badges"] for i in mine)
        if len(mine) > plain[tag]:
            gained += 1
    assert gained >= 3          # for most interests the traveler now gets more of what they asked for


def test_interests_never_break_a_rule_or_the_budget(client, cat):
    for combo in [[], ["ART"], ["NATURE", "FAMILY"], ALL, ["VIEWS_ADVENTURE", "FOOD_MARKETS", "HISTORY_CULTURE"]]:
        for country, start in (("Japan", "2027-04-10"), ("United Arab Emirates", "2027-04-05")):
            out = build(client, country=country, start_date=start, interests=combo, budget_inr=500000)
            if out["outcome"] != "PACKAGE":
                continue
            pkg = out["package"]
            assert validate_trip(to_trip_format(pkg), cat) == []
            assert pkg["pricing"]["total_inr"] <= 500000
            names = [i["catalog_id"] for i in sights(pkg)]
            assert len(names) == len(set(names))                 # no sight twice


def test_interests_survive_edits_and_undo_and_are_not_exported(client, cat):
    pkg = build(client, interests=["ART", "NATURE"], budget_inr=500000)["package"]
    pid = pkg["package_id"]
    day = pkg["days"][1]["date"]
    opts = client.get(f"/api/packages/{pid}/options/attractions", params={"date": day}).json()["options"]
    assert opts
    flags = [o["matches_interests"] for o in opts]
    assert flags == sorted(flags, reverse=True)                    # matching ones come first
    res = client.post(f"/api/packages/{pid}/changes", json={"op": "ADD_ATTRACTION", "attraction_id": opts[0]["attraction_id"],
                                                             "date": day, "start": opts[0]["start_choices"][0]}).json()
    assert res["result"] == "APPLIED"
    assert res["package"]["request"]["interests"] == ["ART", "NATURE"]
    exported = client.get(f"/api/packages/{pid}/export").json()
    assert "interests" not in exported and "route" not in exported
    assert set(exported) == set(to_trip_format(res["package"]))


def test_city_plan_change_and_variants_keep_interests(client):
    pkg = build(client, interests=["FAMILY"], budget_inr=500000)["package"]
    plans = client.get(f"/api/packages/{pkg['package_id']}/options/city-plans").json()
    assert plans["options"]
    v = client.post("/api/packages/variants", json={**MENON, "interests": ["FAMILY"], "budget_inr": 500000}).json()
    assert v["outcome"] == "VARIANTS"
    for p in [v["recommended"], *[x for x in v["variants"].values() if x]]:
        assert p["request"]["interests"] == ["FAMILY"]


# ------------------------------------------------------------------ S2: city guides
def test_every_city_has_a_guide_and_unknown_cities_are_404(client, cat):
    for country in cat.destinations["countries"]:
        for city in country["cities"]:
            g = client.get(f"/api/cities/{city['name']}/guide").json()
            assert g["city"] == city["name"]
            for key in ("getting_around", "etiquette", "sightseeing_tips"):
                assert len(g[key]) >= 3 and all(isinstance(x, str) and x for x in g[key])
    for bad in ("Atlantis", "tokyo", "", "%20", "Tokyo%2F..%2Fx", "..", "Tokyo;drop"):
        r = client.get(f"/api/cities/{bad}/guide")
        assert r.status_code in (404, 405) or r.json()["error"]["code"] == "CITY_NOT_FOUND"


def test_package_guides_follow_the_package_cities(client):
    pkg = build(client)["package"]
    got = [g["city"] for g in client.get(f"/api/packages/{pkg['package_id']}/guides").json()["guides"]]
    assert got == [l["city"] for l in pkg["city_plan"]]
    assert client.get("/api/packages/pkg_nope/guides").status_code == 404


# ------------------------------------------------------------------ S3: dining
def test_every_hotel_area_has_three_or_four_dining_spots_with_labels(cat):
    content = Content()
    for h in cat.hotels.values():
        spots = content.restaurants(h["city"], h["area"])
        assert spots is not None and 3 <= len(spots) <= 4, (h["city"], h["area"])
        for s in spots:
            assert s["estimated_price_per_person_inr"] > 0 and isinstance(s["dietary_tags"], list)


def test_dining_is_per_hotel_estimated_and_never_in_the_total(client):
    pkg = build(client)["package"]
    total_before = pkg["pricing"]["total_inr"]
    out = client.get(f"/api/packages/{pkg['package_id']}/dining").json()
    assert out["included_in_total"] is False and "NOT included" in out["disclaimer"]
    hotels = [i for i in pkg["items"] if i["type"] == "hotel"]
    assert [s["item_id"] for s in out["stays"]] == [h["item_id"] for h in hotels]
    for stay, hotel in zip(out["stays"], hotels, strict=True):
        assert stay["area"] == hotel["details"]["area"] and 3 <= len(stay["restaurants"]) <= 4
        assert all("estimate" in r["price_label"] for r in stay["restaurants"])
    assert client.get(f"/api/packages/{pkg['package_id']}").json()["pricing"]["total_inr"] == total_before
    assert "dining" not in str(client.get(f"/api/packages/{pkg['package_id']}/export").json()).lower()


def test_city_restaurant_endpoint_filters_by_area_and_rejects_unknowns(client):
    r = client.get("/api/cities/Tokyo/restaurants", params={"area": "Ginza"}).json()
    assert r["restaurants"] and all(x["area"] == "Ginza" for x in r["restaurants"]) and r["included_in_total"] is False
    assert len(client.get("/api/cities/Tokyo/restaurants").json()["restaurants"]) >= 15
    assert client.get("/api/cities/Tokyo/restaurants", params={"area": "Moon"}).status_code == 404
    assert client.get("/api/cities/Atlantis/restaurants").status_code == 404
    assert client.get("/api/packages/pkg_nope/dining").status_code == 404


def test_a_missing_content_folder_does_not_stop_the_app(tmp_path):
    c = Content(tmp_path)
    assert c.guide("Tokyo") is None and c.restaurants("Tokyo") is None


def test_content_files_are_separate_from_the_catalog(cat):
    from app.content import CONTENT_DIR
    from app.config import DATA_DIR
    assert DATA_DIR not in CONTENT_DIR.parents and CONTENT_DIR not in DATA_DIR.parents


# ------------------------------------------------------------------ S5: explainer additions
def test_why_this_plan_explains_margins_rooms_and_interests(client):
    reasons = build(client, interests=["ART"])["package"]["rationale"]["reasons"]
    text = " ".join(reasons)
    assert "Safety margins are met" in text and "at least 60" in text and "at least 180" in text
    assert "Rooms:" in text and "traveller(s)" in text
    assert "Your interests (Art & Design)" in text
    assert "Your interests" not in " ".join(build(client)["package"]["rationale"]["reasons"])


def test_margins_quoted_in_the_explainer_are_really_met(client):
    for pkg in (build(client)["package"], build(client, country="United Arab Emirates", start_date="2027-04-05")["package"]):
        text = next(r for r in pkg["rationale"]["reasons"] if r.startswith("Safety margins"))
        import re
        pickup, airport = map(int, re.findall(r"(\d+) min", text)[:2])
        assert pickup >= 60 and airport >= 180


# ------------------------------------------------------------------ S6: route
def test_route_matches_the_package_cities_and_legs(client):
    pkg = build(client)["package"]
    route = pkg["route"]
    assert [s["city"] for s in route["stops"]] == [l["city"] for l in pkg["city_plan"]]
    assert [s["nights"] for s in route["stops"]] == [l["nights"] for l in pkg["city_plan"]]
    assert route["path"][0] == route["path"][-1] == "Bengaluru"
    kinds = [l["kind"] for l in route["legs"]]
    assert kinds[0] == "FLIGHT" and kinds[-1] == "FLIGHT" and kinds.count("INTERCITY") == len(route["stops"]) - 1
    assert [l["order"] for l in route["legs"]] == list(range(1, len(route["legs"]) + 1))
    assert route["origin"]["airport"] == "BLR" and route["origin"]["lat"] is not None
    assert all(s["lat"] is not None and s["lng"] is not None for s in route["stops"])
    assert route["summary"]["travel_minutes"] == sum(l["duration_minutes"] for l in route["legs"])
    assert route["summary"]["nights"] == 6


def test_route_updates_when_the_city_plan_changes_and_for_every_variant(client):
    pkg = build(client, budget_inr=500000)["package"]
    plans = client.get(f"/api/packages/{pkg['package_id']}/options/city-plans").json()["options"]
    other = next(p for p in plans if not p["current"])
    res = client.post(f"/api/packages/{pkg['package_id']}/changes", json={"op": "CHANGE_CITY_PLAN", "plan": other["plan"]}).json()
    if res["result"] == "APPLIED":
        new = res["package"]
        assert [s["city"] for s in new["route"]["stops"]] == [l["city"] for l in new["city_plan"]]
    v = client.post("/api/packages/variants", json={**MENON, "budget_inr": 500000}).json()
    for p in [v["recommended"], *[x for x in v["variants"].values() if x]]:
        assert [s["city"] for s in p["route"]["stops"]] == [l["city"] for l in p["city_plan"]]


def test_route_for_a_single_city_trip_has_no_intercity_leg(client):
    out = build(client, nights=3, budget_inr=400000)
    pkg = out["package"]
    route = pkg["route"]
    assert len(route["stops"]) == len(pkg["city_plan"])
    assert len(route["legs"]) == len(route["stops"]) + 1


# ------------------------------------------------------------------ breaking attempts, mixed
@pytest.mark.parametrize("interests", list(itertools.combinations(ALL, 2)))
def test_every_pair_of_interests_builds_a_valid_trip(client, cat, interests):
    out = build(client, interests=list(interests), budget_inr=500000)
    assert out["outcome"] == "PACKAGE"
    assert validate_trip(to_trip_format(out["package"]), cat) == []


def test_interests_with_a_tight_budget_still_get_the_honest_over_budget_answer(client):
    out = build(client, interests=["ART"], budget_inr=200000)
    assert out["outcome"] == "OVER_BUDGET" and out["raise_budget"]["budget_inr"] == out["cheapest_total_inr"]
    assert out["alternatives"]
    for alt in out["alternatives"]:
        pkg = client.get(f"/api/packages/{alt['package_id']}").json()
        assert pkg["request"]["interests"] == ["ART"]
    nothing_fits = build(client, interests=["ART"], budget_inr=100000)
    assert nothing_fits["outcome"] == "OVER_BUDGET" and nothing_fits["cheapest_total_inr"] > 100000


def test_booking_a_package_with_interests_works_and_is_read_only_afterwards(client):
    pkg = build(client, interests=["NATURE"])["package"]
    booked = client.post(f"/api/packages/{pkg['package_id']}/confirm").json()
    assert booked["package"]["request"]["interests"] == ["NATURE"] and booked["package"]["route"]
    r = client.post(f"/api/packages/{pkg['package_id']}/changes", json={"op": "REMOVE_ATTRACTION", "item_id": "i3"}).json()
    assert r["reason_code"] == "PACKAGE_LOCKED"


# ------------------------------------------------------------------ S1 quick request understands interests
def test_the_sentence_reader_picks_up_interests_in_typed_order(client):
    r = client.post("/api/parse-request", json={"text": "Japan 10 Apr 6 nights 2 adults 1 child 6 from Bengaluru "
                                                          "3.5 lakh, we like nature and history and street food"}).json()
    assert r["fields"]["interests"] == ["NATURE", "HISTORY_CULTURE", "FOOD_MARKETS"]
    assert r["ready"] and "nature" not in r["unparsed"] and "history" not in r["unparsed"]


def test_a_plain_family_trip_is_not_read_as_an_interest(client):
    r = client.post("/api/parse-request", json={"text": "family trip to Japan 10 Apr 6 nights 2 adults from Delhi 4 lakh"}).json()
    assert "interests" not in r["fields"]


def test_a_sentence_with_interests_builds_the_same_trip_as_the_form(client):
    r = client.post("/api/parse-request", json={"text": "Japan 10 Apr 6 nights 2 adults 1 child 6 from Bengaluru "
                                                          "3.5 lakh art"}).json()
    out = client.post("/api/packages", json=r["fields"]).json()
    assert out["outcome"] == "PACKAGE" and out["package"]["request"]["interests"] == ["ART"]


@pytest.mark.parametrize("text", ["art " * 300, "history, ,, nature;;;  parks   BEACH", "ARTART art-art", "interests"])
def test_odd_sentences_with_interest_words_never_crash(client, text):
    r = client.post("/api/parse-request", json={"text": text[:1000]})
    assert r.status_code in (200, 422)
