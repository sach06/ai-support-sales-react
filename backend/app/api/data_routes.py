"""
Data API Routes — wraps DataIngestionService for React frontend consumption.
Endpoints:
  POST /api/data/load
  GET  /api/data/status
  GET  /api/data/progress
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
import threading
from pathlib import Path

# Ensure the backend root is on the path so services resolve correctly
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.services.data_service import data_service
from app.services.load_job_service import (
    get_latest_job_id,
    get_latest_progress,
    load_progress,
    start_load_job,
)
from app.utils.json_utils import df_to_json_safe, json_safe_sanitize

router = APIRouter()

# ── Progress tracking (job-id based, process-isolated) ───────────────────────
_progress_lock = threading.Lock()


# ── /api/data/load ────────────────────────────────────────────────────────────

@router.post("/load")
def load_data():
    """Start a data-load job in an isolated worker process."""
    with _progress_lock:
        latest = get_latest_progress()
        if latest and latest.get("running"):
            return {
                "success": False,
                "message": "Data loading already in progress",
                "job_id": latest.get("job_id"),
                "async": True,
            }

        # Release any API-process DB handle before worker attempts write access.
        try:
            data_service.close()
            data_service.conn = None
        except Exception:
            pass

        job_meta = start_load_job()
        return {
            "success": True,
            "message": "Data loading started",
            "async": True,
            "job_id": job_meta.get("job_id"),
            "pid": job_meta.get("pid"),
        }


# ── /api/data/progress ────────────────────────────────────────────────────────

@router.get("/progress")
def get_progress(job_id: Optional[str] = Query(default=None)):
    """Return progress for a specific job (or latest job if omitted)."""
    target_job_id = job_id or get_latest_job_id()
    if not target_job_id:
        return {
            "job_id": None,
            "running": False,
            "done": False,
            "percent": 0,
            "step": "No load job started",
            "error": None,
            "logs": [],
            "total_steps": 6,
            "current_step": 0,
        }

    progress = load_progress(target_job_id)
    if not progress:
        return {
            "job_id": target_job_id,
            "running": False,
            "done": False,
            "percent": 0,
            "step": "Job not found",
            "error": f"Unknown job_id: {target_job_id}",
            "logs": [],
            "total_steps": 6,
            "current_step": 0,
        }
    return progress


# ── /api/data/status ──────────────────────────────────────────────────────────

@router.get("/status")
def get_status(job_id: Optional[str] = Query(default=None)):
    """Return current data-load status and row counts."""
    try:
        latest = load_progress(job_id) if job_id else get_latest_progress()
        if latest and latest.get("running"):
            return {
                "loaded": False,
                "loading": True,
                "job_id": latest.get("job_id"),
                "row_counts": {},
                "tables": [],
            }

        conn = data_service.get_conn()
        if conn is None:
            return {"loaded": False, "loading": False, "job_id": get_latest_job_id(), "row_counts": {}}

        tables_result = data_service.execute_df("SHOW TABLES")
        table_names = tables_result["name"].tolist() if "name" in tables_result.columns else []

        row_counts = {}
        for tbl in ["crm_data", "bcg_installed_base", "unified_companies"]:
            if tbl in table_names:
                result = data_service.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()
                row_counts[tbl] = result[0] if result else 0

        loaded = "unified_companies" in table_names and row_counts.get("unified_companies", 0) > 0
        return {
            "loaded": loaded,
            "loading": False,
            "job_id": get_latest_job_id(),
            "row_counts": row_counts,
            "tables": table_names,
        }
    except Exception:
        return {"loaded": False, "loading": False, "job_id": get_latest_job_id(), "row_counts": {}}


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


# ── /api/data/company-names ───────────────────────────────────────────────────

@router.get("/company-names")
def get_company_names(
    region: Optional[str] = Query(default="All"),
    country: Optional[str] = Query(default="All"),
    equipment_type: Optional[str] = Query(default="All"),
):
    """List all available company names, optionally filtered by region/country/equipment."""
    import traceback
    try:
        hierarchy = data_service.get_company_hierarchy(
            region=region,
            country=country,
            equipment_type=equipment_type,
        )
        return hierarchy
    except Exception as e:
        print(f"ERROR in /company-names: {traceback.format_exc()}")
        return {"company_names": [], "company_groups": [], "standalone_companies": []}


# ── /api/data/regions ─────────────────────────────────────────────────────────

@router.get("/regions")
def get_regions():
    return {"regions": data_service.REGION_OPTIONS}


# ── /api/data/equipment-types ─────────────────────────────────────────────────

@router.get("/equipment-types")
def get_equipment_types():
    return {"equipment_types": data_service.FIXED_EQUIPMENT_LIST}


# Sanitization handled by app.utils.json_utils


# ── /api/data/customers ───────────────────────────────────────────────────────

@router.get("/customers")
def get_customers(
    region: Optional[str] = Query(default="All"),
    country: Optional[str] = Query(default="All"),
    equipment_type: Optional[str] = Query(default="All"),
    company_name: Optional[str] = Query(default="All"),
):
    """Return filtered customer list from unified_companies view."""
    import traceback
    try:
        df = data_service.get_customer_list(
            equipment_type=equipment_type,
            country=country,
            region=region,
            company_name=company_name,
        )
        if df.empty:
            return {"customers": [], "total": 0}
        clean = df_to_json_safe(df)
        return {"customers": clean, "total": len(clean)}
    except Exception as e:
        print(f"ERROR in /customers: {traceback.format_exc()}")
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
    import traceback
    try:
        df = data_service.get_detailed_plant_data(
            equipment_type=equipment_type,
            country=country,
            region=region,
            company_name=company_name
        )
        if df.empty:
            return {"plants": [], "total": 0}
        clean = df_to_json_safe(df)
        return {"plants": clean, "total": len(clean)}
    except Exception as e:
        print(f"ERROR in /plants: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats")
def get_stats(
    region: Optional[str] = Query(default="All"),
    country: Optional[str] = Query(default="All"),
    equipment_type: Optional[str] = Query(default="All"),
    company_name: Optional[str] = Query(default="All"),
):
    """Return summary statistics (distributions) for the Statistics panel."""
    import traceback
    try:
        result = data_service.get_stats(
            region=region,
            country=country,
            equipment_type=equipment_type,
            company_name=company_name
        )
        # Sanitize: numpy.int64 keys from value_counts().to_dict() break FastAPI JSON encoder
        return json_safe_sanitize(result)
    except Exception as e:
        print(f"ERROR in /stats: {traceback.format_exc()}")
        # Return empty stats instead of 500 error
        return {
            "records": [],
            "summary": {
                "total": 0,
                "status_counts": {},
                "equipment_counts": {},
                "capacity": {},
                "age": {},
                "start_year": {}
            }
        }


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


# ── /api/data/news ────────────────────────────────────────────────────────────

@router.get("/news")
def get_market_news(
    company: Optional[str] = Query(default=None),
    equipment_type: Optional[str] = Query(default=None),
    country: Optional[str] = Query(default=None),
    limit: int = Query(default=12),
):
    """Fetch steel market / company news from Google News RSS."""
    try:
        from app.services.web_enrichment_service import web_enrichment_service
        from email.utils import parsedate_to_datetime
        from datetime import datetime

        # Build contextual search queries
        queries = []
        if company and company.lower() not in ("all", "none", "unknown"):
            queries.append(f'{company} steel industry')
            queries.append(f'{company} steel plant production')
        if equipment_type and equipment_type.lower() not in ("all", "none"):
            queries.append(f'{equipment_type} steel manufacturing')
        if country and country.lower() not in ("all", "none"):
            queries.append(f'{country} steel industry market')
            queries.append(f'{country} steel production manufacturing')

        # Always add broad steel-industry fallback queries so there is always content
        if not queries:
            queries = [
                "global steel industry market trends",
                "steel production electric arc furnace",
                "steel scrap market prices",
                "hot rolling mill steel plant",
                "steel industry decarbonization green",
            ]
        elif len(queries) < 3:
            queries.append("steel industry latest news")

        all_news = []
        seen_urls: set = set()
        seen_titles: set = set()

        for q in queries:
            # Note: Google News RSS does NOT support `when:Nm` appended to queries;
            # results are already sorted newest-first by default.
            items = web_enrichment_service._get_google_news(q, limit=limit)
            for item in items:
                url = item.get("url", "")
                title = item.get("title", "").strip()
                title_key = title[:60].lower()  # dedup near-duplicate titles
                if url and url not in seen_urls and title_key not in seen_titles:
                    seen_urls.add(url)
                    seen_titles.add(title_key)
                    pub = item.get("published_date", "")
                    try:
                        item["_dt"] = parsedate_to_datetime(pub).replace(tzinfo=None)
                    except Exception:
                        item["_dt"] = datetime.min
                    all_news.append(item)

        all_news.sort(key=lambda x: x.get("_dt", datetime.min), reverse=True)
        for n in all_news:
            n.pop("_dt", None)
        return {"news": all_news[:limit]}
    except Exception as e:
        import traceback
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))


# ── /api/data/rematch-poor ────────────────────────────────────────────────────

@router.post("/rematch-poor")
def rematch_poor_matches(background_tasks: BackgroundTasks):
    """Re-run matching ONLY on poor/unmatched BCG entries using aggressive LLM resolution."""
    try:
        background_tasks.add_task(_do_rematch_poor)
        return {"success": True, "message": "Re-matching poor entries in background. Reload data when done."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def _do_rematch_poor():
    """Background task: find all BCG companies with no match or low score and retry with LLM + web search."""
    import json, logging
    from app.services.mapping_service import mapping_service, _build_llm_client
    logger = logging.getLogger("rematch_poor")

    conn = data_service.get_conn()
    if not conn:
        logger.error("No DB connection for rematch")
        return

    # Load CRM names
    try:
        crm_names = conn.execute("SELECT DISTINCT name FROM crm_data WHERE name IS NOT NULL").df()['name'].tolist()
    except Exception:
        crm_names = []

    # Find BCG companies not yet matched, or matched with score < 70
    try:
        poor_bcg = conn.execute("""
            SELECT DISTINCT b.company_internal
            FROM bcg_installed_base b
            LEFT JOIN company_mappings m ON b.company_internal = m.bcg_name
            WHERE m.bcg_name IS NULL OR m.match_score < 70
        """).df()['company_internal'].tolist()
    except Exception as e:
        logger.error(f"Error fetching poor BCG companies: {e}")
        return

    if not poor_bcg:
        logger.info("No poor matches found — all already matched well.")
        return

    logger.info(f"Re-matching {len(poor_bcg)} poor/unmatched BCG companies")

    client, model = _build_llm_client()
    if not client:
        logger.warning("No LLM client — falling back to fuzzy only")

    new_mappings = []
    for bcg_name in poor_bcg:
        if not bcg_name or str(bcg_name).lower() == 'nan':
            continue

        # First try: aggressive fuzzy with lower threshold
        result = mapping_service.find_best_match(bcg_name, crm_names, threshold=60)
        if result:
            matched, score = result
            new_mappings.append((matched, bcg_name, float(score)))
            logger.info(f"Fuzzy rematch: '{bcg_name}' → '{matched}' ({score:.0f})")
            continue

        # If fuzzy fails and LLM available, try web search + LLM
        if client:
            try:
                web_context = _web_search_company(bcg_name)
                prompt = f"""You are a steel industry expert. Match this BCG company name to the correct CRM company.

