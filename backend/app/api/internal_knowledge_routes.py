"""
Internal knowledge indexing and status routes.
"""
from fastapi import APIRouter, Body, HTTPException
from typing import Any, Dict, List, Optional
import threading
import time

from app.services.internal_knowledge_service import internal_knowledge_service
from app.utils.json_utils import json_safe_sanitize

router = APIRouter()

# ── Background reindex state ──────────────────────────────────────────────────
_reindex_state: dict = {
    "running": False,
    "status": "idle",   # idle | running | done | error
    "message": "",
    "result": None,
    "started_at": None,
    "finished_at": None,
}
_reindex_lock = threading.Lock()


def _run_reindex(targets: list | None) -> None:
    global _reindex_state
    try:
        summary = internal_knowledge_service.reindex_network_documents(targets=targets)
        with _reindex_lock:
            _reindex_state["status"] = "done"
            _reindex_state["message"] = f"Indexed {summary.get('document_count', 0)} documents."
            _reindex_state["result"] = summary
    except Exception as exc:
        with _reindex_lock:
            _reindex_state["status"] = "error"
            _reindex_state["message"] = str(exc)
    finally:
        with _reindex_lock:
            _reindex_state["running"] = False
            _reindex_state["finished_at"] = time.time()


@router.get("/status")
def get_internal_knowledge_status():
    try:
        status = json_safe_sanitize(internal_knowledge_service.get_status())
        with _reindex_lock:
            status["reindex_job"] = {
                "running": _reindex_state["running"],
                "status": _reindex_state["status"],
                "message": _reindex_state["message"],
            }
        return status
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/reindex")
def reindex_internal_knowledge(payload: Optional[Dict[str, Any]] = Body(default=None)):
    """Start a background reindex of the network P: drive documents."""
    with _reindex_lock:
        if _reindex_state["running"]:
            return {"accepted": False, "status": "running", "message": "Reindex already in progress."}
        targets = None
        if payload and isinstance(payload.get("targets"), list):
            targets = [str(t) for t in payload["targets"] if str(t).strip()]
        _reindex_state.update({
            "running": True, "status": "running",
            "message": "Reindex started...", "result": None,
            "started_at": time.time(), "finished_at": None,
        })
    t = threading.Thread(target=_run_reindex, args=(targets,), daemon=True)
    t.start()
    return {"accepted": True, "status": "running", "message": "Reindex started in background."}


@router.get("/reindex-status")
def get_reindex_status():
    """Poll the background reindex job status."""
    with _reindex_lock:
        state = dict(_reindex_state)
    return json_safe_sanitize(state)
