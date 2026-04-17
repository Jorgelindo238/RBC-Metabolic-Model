"""CPU-oriented calibration worker service.

This service is meant to run on a long-lived Python host outside Vercel.
It keeps compatibility with the current `/calibration/run` web contract while
also exposing lightweight job endpoints for a future async UI migration.
"""

from __future__ import annotations

import json
import os
import secrets
import sqlite3
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock, Thread
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

_THIS_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _THIS_DIR.parent.parent
_SHARED_API = _PROJECT_ROOT / "apps" / "api"
_STREAMLIT_APP = _PROJECT_ROOT / "streamlit_app"
_SRC = _PROJECT_ROOT / "src"

for path in (_SHARED_API, _STREAMLIT_APP, _SRC):
    path_str = str(path)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)

import st_shim  # noqa: E402

st_shim.install()

from routers.calibration import CalibrationRequest  # noqa: E402
from services.mm_calibration_adapter import get_web_calibration_taxonomy, run_web_calibration  # noqa: E402

app = FastAPI(title="airbc Calibration Worker")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

_RUNTIME_DIR = _THIS_DIR / "runtime"
_JOBS_DB = _RUNTIME_DIR / "calibration_jobs.sqlite3"
_LOCK = Lock()
_AUTH_HEADER = "x-airbc-worker-secret"


class CalibrationJobCreateResponse(BaseModel):
    jobId: str
    status: str
    createdAt: str


class CalibrationJobRecord(BaseModel):
    jobId: str
    status: str
    createdAt: str
    updatedAt: str
    request: dict[str, Any]
    result: dict[str, Any] | None = None
    error: str | None = None


def _get_expected_shared_secret() -> str:
    return os.getenv("CALIBRATION_WORKER_SHARED_SECRET", "").strip()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _db() -> sqlite3.Connection:
    _RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(_JOBS_DB)
    connection.row_factory = sqlite3.Row
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS calibration_jobs (
            job_id TEXT PRIMARY KEY,
            status TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            request_json TEXT NOT NULL,
            result_json TEXT,
            error_text TEXT
        )
        """
    )
    return connection


def _read_job(job_id: str) -> CalibrationJobRecord | None:
    with _LOCK:
        connection = _db()
        try:
            row = connection.execute(
                """
                SELECT job_id, status, created_at, updated_at, request_json, result_json, error_text
                FROM calibration_jobs
                WHERE job_id = ?
                """,
                (job_id,),
            ).fetchone()
        finally:
            connection.close()

    if row is None:
        return None

    return CalibrationJobRecord(
        jobId=row["job_id"],
        status=row["status"],
        createdAt=row["created_at"],
        updatedAt=row["updated_at"],
        request=json.loads(row["request_json"]),
        result=json.loads(row["result_json"]) if row["result_json"] else None,
        error=row["error_text"],
    )


def _upsert_job(job_id: str, status: str, request_json: dict[str, Any], result: dict[str, Any] | None = None, error: str | None = None) -> None:
    now = _now_iso()
    with _LOCK:
        connection = _db()
        try:
            connection.execute(
                """
                INSERT INTO calibration_jobs (job_id, status, created_at, updated_at, request_json, result_json, error_text)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(job_id) DO UPDATE SET
                    status = excluded.status,
                    updated_at = excluded.updated_at,
                    request_json = excluded.request_json,
                    result_json = excluded.result_json,
                    error_text = excluded.error_text
                """,
                (
                    job_id,
                    status,
                    now,
                    now,
                    json.dumps(request_json),
                    json.dumps(result) if result is not None else None,
                    error,
                ),
            )
            connection.commit()
        finally:
            connection.close()


def _run_job(job_id: str, request_payload: dict[str, Any]) -> None:
    try:
        _upsert_job(job_id, "running", request_payload, result=None, error=None)
        result = run_web_calibration(CalibrationRequest(**request_payload))
        _upsert_job(job_id, "completed", request_payload, result=result, error=None)
    except Exception as exc:  # pragma: no cover - safety net for worker mode
        traceback.print_exc()
        _upsert_job(job_id, "failed", request_payload, result=None, error=str(exc))


@app.middleware("http")
async def require_calibration_worker_auth(request: Request, call_next):
    if not request.url.path.startswith("/calibration"):
        return await call_next(request)

    expected_secret = _get_expected_shared_secret()
    if not expected_secret:
        return JSONResponse(
            {
                "detail": (
                    "Calibration worker auth is not configured. "
                    "Set CALIBRATION_WORKER_SHARED_SECRET on the worker host."
                )
            },
            status_code=503,
        )

    provided_secret = request.headers.get(_AUTH_HEADER, "").strip()
    if not provided_secret or not secrets.compare_digest(provided_secret, expected_secret):
        return JSONResponse(
            {"detail": "Unauthorized calibration worker request."},
            status_code=401,
        )

    return await call_next(request)


@app.get("/")
def read_root():
    return {"message": "airbc Calibration Worker is running"}


@app.get("/calibration/available-parameters")
async def get_available_parameters():
    return get_web_calibration_taxonomy()


@app.post("/calibration/run")
async def run_calibration(request: CalibrationRequest):
    try:
        return run_web_calibration(request)
    except HTTPException:
        raise
    except Exception as exc:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/calibration/jobs", response_model=CalibrationJobCreateResponse)
async def create_calibration_job(request: CalibrationRequest):
    job_id = f"cal-{uuid4().hex}"
    payload = request.model_dump()
    _upsert_job(job_id, "queued", payload)
    Thread(target=_run_job, args=(job_id, payload), daemon=True).start()
    return CalibrationJobCreateResponse(jobId=job_id, status="queued", createdAt=_now_iso())


@app.get("/calibration/jobs/{job_id}", response_model=CalibrationJobRecord)
async def get_calibration_job(job_id: str):
    job = _read_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Calibration job not found")
    return job


@app.get("/calibration/jobs/{job_id}/result")
async def get_calibration_job_result(job_id: str):
    job = _read_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Calibration job not found")
    if job.status != "completed":
        raise HTTPException(status_code=409, detail=f"Calibration job is {job.status}")
    return job.result
