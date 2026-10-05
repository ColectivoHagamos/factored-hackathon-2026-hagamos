"""The product web: the built single-page application, served by the API from the same origin (ADR 0006)."""

from pathlib import PurePosixPath

from starlette.exceptions import HTTPException
from starlette.responses import Response
from starlette.staticfiles import StaticFiles
from starlette.types import Scope

# File names in assets/ carry a content hash, so a browser may keep them for a year; the index page never.
IMMUTABLE = "public, max-age=31536000, immutable"
REVALIDATE = "no-cache"


class SinglePageApp(StaticFiles):
    """Static files where a path that names no file answers with index.html, so the browser router picks the page.

    A missing file (a name with an extension) and anything under /v1 stay a 404: only pages fall back.
    """

    async def get_response(self, path: str, scope: Scope) -> Response:
        try:
            response = await super().get_response(path, scope)
        except HTTPException as error:
            if error.status_code != 404 or not _is_a_page(path):
                raise
            response = await super().get_response("index.html", scope)
        response.headers["Cache-Control"] = IMMUTABLE if path.startswith("assets/") else REVALIDATE
        return response


def _is_a_page(path: str) -> bool:
    parts = PurePosixPath(path).parts
    return not (parts and parts[0] == "v1") and "." not in (parts[-1] if parts else "")
