from fastapi import APIRouter
from fastapi.responses import RedirectResponse

router = APIRouter(include_in_schema=False)


@router.get("/console.html")
def console_moved() -> RedirectResponse:
    """The analyst console moved into the web; old links still arrive."""
    return RedirectResponse("/analista", status_code=308)
