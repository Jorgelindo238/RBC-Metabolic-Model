"""Persistence helpers for Monitoring alert workflow state and transition history."""

from __future__ import annotations

import json
import os
import sqlite3
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from threading import Lock
from typing import Any, Dict, List, Optional, Tuple

ALLOWED_WORKFLOW_STATUSES = {
    "New",
    "Acknowledged",
    "In review",
    "Escalated",
    "Resolved",
}

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_DATA_DIR = _PROJECT_ROOT / "data"
_SQLITE_DB_FILE = _DATA_DIR / "monitoring_alerts.sqlite3"
_LEGACY_RUNTIME_FILE = _DATA_DIR / "monitoring_alert_workflows.runtime.json"
_SUPABASE_STATE_TABLE = "monitoring_alert_workflow_states"
_SUPABASE_HISTORY_TABLE = "monitoring_alert_workflow_history"
_PERSISTENCE_LOCK = Lock()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _canonical_text(value: object) -> Optional[str]:
    if not isinstance(value, str):
        return None
    trimmed = value.strip()
    return trimmed or None


def _normalize_status(value: object) -> Optional[str]:
    if value in ALLOWED_WORKFLOW_STATUSES:
        return str(value)
    return None


def _supabase_config() -> Optional[Tuple[str, str]]:
    base_url = os.environ.get("SUPABASE_URL")
    service_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not base_url or not service_key:
        return None
    return base_url.rstrip("/"), service_key


def _supabase_request(
    method: str,
    path: str,
    *,
    params: Optional[Dict[str, str]] = None,
    body: Optional[Dict[str, Any]] = None,
    prefer: Optional[str] = None,
) -> Any:
    config = _supabase_config()
    if not config:
        raise RuntimeError("Supabase persistence is not configured.")

    base_url, service_key = config
    endpoint = f"{base_url}/rest/v1/{path.lstrip('/')}"
    if params:
        endpoint = f"{endpoint}?{urllib.parse.urlencode(params)}"

    payload = json.dumps(body).encode("utf-8") if body is not None else None
    request = urllib.request.Request(endpoint, data=payload, method=method.upper())
    request.add_header("Accept", "application/json")
    request.add_header("apikey", service_key)
    request.add_header("Authorization", f"Bearer {service_key}")
    if body is not None:
        request.add_header("Content-Type", "application/json")
    if prefer:
        request.add_header("Prefer", prefer)

    try:
        with urllib.request.urlopen(request) as response:
            raw = response.read().decode("utf-8").strip()
            if not raw:
                return None
            return json.loads(raw)
    except urllib.error.HTTPError as exc:
        body_text = exc.read().decode("utf-8")
        raise RuntimeError(f"Supabase request failed ({exc.code}): {body_text}") from exc


@lru_cache(maxsize=1)
def _monitoring_workflow_backend() -> str:
    config = _supabase_config()
    if not config:
        return "sqlite"

    try:
        _supabase_request(
            "GET",
            _SUPABASE_STATE_TABLE,
            params={"select": "alert_id", "limit": "1"},
        )
        return "supabase"
    except Exception:
        return "sqlite"


