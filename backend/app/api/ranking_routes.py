"""
Ranking API Routes — wraps MLRankingService for React frontend consumption.
"""
from fastapi import APIRouter, Query, HTTPException
from typing import Optional
from functools import lru_cache
import re
import unicodedata
import sys
import threading
import time
from pathlib import Path

# Ensure the backend root is on the path so services resolve correctly
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.services.ml_ranking_service import ml_ranking_service
import app.services.historical_service as historical_service
from app.services.external_feature_service import external_feature_service
from app.services.web_enrichment_service import web_enrichment_service
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


def _normalize_company_name(name: str) -> str:
    raw = str(name or "").strip().lower()
    if not raw:
        return ""
    ascii_name = unicodedata.normalize("NFKD", raw).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "", ascii_name)


def _company_matches(candidate_name: str, target_name: str) -> bool:
    candidate_norm = _normalize_company_name(candidate_name)
    target_norm = _normalize_company_name(target_name)
    if not candidate_norm or not target_norm:
        return False
    if candidate_norm == target_norm:
        return True
    # Accept close legal-entity variations, e.g. suffix differences.
    return (
        candidate_norm.startswith(target_norm)
        or target_norm.startswith(candidate_norm)
        or candidate_norm in target_norm
        or target_norm in candidate_norm
    )


def _build_competitor_deep_dive(equipment_type: str | None, country: str | None, company_name: str | None) -> list[dict]:
    eq = equipment_type or "selected equipment"
    market = country or "the selected market"
    account = company_name or "the selected customer"

    return [
        {
            "competitor": "Primetals Technologies",
            "positioning": "Integrated steel plant packages with strong electrical and automation depth.",
            "threat_on_selected_scope": f"High if the customer seeks full-line modernization around {eq} with bundled digital stack.",
            "sms_counter_strategy": (
                f"Position SMS with performance-guaranteed scope, faster brownfield integration, and lifecycle service economics for {account} in {market}."
            ),
        },
        {
            "competitor": "Danieli Group",
            "positioning": "Aggressive capex offers and broad equipment portfolio in steel and non-ferrous.",
            "threat_on_selected_scope": f"High on cost-competitive bids, especially where replacement timing for {eq} is imminent.",
            "sms_counter_strategy": (
                "Lead with total-cost-of-ownership proof, reference performance, and phased modernization roadmap that reduces shutdown risk."
            ),
        },
        {
            "competitor": "Tenova",
            "positioning": "Strong sustainability and process optimization narrative in metals and mining.",
            "threat_on_selected_scope": f"Medium-to-high when decarbonization and energy intensity are core decision factors for {account}.",
            "sms_counter_strategy": (
                "Anchor on measurable decarbonization outcomes plus operational KPIs: yield stability, specific energy, and uptime."
            ),
        },
        {
            "competitor": "Thyssenkrupp Industrial Solutions",
            "positioning": "Large-scale plant engineering and EPC integration strengths.",
            "threat_on_selected_scope": "Medium for complex EPC-driven decisions with broad stakeholder governance.",
            "sms_counter_strategy": (
                "Differentiate via metallurgical process specialization and faster implementation cadence at critical bottleneck assets."
            ),
        },
        {
            "competitor": "Fives Group",
            "positioning": "Niche strength in selected thermal/process lines and modernization projects.",
            "threat_on_selected_scope": f"Medium where focused upgrades around {eq} can be split into smaller packages.",
            "sms_counter_strategy": (
                "Propose integrated package architecture where service, automation, and core process equipment deliver one accountable outcome."
            ),
        },
    ]


@lru_cache(maxsize=64)
def _cached_country_intelligence(country: str) -> dict:
    return web_enrichment_service.get_country_intelligence(country) or {}

