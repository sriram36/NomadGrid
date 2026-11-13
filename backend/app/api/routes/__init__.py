"""All HTTP routes under /api, one module per area. Thin layer: parse -> engine/store -> shape the response."""
from fastapi import APIRouter

from app.api.routes import build, changes, content, meta, options, packages, reservations

router = APIRouter(prefix="/api")
for _module in (meta, build, packages, changes, options, content, reservations):   # `build` before `packages`: /packages/variants first
    router.include_router(_module.router)
