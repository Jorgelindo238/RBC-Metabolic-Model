import sys
from pathlib import Path

from fastapi import FastAPI

PROJECT_ROOT = Path(__file__).resolve().parents[1]
API_APP_DIR = PROJECT_ROOT / "apps" / "api"

for path in (PROJECT_ROOT, API_APP_DIR):
    path_str = str(path)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)

from vercel_app import app as inner_app  # noqa: E402

app = FastAPI(title="RBC Metabolic Model API")


@app.get("/")
def root():
    return {"message": "RBC Metabolic Model API is running", "mount": "/api"}


app.mount("/api", inner_app)