def _sqlite_connection() -> sqlite3.Connection:
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(_SQLITE_DB_FILE)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def _ensure_sqlite_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS monitoring_alert_workflow_states (
            alert_id TEXT PRIMARY KEY,
            bag_id TEXT NOT NULL UNIQUE,
            workflow_status TEXT NOT NULL,
            note TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            updated_by TEXT
        );

        CREATE TABLE IF NOT EXISTS monitoring_alert_workflow_history (
            transition_id INTEGER PRIMARY KEY AUTOINCREMENT,
            alert_id TEXT NOT NULL,
            bag_id TEXT NOT NULL,
            previous_status TEXT NOT NULL,
            next_status TEXT NOT NULL,
            changed_at TEXT NOT NULL,
            note TEXT,
            updated_by TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_monitoring_alert_workflow_states_bag_id
            ON monitoring_alert_workflow_states (bag_id);

        CREATE INDEX IF NOT EXISTS idx_monitoring_alert_workflow_states_updated_at
            ON monitoring_alert_workflow_states (updated_at DESC);

        CREATE INDEX IF NOT EXISTS idx_monitoring_alert_workflow_history_bag_id
            ON monitoring_alert_workflow_history (bag_id);

        CREATE INDEX IF NOT EXISTS idx_monitoring_alert_workflow_history_changed_at
            ON monitoring_alert_workflow_history (changed_at DESC);
        """
    )


def _sqlite_seed_from_legacy_runtime_file(connection: sqlite3.Connection) -> None:
    if not _LEGACY_RUNTIME_FILE.exists():
        return

    current_count = connection.execute(
        "SELECT COUNT(*) FROM monitoring_alert_workflow_states"
    ).fetchone()[0]
    if int(current_count or 0) > 0:
        return

    try:
        payload = json.loads(_LEGACY_RUNTIME_FILE.read_text(encoding="utf-8"))
    except Exception:
        return

    if not isinstance(payload, list):
        return

    for item in payload:
        record = _normalize_state_payload(item)
        if not record:
            continue
        connection.execute(
            """
            INSERT INTO monitoring_alert_workflow_states (
                alert_id, bag_id, workflow_status, note, created_at, updated_at, updated_by
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(alert_id) DO UPDATE SET
                bag_id = excluded.bag_id,
                workflow_status = excluded.workflow_status,
                note = excluded.note,
                created_at = excluded.created_at,
                updated_at = excluded.updated_at,
                updated_by = excluded.updated_by
            """,
            (
                record["alertId"],
                record["bagId"],
                record["workflowStatus"],
                record.get("note"),
                record["createdAt"],
                record["updatedAt"],
                record.get("updatedBy"),
            ),
        )

    connection.commit()


def _normalize_state_payload(payload: object) -> Optional[Dict[str, object]]:
    if not isinstance(payload, dict):
        return None

    bag_id = _canonical_text(payload.get("bagId") or payload.get("bag_id"))
    alert_id = _canonical_text(payload.get("alertId") or payload.get("alert_id"))
    if not bag_id and alert_id and alert_id.upper().startswith("ALERT-"):
        bag_id = alert_id[6:]

    workflow_status = _normalize_status(
        payload.get("workflowStatus")
        or payload.get("workflow_status")
        or payload.get("status")
    )
    if not bag_id or not workflow_status:
        return None

    now = _now_iso()
    created_at = (
        _canonical_text(payload.get("createdAt"))
        or _canonical_text(payload.get("created_at"))
        or _canonical_text(payload.get("updatedAt"))
        or _canonical_text(payload.get("updated_at"))
        or now
    )
    updated_at = (
        _canonical_text(payload.get("updatedAt"))
        or _canonical_text(payload.get("updated_at"))
        or created_at
    )

    return {
        "alertId": (alert_id or f"ALERT-{bag_id}").upper(),
        "bagId": bag_id.upper(),
        "workflowStatus": workflow_status,
        "note": _canonical_text(payload.get("note")),
        "createdAt": created_at,
        "updatedAt": updated_at,
        "updatedBy": _canonical_text(payload.get("updatedBy") or payload.get("updated_by")),
    }


def _normalize_transition_payload(payload: object) -> Optional[Dict[str, object]]:
    if not isinstance(payload, dict):
        return None

    bag_id = _canonical_text(payload.get("bagId") or payload.get("bag_id"))
    alert_id = _canonical_text(payload.get("alertId") or payload.get("alert_id"))
    previous_status = _normalize_status(
        payload.get("previousStatus") or payload.get("previous_status")
    )
    next_status = _normalize_status(payload.get("nextStatus") or payload.get("next_status"))
    changed_at = (
        _canonical_text(payload.get("changedAt"))
        or _canonical_text(payload.get("changed_at"))
        or _canonical_text(payload.get("updatedAt"))
        or _canonical_text(payload.get("updated_at"))
        or _now_iso()
    )

    if not bag_id or not previous_status or not next_status:
        return None

    return {
        "alertId": (alert_id or f"ALERT-{bag_id}").upper(),
        "bagId": bag_id.upper(),
        "previousStatus": previous_status,
        "nextStatus": next_status,
        "changedAt": changed_at,
        "note": _canonical_text(payload.get("note")),
        "updatedBy": _canonical_text(payload.get("updatedBy") or payload.get("updated_by")),
    }


def _sqlite_state_row_to_record(row: sqlite3.Row) -> Dict[str, object]:
    return {
        "alertId": str(row["alert_id"]).upper(),
        "bagId": str(row["bag_id"]).upper(),
        "workflowStatus": row["workflow_status"],
        "note": row["note"],
        "createdAt": row["created_at"],
        "updatedAt": row["updated_at"],
        "updatedBy": row["updated_by"],
    }


def _sqlite_transition_row_to_record(row: sqlite3.Row) -> Dict[str, object]:
    return {
        "alertId": str(row["alert_id"]).upper(),
        "bagId": str(row["bag_id"]).upper(),
        "previousStatus": row["previous_status"],
        "nextStatus": row["next_status"],
        "changedAt": row["changed_at"],
        "note": row["note"],
        "updatedBy": row["updated_by"],
    }


def _sqlite_list_states() -> List[Dict[str, object]]:
    with _PERSISTENCE_LOCK:
        connection = _sqlite_connection()
        try:
            _ensure_sqlite_schema(connection)
            _sqlite_seed_from_legacy_runtime_file(connection)
            rows = connection.execute(
                """
                SELECT alert_id, bag_id, workflow_status, note, created_at, updated_at, updated_by
                FROM monitoring_alert_workflow_states
                ORDER BY updated_at DESC, alert_id DESC
                """
            ).fetchall()
            return [_sqlite_state_row_to_record(row) for row in rows]
        finally:
            connection.close()


def _sqlite_list_history(limit: int = 100) -> List[Dict[str, object]]:
    with _PERSISTENCE_LOCK:
        connection = _sqlite_connection()
        try:
            _ensure_sqlite_schema(connection)
            rows = connection.execute(
                """
                SELECT alert_id, bag_id, previous_status, next_status, changed_at, note, updated_by
                FROM monitoring_alert_workflow_history
                ORDER BY changed_at DESC, transition_id DESC
                LIMIT ?
                """,
                (max(1, int(limit)),),
            ).fetchall()
            return [_sqlite_transition_row_to_record(row) for row in rows]
        finally:
            connection.close()


def _sqlite_upsert_state(
    bag_id: str,
    workflow_status: str,
    *,
    note: Optional[str] = None,
    updated_by: Optional[str] = None,
) -> Dict[str, object]:
    normalized_bag_id = bag_id.strip().upper()
    alert_id = f"ALERT-{normalized_bag_id}"
    now = _now_iso()

    with _PERSISTENCE_LOCK:
        connection = _sqlite_connection()
        try:
            _ensure_sqlite_schema(connection)
            current_row = connection.execute(
                """
                SELECT alert_id, bag_id, workflow_status, note, created_at, updated_at, updated_by
                FROM monitoring_alert_workflow_states
                WHERE alert_id = ? OR bag_id = ?
                LIMIT 1
                """,
                (alert_id, normalized_bag_id),
            ).fetchone()

            if current_row is not None:
                current_record = _sqlite_state_row_to_record(current_row)
                next_note = note if note is not None else current_record["note"]
                next_updated_by = updated_by if updated_by is not None else current_record["updatedBy"]

                if (
                    current_record["workflowStatus"] == workflow_status
                    and current_record["note"] == next_note
                    and current_record["updatedBy"] == next_updated_by
                ):
                    return current_record

                if current_record["workflowStatus"] != workflow_status:
                    connection.execute(
                        """
                        INSERT INTO monitoring_alert_workflow_history (
                            alert_id, bag_id, previous_status, next_status, changed_at, note, updated_by
                        ) VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            current_record["alertId"],
                            current_record["bagId"],
                            current_record["workflowStatus"],
                            workflow_status,
                            now,
                            next_note,
                            next_updated_by,
                        ),
                    )

                connection.execute(
                    """
                    UPDATE monitoring_alert_workflow_states
                    SET workflow_status = ?,
                        note = ?,
                        updated_at = ?,
                        updated_by = ?
                    WHERE alert_id = ?
                    """,
                    (
                        workflow_status,
                        next_note,
                        now,
                        next_updated_by,
                        current_record["alertId"],
                    ),
                )
                connection.commit()

                updated_row = connection.execute(
                    """
                    SELECT alert_id, bag_id, workflow_status, note, created_at, updated_at, updated_by
                    FROM monitoring_alert_workflow_states
                    WHERE alert_id = ?
                    LIMIT 1
                    """,
                    (current_record["alertId"],),
                ).fetchone()
                if updated_row is None:
                    raise RuntimeError("Failed to load the updated monitoring alert workflow state.")
                return _sqlite_state_row_to_record(updated_row)

            if workflow_status != "New":
                connection.execute(
                    """
                    INSERT INTO monitoring_alert_workflow_history (
                        alert_id, bag_id, previous_status, next_status, changed_at, note, updated_by
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        alert_id,
                        normalized_bag_id,
                        "New",
                        workflow_status,
                        now,
                        note,
                        updated_by,
                    ),
                )

            connection.execute(
                """
                INSERT INTO monitoring_alert_workflow_states (
                    alert_id, bag_id, workflow_status, note, created_at, updated_at, updated_by
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    alert_id,
                    normalized_bag_id,
                    workflow_status,
                    note,
                    now,
                    now,
                    updated_by,
                ),
            )
            connection.commit()

            created_row = connection.execute(
                """
                SELECT alert_id, bag_id, workflow_status, note, created_at, updated_at, updated_by
                FROM monitoring_alert_workflow_states
                WHERE alert_id = ?
                LIMIT 1
                """,
                (alert_id,),
            ).fetchone()
            if created_row is None:
                raise RuntimeError("Failed to load the created monitoring alert workflow state.")
            return _sqlite_state_row_to_record(created_row)
        finally:
            connection.close()


