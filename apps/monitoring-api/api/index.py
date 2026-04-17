"""Dedicated Vercel entrypoint for monitoring APIs."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

_THIS_DIR = Path(__file__).resolve().parent
_SERVICE_ROOT = _THIS_DIR.parent
_SHARED_API = _SERVICE_ROOT / "shared_api"

for path in (_SHARED_API,):
    path_str = str(path)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)

from routers import monitoring  # noqa: E402


def _parse_csv_env(name: str) -> list[str]:
    raw = os.getenv(name, "")
    if not raw.strip():
        return []
    return [item.strip() for item in raw.split(",") if item.strip()]


inner_app = FastAPI(title="airbc Monitoring API")

default_origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:3001",
    "http://127.0.0.1:3001",
    "https://app.airbc.org",
    "https://airbc.org",
    "https://web-blushark.vercel.app",
    "https://marketing-blushark.vercel.app",
]

allow_origins = sorted(set(default_origins + _parse_csv_env("API_CORS_ALLOW_ORIGINS")))
allow_origin_regex = os.getenv(
    "API_CORS_ALLOW_ORIGIN_REGEX",
    r"^(http://(localhost|127\.0\.0\.1):\d+|https://(?:web|marketing)(?:-[a-z0-9-]+)?-blushark\.vercel\.app)$",
)

inner_app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_origin_regex=allow_origin_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

inner_app.include_router(monitoring.router)


@inner_app.get("/")
def read_root():
    return {"message": "airbc Monitoring API is running"}


app = FastAPI(title="airbc Monitoring API Wrapper")
app.mount("/api", inner_app)
