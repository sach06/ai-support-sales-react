"""
Ranking API Routes — wraps MLRankingService for React frontend consumption.
"""
from fastapi import APIRouter, Query, HTTPException
from typing import Optional
import sys
import threading
import time
from pathlib import Path

# Ensure the backend root is on the path so services resolve correctly
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.services.ml_ranking_service import ml_ranking_service
from app.utils.json_utils import df_to_json_safe
import json

router = APIRouter()

# ── Background retrain state ──────────────────────────────────────────────────
_retrain_state: dict = {
    "running": False,
    "status": "idle",   # idle | running | done | error
    "message": "",
    "result": None,
    "started_at": None,
    "finished_at": None,
}
_retrain_lock = threading.Lock()


def _run_retrain(snapshot_id: str) -> None:
    global _retrain_state
    with _retrain_lock:
        _retrain_state["running"] = True
        _retrain_state["status"] = "running"
        _retrain_state["message"] = "Training in progress..."
        _retrain_state["result"] = None
        _retrain_state["started_at"] = time.time()
        _retrain_state["finished_at"] = None
    try:
        result = ml_ranking_service.retrain_model(data_snapshot_id=snapshot_id)
        with _retrain_lock:
            _retrain_state["status"] = "done"
            _retrain_state["message"] = "Training completed successfully."
            _retrain_state["result"] = result
    except Exception as exc:
        with _retrain_lock:
            _retrain_state["status"] = "error"
            _retrain_state["message"] = str(exc)
    finally:
        with _retrain_lock:
            _retrain_state["running"] = False
            _retrain_state["finished_at"] = time.time()


def _top_knowledge_theme(record: dict) -> str:
    candidates = {
        "service": float(record.get("knowledge_service_signal", 0) or 0),
        "inspection": float(record.get("knowledge_inspection_signal", 0) or 0),
        "modernization": float(record.get("knowledge_modernization_signal", 0) or 0),
        "digital": float(record.get("knowledge_digital_signal", 0) or 0),
        "decarbonization": float(record.get("knowledge_decarbonization_signal", 0) or 0),
        "project": float(record.get("knowledge_project_signal", 0) or 0),
        "quality": float(record.get("knowledge_quality_signal", 0) or 0),
    }
    return max(candidates, key=candidates.get) if candidates else "service"


def _knowledge_feature_dict(record: dict) -> dict:
    return {
        "knowledge_doc_count": float(record.get("knowledge_doc_count", 0) or 0),
        "knowledge_best_match_score": float(record.get("knowledge_best_match_score", 0) or 0),
        "knowledge_avg_match_score": float(record.get("knowledge_avg_match_score", 0) or 0),
        "knowledge_service_signal": float(record.get("knowledge_service_signal", 0) or 0),
        "knowledge_inspection_signal": float(record.get("knowledge_inspection_signal", 0) or 0),
        "knowledge_modernization_signal": float(record.get("knowledge_modernization_signal", 0) or 0),
        "knowledge_digital_signal": float(record.get("knowledge_digital_signal", 0) or 0),
        "knowledge_decarbonization_signal": float(record.get("knowledge_decarbonization_signal", 0) or 0),
        "knowledge_project_signal": float(record.get("knowledge_project_signal", 0) or 0),
        "knowledge_quality_signal": float(record.get("knowledge_quality_signal", 0) or 0),
    }

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
            "country_enc": "Country context captures structural market effects such as policy pressure, cost base, and investment cycles.",
            "knowledge_doc_count": "A larger body of internal project and service references indicates stronger institutional knowledge and more proven touchpoints.",
            "knowledge_best_match_score": "Strong document matches suggest direct evidence linking the account to SMS project, quality, or service history.",
            "knowledge_avg_match_score": "Consistently relevant internal evidence raises confidence that the account is strategically actionable.",
            "knowledge_service_signal": "Service-heavy internal evidence points to spare parts, maintenance, and long-term service potential.",
            "knowledge_inspection_signal": "Inspection and acceptance evidence indicates recent technical interaction and a route into follow-on upgrades.",
            "knowledge_modernization_signal": "Upgrade and revamp references point to capex appetite and modernization demand.",
            "knowledge_digital_signal": "Automation and digital references indicate optimization scope beyond mechanical replacement.",
            "knowledge_decarbonization_signal": "Decarbonization language signals likely relevance for EAF, electrification, and green-steel positioning.",
            "knowledge_project_signal": "Project-document density indicates active execution context or recent commercial traction.",
            "knowledge_quality_signal": "Quality or issue references can indicate recovery work, retrofit demand, or service-led re-entry opportunities."
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
            if float(rec.get("knowledge_doc_count", 0) or 0) > 0:
                enriched = _knowledge_feature_dict(rec)
                top_theme = _top_knowledge_theme(rec)
                rec["top_features"] = json.dumps({
                    top_theme and f"knowledge_{top_theme}_signal": max(
                        float(rec.get(f"knowledge_{top_theme}_signal", 0) or 0),
                        0.01,
                    ),
                    **enriched,
                })
                rec["knowledge_summary"] = (
                    f"{int(rec.get('knowledge_doc_count', 0) or 0)} matched internal docs; "
                    f"dominant theme: {top_theme}."
                )
            else:
                rec["knowledge_summary"] = "No matched internal evidence for this account."
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


@router.post("/retrain")
def retrain_model(snapshot_id: str = Query(default="live_duckdb")):
    """Start model retraining in a background thread (non-blocking)."""
    with _retrain_lock:
        if _retrain_state["running"]:
            return {"accepted": False, "status": "running", "message": "Retraining already in progress."}
        # Reset before starting
        _retrain_state.update({
            "running": True, "status": "running",
            "message": "Training started...", "result": None,
            "started_at": time.time(), "finished_at": None,
        })
    t = threading.Thread(target=_run_retrain, args=(snapshot_id,), daemon=True)
    t.start()
    return {"accepted": True, "status": "running", "message": "Retraining started in background."}


@router.get("/retrain-status")
def get_retrain_status():
    """Poll the background retrain job status."""
    with _retrain_lock:
        state = dict(_retrain_state)
    from app.utils.json_utils import json_safe_sanitize
    return json_safe_sanitize(state)

