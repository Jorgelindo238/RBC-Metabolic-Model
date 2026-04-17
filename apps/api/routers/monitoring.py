"""Monitoring router - bag inventory intake and repository reads."""

from __future__ import annotations

import json
from pathlib import Path
from threading import Lock
from typing import Dict, List, Literal, Optional

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from services.monitoring_alerts_persistence import (
    ALLOWED_WORKFLOW_STATUSES,
    list_alert_workflow_history as load_monitoring_alert_workflow_history,
    list_alert_workflow_states as load_monitoring_alert_workflow_states,
    upsert_alert_workflow_state as persist_monitoring_alert_workflow_state,
)

router = APIRouter(prefix="/monitoring", tags=["monitoring"])

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
_DATA_DIR = _PROJECT_ROOT / "apps" / "api" / "data"
_RUNTIME_FILE = _DATA_DIR / "monitoring_bags.runtime.json"
_STORE_LOCK = Lock()

MonitoringSex = Literal["F", "M"]
MonitoringRiskBand = Literal["Low risk", "Watch", "Elevated"]
MonitoringBagStatus = Literal[
    "Fresh intake",
    "Forecast review",
    "Alert follow-up",
    "Under review",
    "Reserved",
]

MonitoringAlertWorkflowStatus = Literal[
    "New",
    "Acknowledged",
    "In review",
    "Escalated",
    "Resolved",
]


class MonitoringBagCreateRequest(BaseModel):
    bagId: str = Field(..., description="Canonical bag identifier")
    donorId: str = Field(..., description="Donor identifier")
    entryDate: str = Field(..., description="Bag entry date in YYYY-MM-DD format")
    age: int = Field(..., description="Donor age in years")
    sex: MonitoringSex = Field(..., description="Donor sex")
    medicalProfile: MonitoringRiskBand = Field(..., description="Operational risk band")
    repositoryStatus: MonitoringBagStatus = Field(..., description="Repository status")
    storageContext: str = Field(..., description="Storage location or rack context")


class MonitoringBagRecord(BaseModel):
    bagId: str
    donorId: str
    entryDate: str
    age: int
    sex: MonitoringSex
    medicalProfile: MonitoringRiskBand
    repositoryStatus: MonitoringBagStatus
    storageContext: str
    qualityState: str
    forecastState: str
    alerts: int
    linkedRuns: int
    monitoringEvents: int


class MonitoringAlertWorkflowUpdateRequest(BaseModel):
    workflowStatus: MonitoringAlertWorkflowStatus = Field(..., description="Operator workflow status")
    note: Optional[str] = Field(default=None, description="Optional operator note")
    updatedBy: Optional[str] = Field(default=None, description="Optional operator identity placeholder")


class MonitoringAlertWorkflowRecord(BaseModel):
    alertId: str
    bagId: str
    workflowStatus: MonitoringAlertWorkflowStatus
    note: Optional[str] = None
    createdAt: str
    updatedAt: str
    updatedBy: Optional[str] = None


class MonitoringAlertWorkflowTransitionRecord(BaseModel):
    alertId: str
    bagId: str
    previousStatus: MonitoringAlertWorkflowStatus
    nextStatus: MonitoringAlertWorkflowStatus
    changedAt: str
    note: Optional[str] = None
    updatedBy: Optional[str] = None


