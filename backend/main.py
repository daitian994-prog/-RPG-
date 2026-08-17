import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.api.routes import router
from backend.api.lore_routes import router as lore_router
from backend.database.db import init_db

PROJECT_ROOT = Path(__file__).resolve().parents[1]
APP_VERSION = (PROJECT_ROOT / "VERSION").read_text(encoding="utf-8").strip()
IS_VERCEL = bool(os.getenv("VERCEL"))

app = FastAPI(title="Runeterra: The Nameless API", version=APP_VERSION)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router)
app.include_router(lore_router)
if not IS_VERCEL:
    from backend.api.admin_routes import router as admin_router

    app.include_router(admin_router)


@app.on_event("startup")
def startup() -> None:
    init_db()


@app.get("/health")
@app.get("/api/health")
def health():
    return {"status": "ok", "version": APP_VERSION}


# 生产构建存在时，由 FastAPI 一并提供网页，因此游玩只需启动一个服务。
FRONTEND_DIST = Path(__file__).resolve().parents[1] / "frontend" / "dist"
ADMIN_DIST = Path(__file__).resolve().parent / "admin"
if ADMIN_DIST.exists() and not IS_VERCEL:
    app.mount("/admin", StaticFiles(directory=ADMIN_DIST, html=True), name="admin")
if FRONTEND_DIST.exists():
    app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="frontend")
