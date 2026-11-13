"""Change a package (hotel, flight, sights, city plan) and undo the last change."""
from fastapi import APIRouter, Request

from app.api.routes.shared import error
from app.changes.service import apply_change

router = APIRouter()


@router.post("/packages/{package_id}/changes")
async def change_package(package_id: str, request: Request):
    cat, store = request.app.state.cat, request.app.state.store
    pkg = store.get_package(package_id)
    if pkg is None:
        return error(404, "PACKAGE_NOT_FOUND", "We couldn't find that package.")
    try:
        op = await request.json()
    except Exception:
        return error(422, "VALIDATION_ERROR", "The request body must be valid JSON.")
    if not isinstance(op, dict):
        return error(422, "VALIDATION_ERROR", "The change must be a JSON object with an 'op' field.")
    res = apply_change(pkg, op, cat, request.app.state.inventory())
    if res["result"] == "APPLIED":
        store.save_package(res["package"], keep_history=True)
        res["undo_available"] = True
    return res


@router.post("/packages/{package_id}/undo")
def undo_last_change(package_id: str, request: Request):
    store = request.app.state.store
    pkg = store.get_package(package_id)
    if pkg is None:
        return error(404, "PACKAGE_NOT_FOUND", "We couldn't find that package.")
    if pkg["status"] == "BOOKED":
        return {"result": "REFUSED", "reason_code": "PACKAGE_LOCKED",
                "reason": "This holiday is already booked, so it can't be changed or undone."}
    restored = store.undo(package_id)
    if restored is None:
        return {"result": "REFUSED", "reason_code": "NOTHING_TO_UNDO", "reason": "There is no change to undo."}
    return {"result": "UNDONE", "package": restored, "summary": "Your last change was undone.",
            "undo_available": store.history_count(package_id) > 0}
