"""
Ranking API Routes — wraps MLRankingService for React frontend consumption.
"""
from fastapi import APIRouter, Query, BackgroundTasks, HTTPException
from typing import Optional
import sys
from pathlib import Path

# Ensure the backend root is on the path so services resolve correctly
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.services.ml_ranking_service import ml_ranking_service

router = APIRouter()

@router.get("/list")
def get_ranked_list(
    equipment_type: Optional[str] = Query(default=None),
    country: Optional[str] = Query(default=None),
    top_k: int = Query(default=50),
    force_heuristic: bool = Query(default=False)
):
    try:
        df = ml_ranking_service.get_ranked_list(
            equipment_type=equipment_type if equipment_type != "All Equipment Types" else None,
            country=country if country != "All Countries" else None,
            top_k=top_k,
            force_heuristic=force_heuristic
        )
        if df.empty:
            return {"rankings": []}
            
        # Convert to records
        records = df.to_dict(orient="records")
        return {"rankings": records}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/model-status")
def get_model_status():
    try:
        available = ml_ranking_service.is_model_available()
        metadata = ml_ranking_service.get_model_metadata() if available else {}
        return {"available": available, "metadata": metadata}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/equipment-types")
def get_equipment_types():
    try:
        return {"equipment_types": ml_ranking_service.get_equipment_types()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/countries")
def get_countries():
    try:
        return {"countries": ml_ranking_service.get_countries()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
