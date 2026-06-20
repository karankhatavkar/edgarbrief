import time
import uuid

import structlog
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

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

app.include_router(auth.router, prefix="/api")
app.include_router(threads.router, prefix="/api")
app.include_router(chat.router, prefix="/api")


@app.get("/api/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


# Single-container deploy: FastAPI also serves the built React SPA from the same
# origin. Registered last so it only catches paths the /api routers above didn't.
# In local dev frontend_dist is unset and the Vite dev server serves the UI.
if settings.frontend_dist is not None:
    _dist = settings.frontend_dist.resolve()

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str) -> FileResponse:
        # A path under /api reaching here means no endpoint matched — keep it a
        # JSON 404 instead of handing back index.html.
        if full_path.startswith("api/"):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
        # Serve a real built asset if the path points at one (JS/CSS/favicon),
        # else fall back to index.html so client-side routes and refreshes work.
        candidate = (_dist / full_path).resolve()
        if full_path and candidate.is_file() and candidate.is_relative_to(_dist):
            return FileResponse(candidate)
        return FileResponse(_dist / "index.html")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
