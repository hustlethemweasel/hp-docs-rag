import time
import uuid

import structlog
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

logger = structlog.get_logger(__name__)


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Assigns (or propagates) a request ID, binding it to every log line
    for the request's lifetime and echoing it back as X-Request-ID so
    client and server logs can be correlated.
    """

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        request_id = request.headers.get("x-request-id", str(uuid.uuid4()))
        request.state.request_id = request_id
        with structlog.contextvars.bound_contextvars(request_id=request_id):
            start = time.monotonic()
            response = await call_next(request)
            logger.info(
                "request_completed",
                method=request.method,
                path=request.url.path,
                status_code=response.status_code,
                duration_ms=int((time.monotonic() - start) * 1000),
            )
        response.headers["X-Request-ID"] = request_id
        return response
