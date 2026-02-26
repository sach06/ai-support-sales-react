"""
Export API Routes — Handle downloading the generated profile as DOCX or PDF.
"""
from fastapi import APIRouter, HTTPException, BackgroundTasks, Path as URLPath, Body
from fastapi.responses import StreamingResponse
from typing import Dict, Any
import sys
from pathlib import Path
from urllib.parse import quote

# Ensure the backend root is on the path so services resolve correctly
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.services.export_service import export_service
from app.services.enhanced_export_service import enhanced_export_service

router = APIRouter()

@router.post("/docx")
def export_docx(payload: Dict[str, Any] = Body(...)):
    """Export profile to DOCX."""
    profile = payload.get("profile")
    customer_name = payload.get("customer_name")
    
    if not profile or not customer_name:
        raise HTTPException(status_code=400, detail="Missing profile or customer_name in payload")
        
    try:
        buffer = export_service.generate_docx(profile, customer_name)
        filename = export_service.generate_filename(customer_name, "docx")
        
        return StreamingResponse(
            buffer,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={"Content-Disposition": f"attachment; filename*=utf-8''{quote(filename)}"}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/pdf")
def export_pdf(payload: Dict[str, Any] = Body(...)):
    """Export profile to Enhanced PDF."""
    profile = payload.get("profile")
    customer_name = payload.get("customer_name")
    
    if not profile or not customer_name:
        raise HTTPException(status_code=400, detail="Missing profile or customer_name in payload")
        
    try:
        buffer = enhanced_export_service.generate_enhanced_pdf(profile, customer_name)
        filename = export_service.generate_filename(customer_name, "pdf")
        
        return StreamingResponse(
            buffer,
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename*=utf-8''{quote(filename)}"}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