BCG company: "{bcg_name}"
Web context about this company: {web_context}

CRM candidates (first 30):
{json.dumps(crm_names[:30], indent=2)}

Rules:
- ONLY match if you are >70% confident they are the SAME legal entity
- Account for abbreviations, legal suffixes (GmbH/AG/S.A./Ltd), holding vs operating company
- If the BCG company is a subsidiary/plant of a CRM company, match it

Respond ONLY with JSON: {{"match_found": true/false, "matched_name": "<exact CRM string or null>", "confidence": <0-100>}}"""

                completion = client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": "You are a steel industry master data expert."},
                        {"role": "user", "content": prompt},
                    ],
                    response_format={"type": "json_object"},
                    temperature=0,
                )
                result = json.loads(completion.choices[0].message.content)
                if result.get("match_found") and result.get("matched_name") and result.get("confidence", 0) >= 65:
                    matched = result["matched_name"]
                    score = float(result.get("confidence", 75))
                    new_mappings.append((matched, bcg_name, score))
                    logger.info(f"LLM rematch: '{bcg_name}' → '{matched}' ({score:.0f})")
            except Exception as e:
                logger.error(f"LLM rematch error for '{bcg_name}': {e}")

    if new_mappings:
        try:
            conn.executemany(
                """INSERT INTO company_mappings (crm_name, bcg_name, match_score)
                   VALUES (?, ?, ?)
                   ON CONFLICT (bcg_name) DO UPDATE SET crm_name=excluded.crm_name, match_score=excluded.match_score""",
                new_mappings
            )
            logger.info(f"Saved {len(new_mappings)} new/updated mappings")
            # Invalidate fingerprint to force unified view rebuild
            try:
                conn.execute("DELETE FROM _meta WHERE key='data_fingerprint'")
            except Exception:
                pass
        except Exception as e:
            logger.error(f"Error saving rematch results: {e}")


def _web_search_company(company_name: str) -> str:
    """Try to get brief web context about an unknown company name via Google News."""
    try:
        from app.services.web_enrichment_service import web_enrichment_service
        items = web_enrichment_service._get_google_news(f'"{company_name}" steel plant', limit=3)
        snippets = [f"- {i.get('title','')} ({i.get('source','')})" for i in items]
        return "\n".join(snippets) if snippets else "No web context found."
    except Exception:
        return "Web search unavailable."

