"""
Data API Routes — wraps DataIngestionService for React frontend consumption.
Endpoints:
  POST /api/data/load
  GET  /api/data/status
  GET  /api/data/files
  GET  /api/data/countries
  GET  /api/data/customers
  GET  /api/data/plants
  GET  /api/data/logs
  POST /api/data/enrich-geo
"""
from fastapi import APIRouter, Query, BackgroundTasks, HTTPException
from typing import Optional
import sys
from pathlib import Path

# Ensure the backend root is on the path so services resolve correctly
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.services.data_service import data_service

router = APIRouter()

# ── /api/data/load ────────────────────────────────────────────────────────────

@router.post("/load")
def load_data():
    """Initialize database and load all available data files."""
    try:
        data_service.clear_logs()
        data_service.initialize_database()

        available_files = data_service.list_available_files()
        if not available_files:
            return {"success": False, "message": "No data files found in data/ directory", "logs": data_service.get_logs()}

        for file in available_files:
            if "crm" in file.lower():
                data_service.load_crm_data(file)
            elif "bcg" in file.lower():
                data_service.load_bcg_installed_base(file)
            elif "install" in file.lower() or "base" in file.lower():
                data_service.load_installed_base(file)

        data_service.create_unified_view()

        # Clear ML ranking cache
        try:
            from app.services.ml_ranking_service import ml_ranking_service
            ml_ranking_service.clear_cache()
        except Exception:
            pass

        return {
            "success": True,
            "message": "Data loaded successfully",
            "files_loaded": available_files,
            "logs": data_service.get_logs(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── /api/data/status ──────────────────────────────────────────────────────────

@router.get("/status")
def get_status():
    """Return current data-load status and row counts."""
    try:
        conn = data_service.get_conn()
        if conn is None:
            return {"loaded": False, "row_counts": {}}

        tables_result = conn.execute("SHOW TABLES").df()
        table_names = tables_result["name"].tolist() if "name" in tables_result.columns else []

        row_counts = {}
        for tbl in ["crm_data", "bcg_installed_base", "unified_companies"]:
            if tbl in table_names:
                row_counts[tbl] = conn.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()[0]

        loaded = "unified_companies" in table_names and row_counts.get("unified_companies", 0) > 0
        return {"loaded": loaded, "row_counts": row_counts, "tables": table_names}
    except Exception:
        return {"loaded": False, "row_counts": {}}


# ── /api/data/files ───────────────────────────────────────────────────────────

@router.get("/files")
def list_files():
    """List all available Excel/CSV files in the data directory."""
    return {"files": data_service.list_available_files()}


# ── /api/data/countries ───────────────────────────────────────────────────────

@router.get("/countries")
def get_countries():
    """List all available countries from BCG data."""
    return {"countries": data_service.get_all_countries()}


# ── /api/data/regions ─────────────────────────────────────────────────────────

@router.get("/regions")
def get_regions():
    return {"regions": data_service.REGION_OPTIONS}


# ── /api/data/equipment-types ─────────────────────────────────────────────────

@router.get("/equipment-types")
def get_equipment_types():
    return {"equipment_types": data_service.FIXED_EQUIPMENT_LIST}


# ── /api/data/customers ───────────────────────────────────────────────────────

@router.get("/customers")
def get_customers(
    region: Optional[str] = Query(default="All"),
    country: Optional[str] = Query(default="All"),
    equipment_type: Optional[str] = Query(default="All"),
    company_name: Optional[str] = Query(default="All"),
):
    """Return filtered customer list from unified_companies view."""
    try:
        df = data_service.get_customer_list(
            equipment_type=equipment_type,
            country=country,
            region=region,
            company_name=company_name,
        )
        if df.empty:
            return {"customers": [], "total": 0}

        # Sanitize for NaN/Infinity
        df = df.fillna("")
        records = df.to_dict(orient="records")
        return {"customers": records, "total": len(records)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── /api/data/plants ──────────────────────────────────────────────────────────

@router.get("/plants")
def get_plants(
    region: Optional[str] = Query(default="All"),
    country: Optional[str] = Query(default="All"),
    equipment_type: Optional[str] = Query(default="All"),
    company_name: Optional[str] = Query(default="All"),
):
    """Return detailed plant data for the map and inventory table."""
    try:
        df = data_service.get_detailed_plant_data(
            equipment_type=equipment_type,
            country=country,
            region=region,
            company_name=company_name
        )
        if df.empty:
            return {"plants": [], "total": 0}

        df = df.fillna("")
        records = df.to_dict(orient="records")
        return {"plants": records, "total": len(records)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── /api/data/logs ────────────────────────────────────────────────────────────

@router.get("/logs")
def get_logs():
    return {"logs": data_service.get_logs()}


# ── /api/data/enrich-geo ──────────────────────────────────────────────────────

@router.post("/enrich-geo")
def enrich_geo(background_tasks: BackgroundTasks):
    try:
        background_tasks.add_task(data_service.enrich_geo_coordinates)
        return {"success": True, "message": "Background enrichment started."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
