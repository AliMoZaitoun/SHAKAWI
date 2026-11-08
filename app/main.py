import os
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlparse

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.api.v1.endpoints import analytics, auth, citizens, complaints, public, recovery, evidence
from app.api.v1.endpoints import access_admin, directorates
from app.services import identity  # Registers the transactional identity adapter.
from app.services.access import bootstrap_access
from app.db.base import Base
from app.db.migrations import migrate
from app.db.session import SessionLocal, engine


@asynccontextmanager
async def lifespan(app):
    Base.metadata.create_all(bind=engine)
    migrate(engine)
    with SessionLocal() as db:
        auth.provision_accounts(db)
        bootstrap_access(db)
    yield


app = FastAPI(title="Government Complaints Platform", version="1.0.0", lifespan=lifespan)
secret = os.environ.get("SESSION_SECRET")
if not secret:
    raise RuntimeError("SESSION_SECRET must be configured in Secrets")
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
app.mount("/static", StaticFiles(directory="static", check_dir=False), name="static")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/")
def index():
    path = Path("static/index.html")
    if not path.exists():
        return JSONResponse({"message": "واجهة المشروع قيد التجهيز"})
    return FileResponse(path)


@app.get("/Shakwa.html")
def original_link():
    return index()
