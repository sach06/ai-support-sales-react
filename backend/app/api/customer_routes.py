"""
Customer API Routes — get full customer profile, AI Steckbrief, history, financials.
"""
from fastapi import APIRouter, HTTPException, BackgroundTasks, Path as URLPath, Body
from typing import Optional, Dict, Any
import sys
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

# Ensure the backend root is on the path so services resolve correctly
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.services.data_service import data_service
from app.services.profile_generator import profile_generator
from app.services.financial_service import financial_service
import app.services.historical_service as historical_service
from app.services.web_enrichment_service import web_enrichment_service
from app.services.internal_knowledge_service import internal_knowledge_service
from app.utils.json_utils import df_to_json_safe, json_safe_sanitize
import pandas as pd
import json
import math
import numpy as np

router = APIRouter()

def _safe_json(obj):
    return json_safe_sanitize(obj)


@router.get("/{customer_name}")
def get_customer_profile(
    customer_name: str = URLPath(...),
    country: str = "All",
    region: str = "All",
    equipment_type: str = "All"
):
    """Fetch all available raw data for a specific customer before AI generation."""
    try:
        df = data_service.get_customer_list(company_name=customer_name)
        if df.empty:
            raise HTTPException(status_code=404, detail="Customer not found in CRM/BCG data.")
            
        crm_data = df.iloc[0].to_dict()
        
        # We need the correct CRM name or BCG name to get the sub-data
        actual_name = crm_data.get('name') or customer_name
        
        installed_data = data_service.get_detailed_plant_data(
            company_name=actual_name,
            country=country,
            region=region,
            equipment_type=equipment_type
        )
        fin_history = financial_service.get_financial_history(actual_name)
        balances = financial_service.get_latest_balance_sheet(actual_name)
        history = historical_service.get_yearly_performance(actual_name)
        
        return {
            "customer_name": actual_name,
            "crm_data": _safe_json(crm_data),
            "installed_base": _safe_json(installed_data) if not installed_data.empty else [],
            "financial_history": fin_history,
            "balance_sheet": balances,
            "project_history": _safe_json(history)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{customer_name}/test")
def test_customer_profile(customer_name: str = URLPath(...)):
    history = historical_service.get_yearly_performance(customer_name)
    return {"history": _safe_json(history)}

@router.post("/{customer_name}/generate-profile")
def generate_steckbrief(customer_name: str = URLPath(...)):
    """Invoke the GPT-4o Agent to generate a comprehensive structured profile."""
    try:
        # Re-fetch data just like original app did
        df = data_service.get_customer_list(company_name=customer_name)
        if df.empty:
            raise HTTPException(status_code=404, detail="Customer not found")
        
        crm_data = df.iloc[0].to_dict()
        actual_name = crm_data.get('name') or customer_name
        
        installed_data = data_service.get_detailed_plant_data(company_name=actual_name)
        fin_history = financial_service.get_financial_history(actual_name)
        balances = financial_service.get_latest_balance_sheet(actual_name)
        # Build comprehensive context for AI via historical_service
        ib_sum = historical_service.get_ib_summary(actual_name)
        crm_hist = historical_service.get_yearly_performance(actual_name)

        # Determine country for intelligence gathering
        country_value = crm_data.get('country')
        if (not country_value or str(country_value).lower() in ('nan', 'none', '')) and not installed_data.empty:
            first_country_cols = [c for c in ['country_internal', 'country', 'Country'] if c in installed_data.columns]
            if first_country_cols:
                country_value = installed_data.iloc[0].get(first_country_cols[0])

        equipment_types = []
        if not installed_data.empty and 'equipment_type' in installed_data.columns:
            equipment_types = [str(v) for v in installed_data['equipment_type'].dropna().astype(str).unique().tolist()[:8]]
        
        # ── PARALLELIZED WEB ENRICHMENT ────────────────────────────────────
        # Run web API calls concurrently instead of sequentially
        company_overview = None
        company_news = None
        country_intelligence = {}
        knowledge_analysis = None
        
        executor = ThreadPoolExecutor(max_workers=4)
        try:
            # Submit all concurrent tasks
            future_overview = executor.submit(web_enrichment_service.get_company_overview, actual_name)
            future_news = executor.submit(web_enrichment_service.get_recent_news, actual_name, 6)
            future_country_intel = executor.submit(
                web_enrichment_service.get_country_intelligence,
                str(country_value) if country_value else None
            ) if country_value else None
            future_knowledge = executor.submit(
                internal_knowledge_service.analyze_customer,
                actual_name,
                equipment_types,
                str(country_value) if country_value else None,
                4,
            )

            # Collect results with bounded waits
            try:
                company_overview = future_overview.result(timeout=20)
            except Exception as e:
                print(f"Warning: Failed to fetch company overview: {e}")
                company_overview = None

            try:
                company_news = future_news.result(timeout=20)
            except Exception as e:
                print(f"Warning: Failed to fetch company news: {e}")
                company_news = None

            if future_country_intel:
                try:
                    country_intelligence = future_country_intel.result(timeout=20) or {}
                except Exception as e:
                    print(f"Warning: Failed to fetch country intelligence: {e}")
                    country_intelligence = {}

            try:
                knowledge_analysis = future_knowledge.result(timeout=12)
            except Exception as e:
                print(f"Warning: Failed to analyze customer knowledge: {e}")
                knowledge_analysis = {
                    "context": "",
                    "references": [],
                    "evidence": [],
                    "signals": internal_knowledge_service._empty_signals()
                }
        finally:
            # Do not block request completion on stalled worker threads
            executor.shutdown(wait=False, cancel_futures=True)
        
        internal_knowledge = knowledge_analysis.get("context", "")
        
        # Build comprehensive dict
        full_data = {
            "crm": _safe_json(crm_data),
            "financial_history": fin_history,
            "latest_balance_sheet": balances,
            "history": _safe_json(crm_hist)
        }
        
        manager_briefing = internal_knowledge_service.get_manager_briefing_context(max_chars=6000)

        extra_context = {
            "ib_summary": _safe_json(ib_sum),
            "crm_history": _safe_json(crm_hist),
            "company_overview": _safe_json(company_overview),
            "company_news": _safe_json(company_news),
            "country_intelligence": _safe_json(country_intelligence),
            "internal_knowledge": internal_knowledge,
            "internal_knowledge_signals": knowledge_analysis.get("signals", {}),
            "manager_briefing": manager_briefing.get("content", ""),
        }

        web_context_parts = []
        if company_overview:
            web_context_parts.append(
                f"Company overview source: {company_overview.get('source_url', 'Unknown')}\n"
                f"Description: {company_overview.get('description', 'N/A')}\n"
                f"Headquarters: {company_overview.get('headquarters', 'N/A')}\n"
                f"Founded: {company_overview.get('founded', 'N/A')}\n"
                f"Industry: {company_overview.get('industry', 'N/A')}\n"
                f"Employees: {company_overview.get('employee_count', 'N/A')}"
            )
        if company_news:
            web_context_parts.append(
                "Recent public news:\n" + "\n".join(
                    f"- {item.get('title', 'Untitled')} | {item.get('source', 'Unknown')} | {item.get('published_date', 'Unknown')} | {item.get('url', '')}"
                    for item in company_news[:6]
                )
            )
        web_data = "\n\n".join(web_context_parts) if web_context_parts else None
        
        if not installed_data.empty:
            full_data["installed_base"] = _safe_json(installed_data)
            
        # Call the LLM generator with extra context from Axel's repos
        profile = profile_generator.generate_profile(
            customer_data=full_data,
            web_data=web_data,
            extra_context=extra_context
        )

        internal_refs = knowledge_analysis.get("references", [])
        if internal_refs:
            profile.setdefault('references', [])
            if isinstance(profile.get('references'), list):
                profile['references'].extend([r for r in internal_refs if r not in profile['references']])

        if manager_briefing.get("source"):
            profile.setdefault('references', [])
            if isinstance(profile.get('references'), list):
                briefing_ref = f"Manager Briefing (Internal PDF): {manager_briefing['source']}"
                if briefing_ref not in profile['references']:
                    profile['references'].append(briefing_ref)

        if knowledge_analysis.get("evidence"):
            profile["internal_knowledge_evidence"] = knowledge_analysis["evidence"]
        if knowledge_analysis.get("signals"):
            profile["internal_knowledge_signals"] = knowledge_analysis["signals"]
        profile["internal_knowledge_status"] = internal_knowledge_service.get_status()

        # Order-intake history for profile tab/export tables and charts.
        yearly_df = crm_hist.get('yearly_df') if isinstance(crm_hist, dict) else None
        if yearly_df is not None and not yearly_df.empty:
            profile['order_intake_history'] = [
                {
                    'year': int(row.get('Year', 0) or 0),
                    'amount_eur': float(row.get('Total Value (EUR)', 0) or 0),
                    'won_value_eur': float(row.get('Won Value (EUR)', 0) or 0),
                    'win_rate_pct': float(row.get('Win Rate %', 0) or 0),
                }
                for _, row in yearly_df.iterrows()
            ]

        # Ensure extended profile fields exist so UI always renders requested sections.
        profile.setdefault('basic_data', {})
        profile.setdefault('history', {})
        profile.setdefault('sales_strategy', {})

        profile['basic_data'].setdefault('ownership_type', profile['basic_data'].get('owner', 'Not available'))
        profile['basic_data'].setdefault('management_deep_dive', profile['basic_data'].get('management', 'Not available'))
        profile['basic_data'].setdefault('decision_governance', 'Working hypothesis: strategic capex decisions are driven by board/executive approval with operations and finance sign-off.')

        profile['history'].setdefault('active_opportunity_deep_dive', profile.get('priority_analysis', {}).get('engagement_recommendation', 'Active opportunity scope not available from current CRM extract.'))
        profile['sales_strategy'].setdefault('sms_strengths_to_leverage', 'Metallurgical process depth, integrated OEM modernization scope, and lifecycle service execution capability.')
        profile['sales_strategy'].setdefault('sms_relationship_assessment', profile['history'].get('sms_relationship', 'Relationship assessment not available.'))
        
        return {"profile": profile}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{customer_name}/news")
def get_customer_news(customer_name: str = URLPath(...)):
    """Fetch latest market news."""
    try:
        news = web_enrichment_service.get_dashboard_news(company=customer_name, country="All", region="All", limit=10)
        return {"news": news}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
