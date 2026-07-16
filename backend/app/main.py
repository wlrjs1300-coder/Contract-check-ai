from fastapi import FastAPI

app = FastAPI(
    title="ContractCheck AI API",
    version="0.3.0",
)


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}
