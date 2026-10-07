import logging
import sys
import uuid

import structlog
from starlette.datastructures import Headers, MutableHeaders
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send


def configure_logging() -> None:
    """Configure structlog structured JSON logging."""
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=logging.INFO,
    )

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


setup_logging = configure_logging


class CorrelationIdMiddleware:
    """Pure-ASGI middleware: correlation ID + last-resort 500 responses.

    It must sit *inside* ``CORSMiddleware``. Starlette runs the generic
    ``Exception`` handler in ``ServerErrorMiddleware``, which is outside every
    user middleware, so an unhandled error there would return a 500 without
    ``Access-Control-Allow-Origin`` and the browser would report it as a CORS
    failure. Catching it here keeps the CORS headers on error responses.
    """

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return

        headers = Headers(scope=scope)
        correlation_id = headers.get("x-correlation-id") or str(uuid.uuid4())
        scope.setdefault("state", {})["correlation_id"] = correlation_id

        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(correlation_id=correlation_id)

        if scope["type"] == "websocket":
            await self.app(scope, receive, send)
            return

        response_started = False

        async def send_wrapper(message: Message) -> None:
            nonlocal response_started
            if message["type"] == "http.response.start":
                response_started = True
                MutableHeaders(scope=message)["X-Correlation-ID"] = correlation_id
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        except Exception:
            structlog.get_logger().exception(
                "Unhandled exception",
                path=scope.get("path"),
                method=scope.get("method"),
            )
            if response_started:
                raise
            response = JSONResponse(
                status_code=500,
                content={
                    "error_code": "INTERNAL_SERVER_ERROR",
                    "message": "An unexpected server error occurred.",
                    "details": {},
                    "correlation_id": correlation_id,
                },
            )
            await response(scope, receive, send_wrapper)
