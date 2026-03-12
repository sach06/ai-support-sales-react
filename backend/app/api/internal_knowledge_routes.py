"""
Internal knowledge indexing and status routes.
"""
from fastapi import APIRouter, Body, HTTPException
from typing import Any, Dict, List, Optional

from app.services.internal_knowledge_service import internal_knowledge_service
from app.utils.json_utils import json_safe_sanitize

router = APIRouter()


@router.get("/status")
def get_internal_knowledge_status():
    try:
        return json_safe_sanitize(internal_knowledge_service.get_status())
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/reindex")
def reindex_internal_knowledge(payload: Optional[Dict[str, Any]] = Body(default=None)):
    try:
        targets = None
        if payload and isinstance(payload.get("targets"), list):
            targets = [str(target) for target in payload["targets"] if str(target).strip()]
        summary = internal_knowledge_service.reindex_network_documents(targets=targets)
        return json_safe_sanitize(summary)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))