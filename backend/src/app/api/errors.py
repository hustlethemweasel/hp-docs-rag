import structlog
from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse

from app.api.schemas import ErrorDetail, ErrorResponse

logger = structlog.get_logger(__name__)

_CODES_BY_STATUS = {
    400: "bad_request",
    404: "not_found",
    422: "validation_error",
}


def _envelope_response(
    status_code: int, code: str, message: str, request: Request
) -> JSONResponse:
    request_id = getattr(request.state, "request_id", None)
    body = ErrorResponse(
        error=ErrorDetail(code=code, message=message, request_id=request_id)
    )
    headers = {"X-Request-ID": request_id} if request_id else None
    return JSONResponse(
        status_code=status_code, content=body.model_dump(), headers=headers
    )


async def http_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    # Narrowed at runtime: FastAPI only ever dispatches this handler for the
    # HTTPException class it was registered against in create_app().
    assert isinstance(exc, HTTPException)
    code = _CODES_BY_STATUS.get(exc.status_code, "http_error")
    return _envelope_response(exc.status_code, code, str(exc.detail), request)


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.error(
        "unhandled_exception",
        path=request.url.path,
        request_id=getattr(request.state, "request_id", None),
        exc_info=exc,
    )
    return _envelope_response(500, "internal_error", "internal server error", request)
