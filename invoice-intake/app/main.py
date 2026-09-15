from __future__ import annotations

from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.config import get_settings
from app.routers import dash, health, intake, spec

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings.ensure_dirs()
    Path(settings.storage_root).mkdir(parents=True, exist_ok=True)
    yield


app = FastAPI(
    title="Invoice Intake",
    description="Kitsunex-style Japanese invoice intake pipeline (OCR + LLM + We graph persistence).",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(intake.router)
app.include_router(spec.router)
app.include_router(dash.router)

class SPAStaticFiles(StaticFiles):
    async def get_response(self, path: str, scope):
        try:
            return await super().get_response(path, scope)
        except StarletteHTTPException as exc:
            if (
                exc.status_code == 404
                and not path.startswith("assets/")
                and not path.startswith("_next/")
                and not path.startswith("static/")
                and path != "index.html"
            ):
                path = "index.html"
                return await super().get_response(path, scope)
            raise


_settings = get_settings()
_settings.ensure_dirs()
Path(_settings.storage_root).mkdir(parents=True, exist_ok=True)
_files_dir = Path(_settings.storage_root)
app.mount("/files", StaticFiles(directory=str(_files_dir), html=False), name="files")

# The Next.js static export (SAKANA AI SPA) is served at the root. It is
# mounted LAST so /api/*, /files/*, /dash and /docs keep matching first.
_ui_dir = Path(__file__).resolve().parent.parent / "web"
if _ui_dir.exists():
    app.mount("/", SPAStaticFiles(directory=str(_ui_dir), html=True), name="ui")