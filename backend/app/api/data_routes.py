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

router = APIRouter()

# ── Progress tracking ─────────────────────────────────────────────────────────
_load_progress = {
    "running": False,
    "step": "",
    "percent": 0,
    "total_steps": 6,
    "current_step": 0,
    "error": None,
    "done": False,
    "logs": [],
}
_progress_lock = threading.Lock()


def _update_progress(step: str, current: int, total: int, logs: list = None):
    with _progress_lock:
        _load_progress["step"] = step
        _load_progress["current_step"] = current
        _load_progress["total_steps"] = total
        _load_progress["percent"] = int((current / total) * 100) if total > 0 else 0
        if logs:
            _load_progress["logs"] = logs


def _run_load_data():
    """Background data loading with progress tracking."""
    with _progress_lock:
        _load_progress["running"] = True
        _load_progress["done"] = False
        _load_progress["error"] = None
        _load_progress["percent"] = 0
        _load_progress["step"] = "Initializing..."
        _load_progress["current_step"] = 0

    try:
        data_service.clear_logs()

        # Step 1: Initialize database
        _update_progress("Initializing database...", 1, 6)
        data_service.initialize_database()
        _update_progress("Initializing database...", 1, 6, data_service.get_logs())

        # Step 2: Discover files
        _update_progress("Discovering data files...", 2, 6, data_service.get_logs())
        available_files = data_service.list_available_files()
        if not available_files:
            with _progress_lock:
                _load_progress["error"] = "No data files found in data/ directory"
                _load_progress["running"] = False
                _load_progress["done"] = True
            return

        # Step 3: Load BCG data
        for file in available_files:
            if "bcg" in file.lower():
                _update_progress(f"Loading BCG installed base ({file})...", 3, 6, data_service.get_logs())
                data_service.load_bcg_installed_base(file)
                _update_progress(f"BCG data loaded", 3, 6, data_service.get_logs())

        # Step 4: Load CRM data
        for file in available_files:
            if "crm" in file.lower():
                _update_progress(f"Loading CRM data ({file})...", 4, 6, data_service.get_logs())
                data_service.load_crm_data(file)
                _update_progress(f"CRM data loaded", 4, 6, data_service.get_logs())

        # Step 5: Load other files
        for file in available_files:
            if "crm" not in file.lower() and "bcg" not in file.lower():
                if "install" in file.lower() or "base" in file.lower():
                    _update_progress(f"Loading {file}...", 5, 6, data_service.get_logs())
                    data_service.load_installed_base(file)

        # Step 6: Create unified view
        _update_progress("Creating unified company view & matching...", 5, 6, data_service.get_logs())
        data_service.create_unified_view()
        _update_progress("Unified view created", 6, 6, data_service.get_logs())

        # Clear ML ranking cache
        try:
            from app.services.ml_ranking_service import ml_ranking_service
            ml_ranking_service.clear_cache()
        except Exception:
            pass

        with _progress_lock:
            _load_progress["running"] = False
            _load_progress["done"] = True
            _load_progress["percent"] = 100
            _load_progress["step"] = "Complete!"
            _load_progress["logs"] = data_service.get_logs()

    except Exception as e:
        with _progress_lock:
            _load_progress["running"] = False
            _load_progress["done"] = True
            _load_progress["error"] = str(e)
            _load_progress["step"] = f"Error: {e}"
            _load_progress["logs"] = data_service.get_logs()


# ── /api/data/load ────────────────────────────────────────────────────────────

@router.post("/load")
def load_data(background_tasks: BackgroundTasks):
    """Initialize database and load all available data files in background."""
    with _progress_lock:
        if _load_progress["running"]:
            return {"success": False, "message": "Data loading already in progress"}

    background_tasks.add_task(_run_load_data)
    return {"success": True, "message": "Data loading started", "async": True}


# ── /api/data/progress ────────────────────────────────────────────────────────

@router.get("/progress")
def get_progress():
    """Return current data loading progress."""
    with _progress_lock:
        return dict(_load_progress)


# ── /api/data/status ──────────────────────────────────────────────────────────

@router.get("/status")
def get_status():
    """Return current data-load status and row counts."""
    try:
        conn = data_service.get_conn()
        if conn is None:
            return {"loaded": False, "row_counts": {}}

        tables_result = data_service.execute_df("SHOW TABLES")
        table_names = tables_result["name"].tolist() if "name" in tables_result.columns else []

        row_counts = {}
        for tbl in ["crm_data", "bcg_installed_base", "unified_companies"]:
            if tbl in table_names:
                result = data_service.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()
                row_counts[tbl] = result[0] if result else 0

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


# ── Shared sanitizer (handles nullable Int32/Float64 from DuckDB) ────────────
def _df_to_json_safe(df):
    """Convert a DataFrame to a JSON-safe list of dicts.
    DuckDB returns nullable int/float columns (Int32, Float64 with capital)
    that cannot be fillna(""). We instead do a json round-trip which converts
    every value to a native Python type via default=str.
    """
    import json
    records = df.to_dict(orient="records")
    return json.loads(json.dumps(records, default=str))


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
        clean = _df_to_json_safe(df)
        return {"customers": clean, "total": len(clean)}
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
        clean = _df_to_json_safe(df)
        return {"plants": clean, "total": len(clean)}
    except Exception as e:
        print(f"ERROR in /plants: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats")
def get_stats(
    region: Optional[str] = Query(default="All"),
    country: Optional[str] = Query(default="All"),
    equipment_type: Optional[str] = Query(default="All"),
):
    """Return summary statistics (distributions) for the Statistics panel."""
    return data_service.get_stats(
        region=region,
        country=country,
        equipment_type=equipment_type,
    )


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

