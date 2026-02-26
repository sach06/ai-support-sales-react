"""
app/services/historical_service.py
====================================
Loads data from Axel's raw Excel repositories and returns
historical performance, installed-base, and CRM project data
for a given customer company name.

Data sources
------------
- temp_repos/work_apps/templates/ib_list.xlsx         → installed base
- temp_repos/work_apps/templates/gh_current_projects.xlsx → CRM projects
"""
from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# ── Paths ─────────────────────────────────────────────────────────────────────
_ROOT = Path(__file__).resolve().parent.parent.parent
_IB_PATH  = _ROOT / "temp_repos" / "work_apps" / "templates" / "ib_list.xlsx"
_CRM_PATH = _ROOT / "temp_repos" / "work_apps" / "templates" / "gh_current_projects.xlsx"

# Source references shown in the UI
IB_SOURCE_LINK  = "Source: Axel's IB List (ib_list.xlsx)"
CRM_SOURCE_LINK = "Source: Axel's CRM Export (gh_current_projects.xlsx)"


# ── Raw loaders (cached for the app lifetime) ─────────────────────────────────

@lru_cache(maxsize=1)
def _load_ib() -> pd.DataFrame:
    if not _IB_PATH.exists():
        logger.warning("IB file not found: %s", _IB_PATH)
        return pd.DataFrame()
    try:
        df = pd.read_excel(_IB_PATH)
        # Drop unnamed / datetime columns
        df = df[[c for c in df.columns if isinstance(c, str) and not c.startswith("Unnamed") and not c.startswith("last")]]
        return df
    except Exception as e:
        logger.error("Failed to load IB file: %s", e)
        return pd.DataFrame()


@lru_cache(maxsize=1)
def _load_crm() -> pd.DataFrame:
    if not _CRM_PATH.exists():
        logger.warning("CRM file not found: %s", _CRM_PATH)
        return pd.DataFrame()
    try:
        df = pd.read_excel(_CRM_PATH)
        return df
    except Exception as e:
        logger.error("Failed to load CRM file: %s", e)
        return pd.DataFrame()


# ── Name normalisation ────────────────────────────────────────────────────────

def _norm(s: str) -> str:
    """Lowercase, strip punctuation/spaces for fuzzy match."""
    import re
    return re.sub(r"[^a-z0-9]", "", str(s).lower())


def _match_company(df: pd.DataFrame, col: str, company: str, threshold: int = 60) -> pd.DataFrame:
    """Return rows from df where df[col] fuzzy-matches company."""
    if df.empty or col not in df.columns:
        return df.iloc[0:0]
    norm_company = _norm(company)
    # First try substring match (fast)
    mask = df[col].astype(str).str.lower().str.contains(
        company[:8].lower(), na=False
    )
    result = df[mask]
    if len(result) > 0:
        return result
    # Fallback: normalised substring
    mask2 = df[col].apply(lambda x: norm_company[:6] in _norm(x))
    return df[mask2]


# ── Public API ────────────────────────────────────────────────────────────────

def get_ib_for_company(company: str) -> pd.DataFrame:
    """Return installed-base rows for the given company."""
    df = _load_ib()
    # Try 'ib_customer' column first
    for col in ["ib_customer", "account_name", "company", "customer"]:
        matched = _match_company(df, col, company)
        if not matched.empty:
            return matched.reset_index(drop=True)
    return pd.DataFrame()


def get_crm_projects_for_company(company: str) -> pd.DataFrame:
    """Return CRM project rows for the given company."""
    df = _load_crm()
    for col in ["account_name", "company", "customer_project", "ib_customer"]:
        matched = _match_company(df, col, company)
        if not matched.empty:
            return matched.reset_index(drop=True)
    return pd.DataFrame()


