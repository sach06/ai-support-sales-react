"""
Customer API Routes — get full customer profile, AI Steckbrief, history, financials.
"""
from fastapi import APIRouter, HTTPException, BackgroundTasks, Path as URLPath, Body
from typing import Optional, Dict, Any
import sys
from pathlib import Path

# Ensure the backend root is on the path so services resolve correctly
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.services.data_service import data_service
from app.services.profile_generator import profile_generator
from app.services.financial_service import financial_service
import app.services.historical_service as historical_service
from app.services.web_enrichment_service import web_enrichment_service
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
        
        # Build comprehensive dict
        full_data = {
            "crm": _safe_json(crm_data),
            "financial_history": fin_history,
            "latest_balance_sheet": balances,
            "history": _safe_json(crm_hist)
        }
        
        extra_context = {
            "ib_summary": _safe_json(ib_sum),
            "crm_history": _safe_json(crm_hist)
        }
        
        if not installed_data.empty:
            full_data["installed_base"] = _safe_json(installed_data)
            
        # Call the LLM generator with extra context from Axel's repos
        profile = profile_generator.generate_profile(
            customer_data=full_data,
            extra_context=extra_context
        )
        
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