_DEFAULT_BAG_RECORDS: List[Dict[str, object]] = [
    {
        "bagId": "BAG-1042",
        "donorId": "DON-118",
        "entryDate": "2026-03-22",
        "age": 28,
        "sex": "F",
        "medicalProfile": "Low risk",
        "repositoryStatus": "Fresh intake",
        "storageContext": "Cold room A3 · rack 4",
        "qualityState": "Stable",
        "forecastState": "Stable through 72h",
        "alerts": 0,
        "linkedRuns": 1,
        "monitoringEvents": 4,
    },
    {
        "bagId": "BAG-1178",
        "donorId": "DON-244",
        "entryDate": "2026-03-21",
        "age": 41,
        "sex": "M",
        "medicalProfile": "Watch",
        "repositoryStatus": "Forecast review",
        "storageContext": "Cold room B1 · rack 2",
        "qualityState": "Early drift",
        "forecastState": "Watch 7d curve",
        "alerts": 1,
        "linkedRuns": 2,
        "monitoringEvents": 5,
    },
    {
        "bagId": "BAG-1211",
        "donorId": "DON-301",
        "entryDate": "2026-03-20",
        "age": 36,
        "sex": "F",
        "medicalProfile": "Elevated",
        "repositoryStatus": "Alert follow-up",
        "storageContext": "Cold room C2 · rack 1",
        "qualityState": "Quality drop projected",
        "forecastState": "Threshold near 14d",
        "alerts": 2,
        "linkedRuns": 2,
        "monitoringEvents": 7,
    },
    {
        "bagId": "BAG-1224",
        "donorId": "DON-322",
        "entryDate": "2026-03-19",
        "age": 32,
        "sex": "M",
        "medicalProfile": "Low risk",
        "repositoryStatus": "Reserved",
        "storageContext": "Cold room A1 · rack 7",
        "qualityState": "Stable",
        "forecastState": "Stable through 24h",
        "alerts": 0,
        "linkedRuns": 1,
        "monitoringEvents": 2,
    },
    {
        "bagId": "BAG-1250",
        "donorId": "DON-366",
        "entryDate": "2026-03-18",
        "age": 45,
        "sex": "F",
        "medicalProfile": "Elevated",
        "repositoryStatus": "Under review",
        "storageContext": "Cold room D3 · rack 5",
        "qualityState": "Lactate drift",
        "forecastState": "Short horizon watch",
        "alerts": 1,
        "linkedRuns": 2,
        "monitoringEvents": 6,
    },
    {
        "bagId": "BAG-1288",
        "donorId": "DON-401",
        "entryDate": "2026-03-17",
        "age": 30,
        "sex": "M",
        "medicalProfile": "Watch",
        "repositoryStatus": "Alert follow-up",
        "storageContext": "Cold room B3 · rack 1",
        "qualityState": "Review due",
        "forecastState": "Projected drop",
        "alerts": 1,
        "linkedRuns": 1,
        "monitoringEvents": 5,
    },
]


def _ensure_runtime_dir() -> None:
    _DATA_DIR.mkdir(parents=True, exist_ok=True)


def _default_runtime_records() -> List[Dict[str, object]]:
    return [dict(record) for record in _DEFAULT_BAG_RECORDS]


def _canonical_text(value: object) -> Optional[str]:
    if not isinstance(value, str):
        return None

    trimmed = value.strip()
    return trimmed or None


def _normalize_entry_date(value: object) -> Optional[str]:
    trimmed = _canonical_text(value)
    if not trimmed:
        return None

    try:
        from datetime import date as _date

        parsed = _date.fromisoformat(trimmed)
    except Exception:
        return None

    return parsed.isoformat()


def _normalize_count(value: object, fallback: int = 0) -> int:
    try:
        numeric_value = int(value)
    except Exception:
        return fallback

    return numeric_value if numeric_value >= 0 else fallback


def _normalize_bag_record(payload: object) -> Optional[Dict[str, object]]:
    if not isinstance(payload, dict):
        return None

    bag_id = _canonical_text(payload.get("bagId"))
    donor_id = _canonical_text(payload.get("donorId"))
    entry_date = _normalize_entry_date(payload.get("entryDate"))
    age = _normalize_count(payload.get("age"), fallback=-1)
    sex = payload.get("sex")
    medical_profile = payload.get("medicalProfile")
    repository_status = payload.get("repositoryStatus") or payload.get("status")
    storage_context = _canonical_text(payload.get("storageContext"))
    quality_state = _canonical_text(payload.get("qualityState")) or "Stable"
    forecast_state = _canonical_text(payload.get("forecastState")) or "Forecast pending"
    alerts = _normalize_count(payload.get("alerts"))
    linked_runs = _normalize_count(payload.get("linkedRuns"))
    monitoring_events = _normalize_count(payload.get("monitoringEvents", payload.get("linkedEvents")))

    if (
        not bag_id
        or not donor_id
        or not entry_date
        or age <= 0
        or sex not in {"F", "M"}
        or medical_profile not in {"Low risk", "Watch", "Elevated"}
        or repository_status not in {
            "Fresh intake",
            "Forecast review",
            "Alert follow-up",
            "Under review",
            "Reserved",
        }
        or not storage_context
    ):
        return None

    return {
        "bagId": bag_id.upper(),
        "donorId": donor_id.upper(),
        "entryDate": entry_date,
        "age": age,
        "sex": sex,
        "medicalProfile": medical_profile,
        "repositoryStatus": repository_status,
        "storageContext": storage_context,
        "qualityState": quality_state,
        "forecastState": forecast_state,
        "alerts": alerts,
        "linkedRuns": linked_runs,
        "monitoringEvents": monitoring_events,
    }


def _load_runtime_records() -> List[Dict[str, object]]:
    _ensure_runtime_dir()

    if not _RUNTIME_FILE.exists():
        records = _default_runtime_records()
        _write_runtime_records(records)
        return records

    try:
        payload = json.loads(_RUNTIME_FILE.read_text(encoding="utf-8"))
    except Exception:
        records = _default_runtime_records()
        _write_runtime_records(records)
        return records

    if not isinstance(payload, list):
        records = _default_runtime_records()
        _write_runtime_records(records)
        return records

    normalized: List[Dict[str, object]] = []
    for item in payload:
        record = _normalize_bag_record(item)
        if record:
            normalized.append(record)

    if not normalized:
        normalized = _default_runtime_records()
        _write_runtime_records(normalized)
        return normalized

    if normalized != payload:
        _write_runtime_records(normalized)

    return normalized


