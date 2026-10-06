import json
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.v1.router import router as v1_router
from app.core.config import get_settings
from app.core.responses import failure, success

settings = get_settings()
class StructuredFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        entry = {
            "timestamp": datetime.fromtimestamp(record.created, timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "event": record.getMessage(),
            "requestId": getattr(record, "request_id", "-"),
        }
        error_type = getattr(record, "error_type", None)
        if error_type:
            entry["errorType"] = error_type
        return json.dumps(entry, separators=(",", ":"))


logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO))
logger = logging.getLogger("vitapulse")


for handler in logging.getLogger().handlers:
    handler.setFormatter(StructuredFormatter())


@asynccontextmanager
async def lifespan(_: FastAPI):
    logger.info("application_start", extra={"request_id": "-"})
    yield
    logger.info("application_stop", extra={"request_id": "-"})


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    debug=settings.debug and settings.app_env == "development",
    lifespan=lifespan,
)
web_static_files = StaticFiles(
    directory=Path(__file__).resolve().parents[1] / "public",
    html=True,
    check_dir=False,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID", "apikey"],
)
app.include_router(v1_router, prefix=settings.api_v1_prefix)


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID", "").strip() or str(uuid4())
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


@app.exception_handler(StarletteHTTPException)
async def http_error_handler(request: Request, exception: StarletteHTTPException) -> JSONResponse:
    code = {
        401: "UNAUTHORIZED",
        403: "FORBIDDEN",
        404: "NOT_FOUND",
        422: "VALIDATION_ERROR",
        503: "SERVICE_UNAVAILABLE",
    }.get(exception.status_code, "REQUEST_ERROR")
    message = exception.detail if isinstance(exception.detail, str) else "The request could not be completed."
    return JSONResponse(
        status_code=exception.status_code,
        content=failure(request, code, message),
        headers=exception.headers,
    )


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, _: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content=failure(request, "VALIDATION_ERROR", "Check the request and try again."),
    )


@app.exception_handler(Exception)
async def unexpected_error_handler(request: Request, exception: Exception) -> JSONResponse:
    logger.error(
        "unhandled_request_error",
        extra={
            "request_id": request.state.request_id,
            "error_type": type(exception).__name__,
        },
    )
    return JSONResponse(
        status_code=500,
        content=failure(request, "INTERNAL_ERROR", "The request could not be completed."),
    )


@app.get("/health")
async def health(request: Request) -> dict:
    return success(request, {"status": "ok"})


@app.get("/ready")
async def ready(request: Request):
    from app.api.v1.router import versioned_ready

    return await versioned_ready(request, settings)


@app.api_route("/{file_path:path}", methods=["GET", "HEAD"], include_in_schema=False)
async def serve_web_app(file_path: str, request: Request):
    if file_path == "api" or file_path.startswith("api/"):
        raise StarletteHTTPException(status_code=404, detail="Not Found")
    return await web_static_files.get_response(file_path, request.scope)
