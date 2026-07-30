from __future__ import annotations

import os
import logging
import re
import time
from contextlib import asynccontextmanager
from urllib.parse import urlsplit

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.app.api.analysis_jobs import router as analysis_jobs_router
from backend.app.api.documents import router as documents_router
from backend.app.api.extractions import router as extractions_router
from backend.app.api.auth import router as auth_router
from backend.app.core.config import get_jwt_config
from backend.app.core.encryption_config import get_encryption_keyring
from backend.app.core.email_lookup import get_email_lookup_key
from backend.app.core.logging import configure_logging, log_event
from backend.app.core.operations_config import validate_runtime_configuration
from backend.app.core.proxy_config import get_proxy_config
from backend.app.core.request_context import (
    build_client_context,
    is_loopback_peer,
    normalized_host,
)
from backend.app.services.extraction_orphan_cleanup import OrphanCleanupError, sweep_orphan_request_directories
from backend.app.services.readiness import ReadinessError, get_readiness_status


DEFAULT_CORS_ALLOWED_ORIGINS = "http://localhost:5173"
_REQUEST_ID_HEADER = "X-Request-ID"
_REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._-]{1,64}$")


def parse_cors_allowed_origins(value: str | None = None) -> list[str]:
    configured_value = (
        value
        if value is not None
        else os.getenv(
            "CORS_ALLOWED_ORIGINS",
            DEFAULT_CORS_ALLOWED_ORIGINS,
        )
    )
    origins = [
        origin.strip().rstrip("/")
        for origin in configured_value.split(",")
        if origin.strip().rstrip("/")
    ]

    if "*" in origins:
        raise ValueError("CORS wildcard origins are not allowed.")

    for origin in origins:
        parsed_origin = urlsplit(origin)

        if (
            parsed_origin.scheme not in {"http", "https"}
            or not parsed_origin.netloc
            or parsed_origin.path
            or parsed_origin.query
            or parsed_origin.fragment
        ):
            raise ValueError(
                "CORS origins must be HTTP origins without paths."
            )

    return list(dict.fromkeys(origins))


def _coerce_request_id(raw_request_id: str | None) -> str:
    if raw_request_id and _REQUEST_ID_PATTERN.fullmatch(raw_request_id):
        return raw_request_id
    return f"{time.time_ns()}"


def _coerce_job_id(raw_job_id: str | None) -> str | None:
    if raw_job_id and _REQUEST_ID_PATTERN.fullmatch(raw_job_id):
        return raw_job_id
    return None


@asynccontextmanager
async def lifespan(app: FastAPI):  # noqa: ARG001
    configure_logging("api")
    validate_runtime_configuration()
    get_jwt_config()
    get_encryption_keyring()
    get_email_lookup_key()
    try:
        sweep_result = sweep_orphan_request_directories()
    except OrphanCleanupError:
        raise
    app.state.orphan_cleanup = {
        "scanned_count": sweep_result.scanned_count,
        "eligible_count": sweep_result.eligible_count,
        "removed_count": sweep_result.removed_count,
        "skipped_active_count": sweep_result.skipped_active_count,
        "skipped_unsafe_count": sweep_result.skipped_unsafe_count,
        "failed_count": sweep_result.failed_count,
        "status_codes": dict(sweep_result.status_codes),
    }
    yield


app = FastAPI(
    title="ContractCheck AI API",
    version="0.8.0",
    lifespan=lifespan,
)


@app.middleware("http")
async def request_logging_middleware(request: Request, call_next):
    request_id = _coerce_request_id(request.headers.get(_REQUEST_ID_HEADER))
    request.state.request_id = request_id
    job_id = _coerce_job_id(request.headers.get("X-Job-ID"))
    start = time.perf_counter()

    logger = logging.getLogger("api")
    proxy_config = get_proxy_config(enforce_production=False)
    client_context = build_client_context(request, proxy_config)
    request.state.client_context = client_context
    internal_health_request = (
        request.url.path in {"/health", "/ready"}
        and is_loopback_peer(client_context)
        and not client_context.forwarded_used
    )

    if not internal_health_request:
        host = normalized_host(request)
        if proxy_config.allowed_hosts and host not in proxy_config.allowed_hosts:
            log_event(
                logger=logger,
                event="ingress_rejected",
                service="api",
                status=400,
                request_id=request_id,
                safe_error_code="INVALID_REQUEST_HOST",
            )
            response = JSONResponse(
                status_code=400,
                content={"detail": "Invalid request host."},
            )
            response.headers[_REQUEST_ID_HEADER] = request_id
            return response
        if proxy_config.require_https and client_context.scheme != "https":
            log_event(
                logger=logger,
                event="ingress_rejected",
                service="api",
                status=426,
                request_id=request_id,
                safe_error_code="HTTPS_REQUIRED",
            )
            response = JSONResponse(
                status_code=426,
                content={"detail": "HTTPS is required."},
            )
            response.headers[_REQUEST_ID_HEADER] = request_id
            return response

    try:
        response = await call_next(request)
    except Exception:
        duration_ms = int((time.perf_counter() - start) * 1000)
        log_event(
            logger=logger,
            event="http_request_completed",
            service="api",
            status="error",
            request_id=request_id,
            job_id=job_id,
            duration_ms=duration_ms,
            safe_error_code="UNHANDLED_REQUEST_ERROR",
        )
        raise

    response.headers[_REQUEST_ID_HEADER] = request_id
    duration_ms = int((time.perf_counter() - start) * 1000)
    log_event(
        logger=logger,
        event="http_request_completed",
        service="api",
        status=str(response.status_code),
        request_id=request_id,
        job_id=job_id,
        duration_ms=duration_ms,
    )
    return response


app.add_middleware(
    CORSMiddleware,
    allow_origins=parse_cors_allowed_origins(),
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH"],
    allow_headers=["Accept", "Content-Type", "Authorization", "If-Match", "X-Request-ID", "X-Job-ID"],
)

app.include_router(auth_router)
app.include_router(documents_router)
app.include_router(analysis_jobs_router)
app.include_router(extractions_router)


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/ready")
def readiness_check() -> dict[str, str]:
    try:
        status = get_readiness_status()
    except ReadinessError:
        return JSONResponse(
            status_code=503,
            content={"status": "not_ready"},
        )
    return status