@router.get("/list")
def get_ranked_list(
    equipment_type: Optional[str] = Query(default=None),
    country: Optional[str] = Query(default=None),
    company_name: Optional[str] = Query(default=None),
    top_k: int = Query(default=50),
    force_heuristic: bool = Query(default=False)
):
    try:
        company_filter = company_name.strip() if company_name and company_name != "All" else None

        # If a specific company is selected, request a broader candidate set once on the backend.
        # This avoids frontend over-fetch while ensuring the selected company can be pinned.
        effective_top_k = None if company_filter else top_k

        df = ml_ranking_service.get_ranked_list(
            equipment_type=equipment_type if equipment_type != "All Equipment Types" else None,
            country=country if country != "All Countries" else None,
            top_k=effective_top_k,
            force_heuristic=force_heuristic
        )
        if df.empty:
            return {"rankings": []}

        if company_filter:
            records_all = df.to_dict(orient="records")
            selected = None
            others = []
            for rec in records_all:
                rec_company = str(rec.get("company") or "").strip()
                if selected is None and _company_matches(rec_company, company_filter):
                    selected = rec
                else:
                    others.append(rec)

            # If strict filter slice does not contain the selected account,
            # attempt one broader lookup so the user-selected company is still shown.
            if selected is None:
                try:
                    df_company = ml_ranking_service.get_ranked_list(
                        equipment_type=None,
                        country=None,
                        top_k=None,
                        force_heuristic=force_heuristic,
                    )
                    if not df_company.empty:
                        for rec in df_company.to_dict(orient="records"):
                            if _company_matches(str(rec.get("company") or "").strip(), company_filter):
                                selected = rec
                                break
                except Exception:
                    # Keep normal flow even if fallback probe fails.
                    pass

            limited = others[: max(0, top_k - 1)] if top_k else others
            records = ([selected] if selected else []) + limited
        else:
            records = df.to_dict(orient="records")

        feature_explanations = {
            "equipment_age": "Older assets typically indicate stronger modernization demand and higher replacement potential.",
            "is_sms_oem": "Existing SMS footprint improves technical fit, installed-base continuity, and service upsell likelihood.",
            "crm_rating_num": "Higher CRM relationship quality usually correlates with easier access to decision-makers and faster deal conversion.",
            "crm_projects_count": "A deeper project history with the account signals proven execution trust and cross-sell potential.",
            "log_fte": "Larger organizations often have broader capex programs and better ability to fund major revamp projects.",
            "equipment_type_enc": "Certain equipment classes are structurally more likely to require upgrades based on lifecycle and process criticality.",
            "country_enc": "Country context captures structural market effects such as policy pressure, cost base, and investment cycles.",
            "knowledge_doc_count": "How many relevant SMS references we found for this account. More references usually means a warmer entry point.",
            "knowledge_best_match_score": "How strong the single best SMS reference is compared to this customer. Higher means a very similar proven case.",
            "knowledge_avg_match_score": "How relevant our full set of matched references is on average. Higher means the account fits our historical strengths.",
            "knowledge_service_signal": "Service-heavy internal evidence points to spare parts, maintenance, and long-term service potential.",
            "knowledge_inspection_signal": "Inspection and acceptance evidence indicates recent technical interaction and a route into follow-on upgrades.",
            "knowledge_modernization_signal": "Upgrade and revamp references point to capex appetite and modernization demand.",
            "knowledge_digital_signal": "Automation and digital references indicate optimization scope beyond mechanical replacement.",
            "knowledge_decarbonization_signal": "Decarbonization language signals likely relevance for EAF, electrification, and green-steel positioning.",
            "knowledge_project_signal": "Project-document density indicates active execution context or recent commercial traction.",
            "knowledge_quality_signal": "Quality or issue references can indicate recovery work, retrofit demand, or service-led re-entry opportunities.",
            "ext_news_article_count_180d": "More relevant recent news usually means the account is active enough to surface public strategic moves.",
            "ext_news_unique_source_count_180d": "Coverage across multiple sources suggests the market signal is broad rather than a single isolated mention.",
            "ext_news_days_since_last_mention": "More recent mentions can indicate an active investment or restructuring cycle.",
            "ext_news_capex_signal": "Capex and investment language in recent coverage indicates potential modernization or expansion appetite.",
            "ext_news_modernization_signal": "Upgrade and revamp language in public news points to near-term technical opportunity.",
            "ext_news_decarbonization_signal": "Public decarbonization narratives can align with electrification, efficiency, and green-steel sales plays.",
            "ext_news_restructuring_signal": "Restructuring can mean either caution or a trigger for targeted productivity investments.",
            "ext_news_shutdown_signal": "Shutdown or distress signals should typically suppress pursuit priority unless service recovery scope is explicit.",
            "ext_web_press_signal": "A visible corporate press footprint often correlates with organizational maturity and externally visible strategic activity.",
            "ext_web_sustainability_signal": "Sustainability language on the company overview is a proxy for ESG-driven investment relevance.",
            "ext_web_digital_signal": "Digital and automation language suggests openness to control, analytics, and optimization offers.",
            "ext_web_expansion_signal": "Expansion language points to capacity, brownfield, or adjacent-line opportunity.",
            "market_country_steel_news_count": "A more active steel-news environment can indicate investment, policy, or supply-chain change in the market.",
            "market_country_trade_pressure_score": "Trade and tariff pressure can accelerate competitiveness and modernization decisions.",
            "market_country_auto_demand_score": "Automotive demand is a useful downstream proxy for flat-product and quality-upgrade pull.",
            "market_country_macro_activity_score": "Stronger manufacturing and infrastructure language suggests a healthier capex backdrop.",
            "market_country_steel_intensity_score": "A more steel-intensive market backdrop increases relevance of equipment and service offerings."
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
            
        # Enrich records for frontend explanation and badges.
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
                    f"{int(rec.get('knowledge_doc_count', 0) or 0)} relevant SMS references found; "
                    f"strongest evidence theme: {top_theme}."
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


@router.post("/refresh-external-features")
def refresh_external_features(max_company_count: int = Query(default=75, ge=10, le=250)):
    """Refresh stable external feature snapshots used by ranking training/inference."""
    try:
        result = external_feature_service.refresh_snapshots(max_company_count=max_company_count)
        ml_ranking_service.clear_cache()
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/retrain-status")
def get_retrain_status():
    """Poll the background retrain job status."""
    with _retrain_lock:
        state = dict(_retrain_state)
    from app.utils.json_utils import json_safe_sanitize
    return json_safe_sanitize(state)


@router.get("/company-intelligence")
def get_company_intelligence(
    company_name: str = Query(...),
    equipment_type: Optional[str] = Query(default=None),
    country: Optional[str] = Query(default=None),
):
    """Return selected-company deep dive context for ranking analytics cards."""
    try:
        history = historical_service.get_yearly_performance(company_name)
        metrics = history.get("metrics", {}) if isinstance(history, dict) else {}

        won_list = history.get("won_list") if isinstance(history, dict) else None
        lost_list = history.get("lost_list") if isinstance(history, dict) else None
        yearly_df = history.get("yearly_df") if isinstance(history, dict) else None

        won_count = int(len(won_list)) if won_list is not None else 0
        lost_count = int(len(lost_list)) if lost_list is not None else 0
        won_value = float(metrics.get("total_won_value", 0) or 0)

        yearly_records = []
        if yearly_df is not None and not yearly_df.empty:
            yearly_records = yearly_df.to_dict(orient="records")

        country_news = _cached_country_intelligence(country or "global")
        steel_news = country_news.get("steel_news", [])[:2] if isinstance(country_news, dict) else []
        news_headlines = [item.get("title", "") for item in steel_news if item.get("title")]

        deep_dive_summary = (
            f"Account '{company_name}' shows {won_count} won and {lost_count} non-won historical projects in CRM. "
            f"Total recorded won value: EUR {won_value:,.0f}. "
            f"For {equipment_type or 'the selected equipment'}, prioritize proposals that connect capex decisions to uptime, yield, energy intensity, and lifecycle service capture."
        )

        if news_headlines:
            deep_dive_summary += " Recent market context: " + " | ".join(news_headlines)

        payload = {
            "company_name": company_name,
            "won_vs_lost": {
                "won_count": won_count,
                "lost_count": lost_count,
                "won_value_eur": won_value,
                "win_rate_pct": float(metrics.get("win_rate", 0) or 0),
                "total_projects": int(metrics.get("n_projects", won_count + lost_count) or 0),
            },
            "order_intake_history": yearly_records,
            "competitor_deep_dive": _build_competitor_deep_dive(equipment_type, country, company_name),
            "deep_dive_summary": deep_dive_summary,
        }

        from app.utils.json_utils import json_safe_sanitize
        return json_safe_sanitize(payload)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

