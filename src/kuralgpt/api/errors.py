"""Standard API error responses using RFC 9457 problem details."""

from fastapi import Request
from fastapi.responses import JSONResponse


class ApiError(Exception):
    """An application error with an HTTP status code."""

    def __init__(
        self,
        status_code: int,
        title: str,
        detail: str,
        error_type: str = "about:blank",
    ) -> None:
        self.status_code = status_code
        self.title = title
        self.detail = detail
        self.error_type = error_type
        super().__init__(detail)


async def api_error_handler(request: Request, exc: ApiError) -> JSONResponse:
    """Convert application errors into problem-details responses."""
    request_id = getattr(request.state, "request_id", None)

    problem = {
        "type": exc.error_type,
        "title": exc.title,
        "status": exc.status_code,
        "detail": exc.detail,
        "instance": str(request.url.path),
    }

    if request_id:
        problem["request_id"] = request_id

    return JSONResponse(
        status_code=exc.status_code,
        content=problem,
        media_type="application/problem+json",
    )