def _write_runtime_records(records: List[Dict[str, object]]) -> None:
    _ensure_runtime_dir()
    payload = json.dumps(records, indent=2, sort_keys=True)
    _RUNTIME_FILE.write_text(payload, encoding="utf-8")


def _normalize_workflow_status(value: object) -> Optional[MonitoringAlertWorkflowStatus]:
    if value in ALLOWED_WORKFLOW_STATUSES:
        return value  # type: ignore[return-value]
    return None


def _normalize_optional_text(value: object) -> Optional[str]:
    return _canonical_text(value)


def _normalize_alert_workflow_update_request(
    bag_id: str,
    request: MonitoringAlertWorkflowUpdateRequest,
) -> Dict[str, object]:
    normalized_bag_id = _canonical_text(bag_id)
    if not normalized_bag_id:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="bagId is required.")

    workflow_status = _normalize_workflow_status(request.workflowStatus)
    if not workflow_status:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="workflowStatus must be one of: New, Acknowledged, In review, Escalated, Resolved.",
        )

    return {
        "bagId": normalized_bag_id.upper(),
        "workflowStatus": workflow_status,
        "note": _normalize_optional_text(request.note),
        "updatedBy": _normalize_optional_text(request.updatedBy),
    }


def _normalize_create_request(request: MonitoringBagCreateRequest) -> Dict[str, object]:
    bag_id = _canonical_text(request.bagId)
    donor_id = _canonical_text(request.donorId)
    entry_date = _normalize_entry_date(request.entryDate)
    storage_context = _canonical_text(request.storageContext)

    if not bag_id:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="bagId is required.")
    if not donor_id:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="donorId is required.")
    if not entry_date:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="entryDate must be a valid YYYY-MM-DD date.")
    if request.age <= 0:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="age must be greater than zero.")
    if not storage_context:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="storageContext is required.")

    return {
        "bagId": bag_id.upper(),
        "donorId": donor_id.upper(),
        "entryDate": entry_date,
        "age": int(request.age),
        "sex": request.sex,
        "medicalProfile": request.medicalProfile,
        "repositoryStatus": request.repositoryStatus,
        "storageContext": storage_context,
    }


def _build_canonical_bag_record(input_record: Dict[str, object]) -> Dict[str, object]:
    return {
        **input_record,
        "qualityState": "Stable",
        "forecastState": "Forecast pending",
        "alerts": 0,
        "linkedRuns": 0,
        "monitoringEvents": 0,
    }


@router.get("/alerts/workflow-states", response_model=List[MonitoringAlertWorkflowRecord])
def list_monitoring_alert_workflow_states():
    with _STORE_LOCK:
        try:
            return load_monitoring_alert_workflow_states()
        except RuntimeError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=str(exc),
            ) from exc


@router.get("/alerts/workflow-history", response_model=List[MonitoringAlertWorkflowTransitionRecord])
def list_monitoring_alert_workflow_history(limit: int = 100):
    with _STORE_LOCK:
        try:
            return load_monitoring_alert_workflow_history(limit=limit)
        except RuntimeError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=str(exc),
            ) from exc


@router.put("/alerts/{bag_id}/workflow", response_model=MonitoringAlertWorkflowRecord)
def update_monitoring_alert_workflow_state(
    bag_id: str,
    request: MonitoringAlertWorkflowUpdateRequest,
):
    with _STORE_LOCK:
        normalized = _normalize_alert_workflow_update_request(bag_id, request)
        try:
            return persist_monitoring_alert_workflow_state(
                normalized["bagId"],
                normalized["workflowStatus"],
                note=normalized["note"],
                updated_by=normalized["updatedBy"],
            )
        except RuntimeError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=str(exc),
            ) from exc


@router.get("/bags", response_model=List[MonitoringBagRecord])
def list_monitoring_bags():
    with _STORE_LOCK:
        return _load_runtime_records()


@router.post("/bags", response_model=MonitoringBagRecord, status_code=status.HTTP_201_CREATED)
def create_monitoring_bag(request: MonitoringBagCreateRequest):
    with _STORE_LOCK:
        records = _load_runtime_records()
        normalized = _normalize_create_request(request)

        if any(str(record.get("bagId", "")).upper() == normalized["bagId"] for record in records):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Bag {normalized['bagId']} already exists in the repository.",
            )

        created_record = _build_canonical_bag_record(normalized)
        next_records = [created_record, *records]
        _write_runtime_records(next_records)
        return created_record
