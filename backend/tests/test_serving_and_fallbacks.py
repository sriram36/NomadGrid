"""Serving the web UI, and every fallback: no UI built, unwritable database, missing catalog."""
import logging

import pytest
from fastapi.testclient import TestClient

from app.api.app import create_app
from app.config import DATA_DIR


@pytest.fixture()
def ui(tmp_path):
    """A fake built frontend next to a secret file that must never be served."""
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<html><body>THE-APP</body></html>", encoding="utf-8")
    (dist / "assets" / "app.js").write_text("console.log('app')", encoding="utf-8")
    (dist / "favicon.txt").write_text("ICON", encoding="utf-8")
    (tmp_path / "secret.txt").write_text("TOP-SECRET", encoding="utf-8")
    return dist


@pytest.fixture()
def with_ui(ui, tmp_path):
    return TestClient(create_app(db_path=tmp_path / "a.sqlite", frontend_dist=ui))


@pytest.fixture()
def without_ui(tmp_path):
    return TestClient(create_app(db_path=tmp_path / "b.sqlite", frontend_dist=tmp_path / "nothing-here"))


# ------------------------------------------------------------------ the UI is served
def test_root_and_client_side_routes_serve_the_app(with_ui):
    for path in ("/", "/packages/pkg_abc123", "/compare", "/outcome", "/bookings", "/some/deep/link"):
        r = with_ui.get(path)
        assert r.status_code == 200 and "THE-APP" in r.text, path


def test_built_assets_and_files_are_served(with_ui):
    assert with_ui.get("/assets/app.js").text == "console.log('app')"
    assert with_ui.get("/favicon.txt").text == "ICON"


def test_the_api_keeps_its_own_answers_when_the_ui_is_present(with_ui):
    assert with_ui.get("/api/health").json() == {"status": "ok"}
    assert with_ui.get("/api/packages").status_code == 405                      # wrong method stays a 405
    assert with_ui.get("/api/nothing-here").json()["error"]["code"] == "NOT_FOUND"
    assert with_ui.get("/api/reservations/123").json()["error"]["code"] == "RESERVATION_NOT_FOUND"
    assert with_ui.get("/images/hotels/not-a-photo.jpg").status_code == 404
    assert "THE-APP" not in with_ui.get("/api/nothing-here").text


@pytest.mark.parametrize("path", ["/..%2fsecret.txt", "/%2e%2e/secret.txt", "/assets/..%2f..%2fsecret.txt",
                                  "/....//secret.txt", "/%5c..%5csecret.txt"])
def test_files_outside_the_build_are_never_served(with_ui, path):
    r = with_ui.get(path)
    assert "TOP-SECRET" not in r.text


def test_post_to_an_unknown_page_is_not_swallowed_by_the_app(with_ui):
    assert with_ui.post("/packages/pkg_x").status_code in (404, 405)


# ------------------------------------------------------------------ no UI built: a friendly page, API still works
def test_without_a_built_ui_the_home_page_explains_what_to_do(without_ui):
    r = without_ui.get("/")
    assert r.status_code == 200 and "text/html" in r.headers["content-type"]
    assert "booking API is running" in r.text and "npm run build" in r.text and "/docs" in r.text


def test_without_a_ui_the_api_and_docs_work_and_other_pages_are_404(without_ui):
    assert without_ui.get("/api/health").json() == {"status": "ok"}
    assert without_ui.get("/docs").status_code == 200
    assert without_ui.get("/packages/pkg_x").json()["error"]["code"] == "NOT_FOUND"


# ------------------------------------------------------------------ the database
def test_an_unwritable_database_falls_back_to_a_temporary_one_and_warns(tmp_path, caplog):
    blocker = tmp_path / "a-file-not-a-folder"
    blocker.write_text("x", encoding="utf-8")
    with caplog.at_level(logging.WARNING, logger="nomadgrid"):
        client = TestClient(create_app(db_path=blocker / "db.sqlite", frontend_dist=tmp_path / "none"))
    assert "Falling back" in caplog.text and "DB_PATH" in caplog.text
    body = {"departure_city": "Bengaluru", "country": "Japan", "start_date": "2027-04-10", "nights": 6, "adults": 2,
            "child_ages": [6], "budget_inr": 350000}
    pkg = client.post("/api/packages", json=body).json()["package"]            # it still works end to end
    assert client.post(f"/api/packages/{pkg['package_id']}/confirm").status_code == 200


# ------------------------------------------------------------------ the catalog
def test_a_missing_catalog_says_exactly_what_to_set(tmp_path):
    with pytest.raises(FileNotFoundError) as e:
        create_app(data_dir=tmp_path, db_path=tmp_path / "x.sqlite")
    assert "DATA_DIR" in str(e.value) and "destinations.json" in str(e.value) or "catalog" in str(e.value)


def test_the_provided_catalog_loads(tmp_path):
    assert TestClient(create_app(data_dir=DATA_DIR, db_path=tmp_path / "x.sqlite")).get("/api/meta").status_code == 200