def get_yearly_performance(company: str) -> dict:
    """
    Build yearly project performance summary from CRM data.

    Returns
    -------
    dict with keys:
        yearly_df  : DataFrame(year, total_value_eur, n_projects, n_won, value_won)
        metrics    : dict(total_won_value, time_span, win_rate)
        won_list   : DataFrame of won projects
        lost_list  : DataFrame of lost / inactive projects
    """
    projects = get_crm_projects_for_company(company)
    if projects.empty:
        return {}

    df = projects.copy()

    # Parse year from date columns
    date_col = next((c for c in ["cp_close_date", "sp_oi_date", "CP_created_on", "date_of_inquiry"]
                     if c in df.columns), None)
    if date_col:
        df["_year"] = pd.to_datetime(df[date_col], errors="coerce").dt.year
    else:
        df["_year"] = pd.NaT

    # Value column
    val_col = next((c for c in ["cp_expected_value_eur", "sp_expected_value_eur", "CP_value_local_currency"]
                    if c in df.columns), None)
    if val_col:
        df["_value"] = pd.to_numeric(df[val_col], errors="coerce").fillna(0)
    else:
        df["_value"] = 0

    # Status / won detection
    status_col = next((c for c in ["cp_status_hot", "sp_custom_status", "cp_custom_status", "sales_phase"]
                       if c in df.columns), None)
    if status_col:
        df["_status"] = df[status_col].astype(str)
    else:
        df["_status"] = "Unknown"

    won_keywords = ["won", "booked", "converted", "order", "placed"]
    df["_is_won"] = df["_status"].str.lower().apply(
        lambda s: any(k in s for k in won_keywords)
    )

    # Yearly summary
    df_with_year = df.dropna(subset=["_year"])
    if df_with_year.empty:
        yearly_df = pd.DataFrame()
    else:
        g = df_with_year.groupby("_year")
        yearly_df = pd.DataFrame({
            "Year": g["_year"].first().astype(int),
            "Projects": g["_value"].count(),
            "Total Value (EUR)": g["_value"].sum().round(0),
            "Won Value (EUR)": g.apply(lambda x: x.loc[x["_is_won"], "_value"].sum()).round(0),
            "Win Rate %": g.apply(lambda x: (x["_is_won"].sum() / max(len(x), 1) * 100)).round(1),
        }).reset_index(drop=True).sort_values("Year")

    won_list  = df[df["_is_won"]].copy()
    lost_list = df[~df["_is_won"]].copy()

    total_won = float(df.loc[df["_is_won"], "_value"].sum())
    years_list = df_with_year["_year"].dropna().unique()
    time_span = int(max(years_list) - min(years_list)) if len(years_list) > 1 else 0
    win_rate  = float(df["_is_won"].mean() * 100) if len(df) > 0 else 0.0

    return {
        "yearly_df": yearly_df,
        "metrics": {
            "total_won_value": total_won,
            "time_span": time_span,
            "win_rate": round(win_rate, 1),
            "n_projects": len(df),
        },
        "won_list": won_list,
        "lost_list": lost_list,
        "raw_projects": df,
        "source": CRM_SOURCE_LINK,
    }


def get_ib_summary(company: str) -> dict:
    """
    Return installed-base summary for the company.

    Keys: df, n_units, n_sms_oem, avg_age, equipment_types, countries
    """
    df = get_ib_for_company(company)
    if df.empty:
        return {"df": df, "n_units": 0}

    CURRENT_YEAR = 2026

    # Startup year
    year_col = next((c for c in ["ib_startup", "start_year", "installation_year"] if c in df.columns), None)
    if year_col:
        df["_year"] = pd.to_numeric(df[year_col], errors="coerce")
        df["_age"] = df["_year"].apply(lambda y: max(0, CURRENT_YEAR - int(y)) if pd.notna(y) else np.nan)
    else:
        df["_age"] = np.nan

    # OEM/product columns
    prod_col  = next((c for c in ["ib_machine", "ib_product", "ib_description", "equipment"] if c in df.columns), None)
    ctry_col  = next((c for c in ["ib_customer_country", "ib_country", "country"] if c in df.columns), None)
    city_col  = next((c for c in ["ib_city", "city"] if c in df.columns), None)
    status_col = next((c for c in ["ib_status", "status"] if c in df.columns), None)

    n_units = len(df)
    avg_age = float(df["_age"].mean()) if "_age" in df.columns and df["_age"].notna().any() else 0.0
    eq_types = df[prod_col].dropna().unique().tolist() if prod_col else []
    countries = df[ctry_col].dropna().unique().tolist() if ctry_col else []

    return {
        "df": df,
        "n_units": n_units,
        "avg_age": round(avg_age, 1),
        "equipment_types": eq_types,
        "countries": countries,
        "prod_col": prod_col,
        "ctry_col": ctry_col,
        "city_col": city_col,
        "status_col": status_col,
        "year_col": year_col,
        "source": IB_SOURCE_LINK,
    }
