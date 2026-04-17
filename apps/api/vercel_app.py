"""
Lightweight FastAPI app for the Vercel deployment.

This keeps the web simulation surface available in production without bundling
the heavier monitoring and LLM-assisted research routers that are not required
for the simulation workspace.
"""

import os
import sys
from pathlib import Path

_THIS_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _THIS_DIR.parent.parent
_STREAMLIT_APP = _PROJECT_ROOT / "streamlit_app"
_SRC = _PROJECT_ROOT / "src"

for path in (_THIS_DIR, _STREAMLIT_APP, _SRC):
    path_str = str(path)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)

import st_shim  # noqa: E402

st_shim.install()

from fastapi import FastAPI  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from routers import data, flux, pathway, sensitivity, simulation  # noqa: E402


def _parse_csv_env(name: str) -> list[str]:
    raw = os.getenv(name, "")
    if not raw.strip():
        return []
    return [item.strip() for item in raw.split(",") if item.strip()]


app = FastAPI(title="RBC Metabolic Model API")

default_origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:3001",
    "http://127.0.0.1:3001",
    "http://localhost:3002",
    "http://127.0.0.1:3002",
    "http://localhost:3003",
    "http://127.0.0.1:3003",
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

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_origin_regex=allow_origin_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(simulation.router)
app.include_router(data.router)
app.include_router(flux.router)
app.include_router(pathway.router)
app.include_router(sensitivity.router)


@app.get("/")
def read_root():
    return {"message": "RBC Metabolic Model API is running"}