def _supabase_list_states() -> List[Dict[str, object]]:
    payload = _supabase_request(
        "GET",
        _SUPABASE_STATE_TABLE,
        params={"select": "*", "order": "updated_at.desc"},
    )
    if not payload:
        return []
    if not isinstance(payload, list):
        raise RuntimeError("Unexpected monitoring workflow state payload from Supabase.")

    records: List[Dict[str, object]] = []
    for item in payload:
        record = _normalize_state_payload(item)
        if record:
            records.append(record)
    return records


def _supabase_list_history(limit: int = 100) -> List[Dict[str, object]]:
    payload = _supabase_request(
        "GET",
        _SUPABASE_HISTORY_TABLE,
        params={
            "select": "*",
            "order": "changed_at.desc",
            "limit": str(max(1, int(limit))),
        },
    )
    if not payload:
        return []
    if not isinstance(payload, list):
        raise RuntimeError("Unexpected monitoring workflow history payload from Supabase.")

    records: List[Dict[str, object]] = []
    for item in payload:
        record = _normalize_transition_payload(item)
        if record:
            records.append(record)
    return records


def _supabase_upsert_state(
    bag_id: str,
    workflow_status: str,
    *,
    note: Optional[str] = None,
    updated_by: Optional[str] = None,
) -> Dict[str, object]:
    payload = _supabase_request(
        "POST",
        f"rpc/upsert_monitoring_alert_workflow_state",
        body={
            "p_bag_id": bag_id,
            "p_workflow_status": workflow_status,
            "p_note": note,
            "p_updated_by": updated_by,
        },
    )
    if not payload:
        raise RuntimeError("Supabase returned an empty monitoring workflow response.")

    if isinstance(payload, list):
        payload = payload[0] if payload else None
    if not isinstance(payload, dict):
        raise RuntimeError("Unexpected monitoring workflow response from Supabase.")

    record = _normalize_state_payload(payload)
    if not record:
        raise RuntimeError("Supabase returned an invalid monitoring workflow record.")
    return record


def list_alert_workflow_states() -> List[Dict[str, object]]:
    backend = _monitoring_workflow_backend()
    if backend == "supabase":
        try:
            return _supabase_list_states()
        except Exception:
            # If the configured Supabase schema is unavailable at runtime, keep the
            # Monitoring workflow operational by falling back to the local DB file.
            pass
    return _sqlite_list_states()


def list_alert_workflow_history(limit: int = 100) -> List[Dict[str, object]]:
    backend = _monitoring_workflow_backend()
    if backend == "supabase":
        try:
            return _supabase_list_history(limit=limit)
        except Exception:
            pass
    return _sqlite_list_history(limit=limit)


def upsert_alert_workflow_state(
    bag_id: str,
    workflow_status: str,
    *,
    note: Optional[str] = None,
    updated_by: Optional[str] = None,
) -> Dict[str, object]:
    backend = _monitoring_workflow_backend()
    if backend == "supabase":
        try:
            return _supabase_upsert_state(
                bag_id,
                workflow_status,
                note=note,
                updated_by=updated_by,
            )
        except Exception:
            pass
    return _sqlite_upsert_state(
        bag_id,
        workflow_status,
        note=note,
        updated_by=updated_by,
    )
