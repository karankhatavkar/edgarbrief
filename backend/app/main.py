import time
import uuid

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.api import auth, chat, threads
from app.config import settings
from app.logging_config import configure_logging

configure_logging()
log = structlog.get_logger(__name__)

app = FastAPI(title="EdgarBrief")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def bind_request_context(request: Request, call_next):
    """Correlate every log line in a request with a shared request_id."""
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(
        request_id=str(uuid.uuid4()),
        method=request.method,
        path=request.url.path,
    )
    start = time.perf_counter()
    response = await call_next(request)
    log.info(
        "request.completed",
        status_code=response.status_code,
        duration_ms=round((time.perf_counter() - start) * 1000, 1),
    )
    return response

app.include_router(auth.router)
app.include_router(threads.router)
app.include_router(chat.router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
