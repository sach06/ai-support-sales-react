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
from app.utils.json_utils import df_to_json_safe
import json

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

        feature_explanations = {
            "equipment_age": "Older assets typically indicate stronger modernization demand and higher replacement potential.",
            "is_sms_oem": "Existing SMS footprint improves technical fit, installed-base continuity, and service upsell likelihood.",
            "crm_rating_num": "Higher CRM relationship quality usually correlates with easier access to decision-makers and faster deal conversion.",
            "crm_projects_count": "A deeper project history with the account signals proven execution trust and cross-sell potential.",
            "log_fte": "Larger organizations often have broader capex programs and better ability to fund major revamp projects.",
            "equipment_type_enc": "Certain equipment classes are structurally more likely to require upgrades based on lifecycle and process criticality.",
            "country_enc": "Country context captures structural market effects such as policy pressure, cost base, and investment cycles."
        }

        model_meta = ml_ranking_service.get_model_metadata() if not force_heuristic else {}
        model_importance = model_meta.get("feature_importance", {}) if isinstance(model_meta, dict) else {}
        if model_importance:
            sorted_features = sorted(model_importance.items(), key=lambda kv: float(kv[1]), reverse=True)
            default_top_feature_dict = {k: float(v) for k, v in sorted_features[:5]}
        else:
            default_top_feature_dict = {
                "equipment_age": 1.0,
                "is_sms_oem": 0.85,
                "crm_rating_num": 0.8,
                "crm_projects_count": 0.75,
                "log_fte": 0.7,
            }
            
        # Convert to records
        records = df.to_dict(orient="records")
        for rec in records:
            age = rec.get("equipment_age", 0)
            if age >= 30:
                rec["opportunity_type"] = "OEM Replacement"
                rec["opportunity_description"] = f"Equipment is {age:.1f} years old. High probability of full replacement."
            elif age >= 15:
                rec["opportunity_type"] = "Revamping / Upgrade"
                rec["opportunity_description"] = f"Equipment is {age:.1f} years old. Prime candidate for modernization."
            else:
                rec["opportunity_type"] = "Service Contract"
                rec["opportunity_description"] = f"Modern equipment ({age:.1f} yrs). Focus on predictive maintenance and spares."

            if not rec.get("top_features"):
                rec["top_features"] = json.dumps(default_top_feature_dict)
            rec["driver_explanations"] = feature_explanations
                
        from app.utils.json_utils import json_safe_sanitize
        return {"rankings": json_safe_sanitize(records)}
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
