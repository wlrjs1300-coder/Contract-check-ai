from fastapi import FastAPI

from backend.app.api.analysis_jobs import router as analysis_jobs_router
from backend.app.api.documents import router as documents_router
from backend.app.db import models as _models  # noqa: F401
from backend.app.db.database import Base, engine


Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="ContractCheck AI API",
    version="0.3.2",
)

app.include_router(documents_router)
app.include_router(analysis_jobs_router)


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}
