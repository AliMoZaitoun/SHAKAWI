import os
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlparse

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.api.v1.endpoints import analytics, auth, citizens, complaints, public, recovery, evidence
from app.api.v1.endpoints import access_admin, directorates, localization, foundations
from app.services import identity  # Registers the transactional identity adapter.
from app.services import translations, file_catalog, audit
from app.services.foundation_middleware import FoundationMiddleware
from app.services.access import bootstrap_access
from app.db.base import Base
from app.db.upgrade import upgrade_database
from app.db.session import SessionLocal, engine


@asynccontextmanager
async def lifespan(app):
    upgrade_database(engine)
    with SessionLocal() as db:
        bootstrap_access(db)
        auth.provision_accounts(db)
        bootstrap_access(db)
        translations.seed_translations(db)
        db.commit()
    yield


app = FastAPI(title="Government Complaints Platform", version="1.0.0", lifespan=lifespan)
secret = os.environ.get("SESSION_SECRET")
if not secret:
    raise RuntimeError("SESSION_SECRET must be configured in Secrets")
app.add_middleware(FoundationMiddleware)
app.add_middleware(
    SessionMiddleware, secret_key=secret,
    same_site="none" if os.environ.get("REPLIT_DEV_DOMAIN") or os.environ.get("REPLIT_DEPLOYMENT") else "strict",
    max_age=8 * 3600,
    https_only=bool(os.environ.get("REPLIT_DEV_DOMAIN") or os.environ.get("REPLIT_DEPLOYMENT")),
)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        origin = request.headers.get("Origin")
        if origin and urlparse(origin).netloc != request.headers.get("host"):
            return JSONResponse({"detail": "Cross-origin requests are not allowed"}, status_code=403)
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "same-origin"
    response.headers["Cache-Control"] = "no-store"
    return response


app.include_router(auth.router, prefix="/api/v1/auth", tags=["Auth"])
app.include_router(citizens.router, prefix="/api/v1/citizens", tags=["Citizens"])
app.include_router(recovery.router, prefix="/api/v1/citizens/recovery", tags=["Ownership recovery"])
app.include_router(public.router, prefix="/api/v1/complaints/public", tags=["Public transparency"])
app.include_router(analytics.router, prefix="/api/v1/analytics", tags=["Staff analytics"])
app.include_router(complaints.router, prefix="/api/v1/complaints", tags=["Complaints"])
app.include_router(evidence.router, prefix="/api/v1", tags=["Private evidence"])
app.include_router(access_admin.router, prefix="/api/v1/admin", tags=["Access administration"])
app.include_router(directorates.router, prefix="/api/v1", tags=["Directorates"])
app.include_router(localization.router, prefix="/api/v1", tags=["Languages and translations"])
app.include_router(foundations.router, prefix="/api/v1", tags=["Private files, audit and history"])
app.mount("/static", StaticFiles(directory="static", check_dir=False), name="static")
FRONTEND_DIST = Path(__file__).resolve().parents[1] / "frontend" / "dist"


@app.get("/assets/{asset_path:path}", include_in_schema=False)
def react_asset(asset_path: str):
    directory = (FRONTEND_DIST / "assets").resolve()
    path = (directory / asset_path).resolve()
    if not path.is_relative_to(directory) or not path.is_file():
        raise HTTPException(404, "Asset not found")
    return FileResponse(path)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/")
def index():
    if os.environ.get("SHAKWA_UI") != "legacy" and (FRONTEND_DIST / "index.html").is_file():
        return FileResponse(FRONTEND_DIST / "index.html")
    return legacy_index()


@app.get("/legacy")
def legacy_index():
    path = Path("static/index.html")
    if not path.exists():
        return JSONResponse({"message": "واجهة المشروع قيد التجهيز"})
    return FileResponse(path)


@app.get("/Shakwa.html")
def original_link():
    return legacy_index()


@app.get("/{path:path}", include_in_schema=False)
def react_route(path: str):
    # Unknown APIs and files must remain 404, not a 200 HTML SPA response.
    if path.split("/", 1)[0] in {"api", "assets", "static", "docs", "redoc", "health", "legacy"} or "." in path.rsplit("/", 1)[-1]:
        raise HTTPException(404, "Not found")
    if os.environ.get("SHAKWA_UI") != "legacy" and (FRONTEND_DIST / "index.html").is_file():
        return FileResponse(FRONTEND_DIST / "index.html")
    raise HTTPException(404, "React build is not available; run pnpm install and pnpm build")
