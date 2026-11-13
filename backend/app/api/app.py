"""FastAPI app factory."""
import logging
import tempfile
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from app import config
from app.api.fallback_page import PAGE as FALLBACK_PAGE
from app.api.routes import router
from app.catalog.loader import Catalog
from app.engine.inventory import Inventory
from app.store.db import Store

log = logging.getLogger("nomadgrid")


def open_store(db_path) -> Store:
    """Open the database; if its folder cannot be written, fall back to a temporary one (with a clear warning)
    so the app still starts. Data kept there lasts only until the temp folder is cleared."""
    try:
        return Store(db_path)
    except OSError as e:
        fallback = Path(tempfile.gettempdir()) / "nomadgrid" / "nomadgrid.sqlite"
        log.warning("Cannot use the database at %s (%s). Falling back to %s - reservations will NOT survive a "
                    "cleared temp folder. Set DB_PATH to a writable location.", db_path, e, fallback)
        return Store(fallback)


def create_app(data_dir=None, db_path=None, images_dir=None, frontend_dist=None) -> FastAPI:
    app = FastAPI(title="NomadGrid - Build My Holiday", version="1.0")
    dist = Path(frontend_dist or config.FRONTEND_DIST)
    has_ui = (dist / "index.html").is_file()
    app.state.cat = Catalog(data_dir or config.DATA_DIR)
    app.state.store = open_store(db_path or config.DB_PATH)
    app.state.inventory = lambda: Inventory(app.state.cat, *app.state.store.used_maps())

    @app.exception_handler(RequestValidationError)
    async def _validation(request: Request, exc: RequestValidationError):
        return JSONResponse(status_code=422, content={"error": {
            "code": "VALIDATION_ERROR", "message": "The request could not be understood.", "fields": []}})

    @app.exception_handler(StarletteHTTPException)
    async def _http(request: Request, exc: StarletteHTTPException):
        path = request.url.path
        if has_ui and exc.status_code == 404 and request.method == "GET" and not path.startswith(("/api/", "/images/")):
            target = dist / path.lstrip("/")
            if path != "/" and target.is_file() and dist.resolve() in target.resolve().parents:
                return FileResponse(target)          # a real file from the build (icons etc.)
            return FileResponse(dist / "index.html")   # a client-side route such as /packages/pkg_123
        code = {404: "NOT_FOUND", 405: "METHOD_NOT_ALLOWED"}.get(exc.status_code, "HTTP_ERROR")
        msg = {404: "Not found.", 405: "That method is not allowed here."}.get(exc.status_code, "Request failed.")
        return JSONResponse(status_code=exc.status_code, content={"error": {"code": code, "message": msg}})

    @app.exception_handler(Exception)
    async def _unexpected(request: Request, exc: Exception):
        log.exception("unhandled error on %s", request.url.path)
        return JSONResponse(status_code=500, content={"error": {
            "code": "INTERNAL_ERROR", "message": "Something went wrong on our side. Please try again."}})

    app.include_router(router)

    images = Path(images_dir or config.IMAGES_DIR)
    if images.is_dir():
        app.mount("/images", StaticFiles(directory=str(images)), name="images")

    if has_ui:
        log.info("Serving the web UI from %s", dist)
        if (dist / "assets").is_dir():
            app.mount("/assets", StaticFiles(directory=str(dist / "assets")), name="assets")
    else:
        log.warning("The web UI is not built (%s/index.html is missing): serving the API only. "
                    "Run `npm run build` in the frontend folder.", dist)

        @app.get("/", include_in_schema=False)
        def no_ui():
            return HTMLResponse(FALLBACK_PAGE)
    return app
