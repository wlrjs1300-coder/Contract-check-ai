import os
from urllib.parse import urlsplit

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.api.analysis_jobs import router as analysis_jobs_router
from backend.app.api.documents import router as documents_router
from backend.app.api.extractions import router as extractions_router
from backend.app.db import models as _models  # noqa: F401
from backend.app.db.database import Base, engine


Base.metadata.create_all(bind=engine)


DEFAULT_CORS_ALLOWED_ORIGINS = "http://localhost:5173"


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


app = FastAPI(
    title="ContractCheck AI API",
    version="0.6.1",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=parse_cors_allowed_origins(),
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Accept", "Content-Type"],
)

app.include_router(documents_router)
app.include_router(analysis_jobs_router)
app.include_router(extractions_router)


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}
