from fastapi import FastAPI

from app.api.routes import router

app = FastAPI(title="Kanta AI", version="0.1.0")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(router, prefix="/v1")
