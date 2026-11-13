"""FastAPI app factory."""
import logging
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from app import config
from app.api.routes import router
from app.catalog.loader import Catalog
from app.engine.inventory import Inventory
from app.store.db import Store

log = logging.getLogger("nomadgrid")


def create_app(data_dir=None, db_path=None, images_dir=None, frontend_dist=None) -> FastAPI:
    app = FastAPI(title="NomadGrid - Build My Holiday", version="1.0")
    app.state.cat = Catalog(data_dir or config.DATA_DIR)
    app.state.store = Store(db_path or config.DB_PATH)
    app.state.inventory = lambda: Inventory(app.state.cat)

    @app.exception_handler(RequestValidationError)
    async def _validation(request: Request, exc: RequestValidationError):
        return JSONResponse(status_code=422, content={"error": {
            "code": "VALIDATION_ERROR", "message": "The request could not be understood.", "fields": []}})

    @app.exception_handler(StarletteHTTPException)
    async def _http(request: Request, exc: StarletteHTTPException):
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

    dist = Path(frontend_dist or config.FRONTEND_DIST)
    if (dist / "index.html").is_file():
        if (dist / "assets").is_dir():
            app.mount("/assets", StaticFiles(directory=str(dist / "assets")), name="assets")

        @app.get("/{full_path:path}", include_in_schema=False)
        def spa(full_path: str):
            if full_path.startswith("api/"):
                return JSONResponse(status_code=404, content={"error": {"code": "NOT_FOUND", "message": "Not found."}})
            target = dist / full_path
            if full_path and target.is_file() and dist in target.resolve().parents:
                return FileResponse(target)
            return FileResponse(dist / "index.html")
    return app
