"""Stable external feature snapshots for ranking model training and inference."""
from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from app.services.data_service import data_service
from app.services.web_enrichment_service import web_enrichment_service

logger = logging.getLogger(__name__)

COMPANY_EXTERNAL_FEATURE_COLS = [
    "ext_news_article_count_180d",
    "ext_news_unique_source_count_180d",
    "ext_news_days_since_last_mention",
    "ext_news_capex_signal",
    "ext_news_modernization_signal",
    "ext_news_decarbonization_signal",
    "ext_news_restructuring_signal",
    "ext_news_shutdown_signal",
    "ext_web_press_signal",
    "ext_web_sustainability_signal",
    "ext_web_digital_signal",
    "ext_web_expansion_signal",
    "ext_external_feature_freshness_days",
]

COUNTRY_MARKET_FEATURE_COLS = [
    "market_country_steel_news_count",
    "market_country_economic_news_count",
    "market_country_trade_news_count",
    "market_country_auto_news_count",
    "market_country_macro_news_count",
    "market_country_trade_pressure_score",
    "market_country_auto_demand_score",
    "market_country_macro_activity_score",
    "market_country_steel_intensity_score",
    "market_country_feature_freshness_days",
]

_NEWS_SIGNAL_KEYWORDS = {
    "capex": ["capex", "investment", "invest", "expansion", "new line", "new plant", "greenfield", "brownfield"],
    "modernization": ["modernization", "upgrade", "revamp", "retrofit", "efficiency", "automation"],
    "decarbonization": ["decarbonization", "co2", "carbon", "hydrogen", "green steel", "electrification", "cbam"],
    "restructuring": ["restructuring", "reorganization", "layoff", "cost cutting", "divest", "turnaround"],
    "shutdown": ["shutdown", "closure", "idle", "insolvency", "bankruptcy", "halt production"],
}


def _normalise_company_name(name: Any) -> str:
    raw = str(name or "").strip().lower()
    if not raw:
        return ""
    raw = re.sub(r"\b(gmbh|co|kg|inc|ltd|llc|corp|ag|sa|spa|nv|bv|as|ab|oy|plc)\b\.?", "", raw)
    raw = re.sub(r"[^a-z0-9 ]", " ", raw)
    return re.sub(r"\s+", " ", raw).strip()


def _normalise_country(country: Any) -> str:
    return re.sub(r"\s+", " ", str(country or "").strip().lower())


def _parse_rss_datetime(value: str) -> Optional[datetime]:
    if not value:
        return None
    try:
        parsed = parsedate_to_datetime(value)
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except Exception:
        return None


def _keyword_signal(texts: List[str], keywords: List[str]) -> float:
    if not texts:
        return 0.0
    hits = 0
    for text in texts:
        lowered = text.lower()
        if any(keyword in lowered for keyword in keywords):
            hits += 1
    return float(hits / max(len(texts), 1))


class ExternalFeatureService:
    """Build and persist stable external feature snapshots in DuckDB."""

    def _table_exists(self, table_name: str) -> bool:
        try:
            tables = data_service.execute_df("SHOW TABLES")
            names = set(tables.iloc[:, 0].astype(str).tolist()) if not tables.empty else set()
            return table_name in names
        except Exception:
            return False

    def _load_company_candidates(self, max_company_count: int = 75) -> pd.DataFrame:
        crm_table = None
        tables = data_service.execute_df("SHOW TABLES")
        names = set(tables.iloc[:, 0].astype(str).tolist()) if not tables.empty else set()
        for candidate in ["crm_data", "crm", "customers", "unified_companies"]:
            if candidate in names:
                crm_table = candidate
                break

        if crm_table is None:
            return pd.DataFrame(columns=["company_name", "country"])

        crm_df = data_service.execute_df(f"SELECT * FROM {crm_table}")
        if crm_df.empty:
            return pd.DataFrame(columns=["company_name", "country"])

        company_col = next((c for c in ["name", "customer_name", "company_name", "crm_name", "bcg_name"] if c in crm_df.columns), None)
        country_col = next((c for c in ["country", "Country", "country_internal"] if c in crm_df.columns), None)
        project_col = next((c for c in ["project_count", "projects_count", "num_projects"] if c in crm_df.columns), None)

        if not company_col:
            return pd.DataFrame(columns=["company_name", "country"])

        candidates = crm_df[[company_col] + ([country_col] if country_col else []) + ([project_col] if project_col else [])].copy()
        candidates = candidates.rename(columns={company_col: "company_name"})
        if country_col:
            candidates = candidates.rename(columns={country_col: "country"})
        else:
            candidates["country"] = ""
        if project_col:
            candidates["priority_projects"] = pd.to_numeric(candidates[project_col], errors="coerce").fillna(0)
        else:
            candidates["priority_projects"] = 0

        candidates["company_name"] = candidates["company_name"].fillna("").astype(str).str.strip()
        candidates["country"] = candidates["country"].fillna("").astype(str).str.strip()
        candidates = candidates[candidates["company_name"] != ""]
        candidates["company_name_normalized"] = candidates["company_name"].map(_normalise_company_name)
        candidates = candidates[candidates["company_name_normalized"] != ""]
        candidates = candidates.sort_values(["priority_projects", "company_name"], ascending=[False, True])
        candidates = candidates.drop_duplicates(subset=["company_name_normalized"], keep="first")
        return candidates[["company_name", "company_name_normalized", "country"]].head(max_company_count)

    def _load_country_candidates(self) -> List[str]:
        candidates: List[str] = []
        for table_name in ["crm_data", "crm", "customers", "unified_companies", "bcg_installed_base", "bcg_data"]:
            if not self._table_exists(table_name):
                continue
            df = data_service.execute_df(f"SELECT * FROM {table_name}")
            if df.empty:
                continue
            country_col = next((c for c in ["country", "Country", "country_internal", "ib_customer_country"] if c in df.columns), None)
            if not country_col:
                continue
            values = (
                df[country_col]
                .fillna("")
                .astype(str)
                .str.strip()
                .tolist()
            )
            candidates.extend([value for value in values if value and value.lower() not in {"all", "unknown", "none"}])
        return sorted(set(candidates))

    def _build_company_feature_row(self, company_name: str, country: str = "") -> Dict[str, Any]:
        snapshot_at = datetime.now(timezone.utc)
        news_items = web_enrichment_service.get_recent_news(company_name, limit=12) or []
        overview = web_enrichment_service.get_company_overview(company_name) or {}

        cutoff_days = 180
        recent_items = []
        all_texts: List[str] = []
        unique_sources = set()
        days_since_last = float(cutoff_days)

        for item in news_items:
            published_at = _parse_rss_datetime(str(item.get("published_date", "") or ""))
            if published_at is not None:
                age_days = (snapshot_at - published_at).days
                days_since_last = min(days_since_last, max(age_days, 0))
                if age_days > cutoff_days:
                    continue
            title = str(item.get("title", "") or "")
            description = str(item.get("description", "") or "")
            source = str(item.get("source", "") or "")
            combined = " ".join(part for part in [title, description] if part).strip()
            if not combined:
                continue
            recent_items.append(item)
            all_texts.append(combined)
            if source:
                unique_sources.add(source.strip().lower())

        overview_text = " ".join(
            str(overview.get(key, "") or "")
            for key in ["description", "industry", "headquarters", "employee_count"]
        ).strip()
        if overview_text:
            all_texts.append(overview_text)

        return {
            "company_name": company_name,
            "company_name_normalized": _normalise_company_name(company_name),
            "country": country,
            "snapshot_at": snapshot_at.isoformat(),
            "ext_news_article_count_180d": float(len(recent_items)),
            "ext_news_unique_source_count_180d": float(len(unique_sources)),
            "ext_news_days_since_last_mention": float(days_since_last if recent_items else cutoff_days),
            "ext_news_capex_signal": _keyword_signal(all_texts, _NEWS_SIGNAL_KEYWORDS["capex"]),
            "ext_news_modernization_signal": _keyword_signal(all_texts, _NEWS_SIGNAL_KEYWORDS["modernization"]),
            "ext_news_decarbonization_signal": _keyword_signal(all_texts, _NEWS_SIGNAL_KEYWORDS["decarbonization"]),
            "ext_news_restructuring_signal": _keyword_signal(all_texts, _NEWS_SIGNAL_KEYWORDS["restructuring"]),
            "ext_news_shutdown_signal": _keyword_signal(all_texts, _NEWS_SIGNAL_KEYWORDS["shutdown"]),
            "ext_web_press_signal": 1.0 if overview.get("source_url") else 0.0,
            "ext_web_sustainability_signal": _keyword_signal([overview_text] if overview_text else [], _NEWS_SIGNAL_KEYWORDS["decarbonization"]),
            "ext_web_digital_signal": _keyword_signal([overview_text] if overview_text else [], ["digital", "automation", "software", "analytics", "ai"]),
            "ext_web_expansion_signal": _keyword_signal(all_texts, ["expansion", "growth", "capacity", "new mill", "new plant"]),
            "ext_external_feature_freshness_days": float(0),
        }

    def _news_bucket_count(self, items: List[Dict[str, Any]]) -> float:
        return float(len([item for item in items if str(item.get("title", "") or "").strip()]))

    def _build_country_feature_row(self, country: str) -> Dict[str, Any]:
        snapshot_at = datetime.now(timezone.utc)
        intel = web_enrichment_service.get_country_intelligence(country) or {}
        steel_news = intel.get("steel_news", []) if isinstance(intel, dict) else []
        economic_news = intel.get("economic_developments", []) if isinstance(intel, dict) else []
        trade_news = intel.get("tariffs_trade", []) if isinstance(intel, dict) else []
        auto_news = intel.get("automotive_trends", []) if isinstance(intel, dict) else []
        macro_news = intel.get("other_macro", []) if isinstance(intel, dict) else []

        def _texts(items: List[Dict[str, Any]]) -> List[str]:
            values: List[str] = []
            for item in items:
                title = str(item.get("title", "") or "")
                description = str(item.get("description", "") or "")
                combined = " ".join(part for part in [title, description] if part).strip()
                if combined:
                    values.append(combined)
            return values

        return {
            "country": country,
            "country_normalized": _normalise_country(country),
            "snapshot_at": snapshot_at.isoformat(),
            "market_country_steel_news_count": self._news_bucket_count(steel_news),
            "market_country_economic_news_count": self._news_bucket_count(economic_news),
            "market_country_trade_news_count": self._news_bucket_count(trade_news),
            "market_country_auto_news_count": self._news_bucket_count(auto_news),
            "market_country_macro_news_count": self._news_bucket_count(macro_news),
            "market_country_trade_pressure_score": _keyword_signal(_texts(trade_news), ["tariff", "trade", "dumping", "duty", "cbam"]),
            "market_country_auto_demand_score": _keyword_signal(_texts(auto_news), ["automotive", "vehicle", "ev", "car demand", "mobility"]),
            "market_country_macro_activity_score": _keyword_signal(_texts(economic_news) + _texts(macro_news), ["growth", "investment", "industrial", "manufacturing", "infrastructure"]),
            "market_country_steel_intensity_score": _keyword_signal(_texts(steel_news), ["steel", "mill", "blast furnace", "eaf", "rolling mill"]),
            "market_country_feature_freshness_days": float(0),
        }

    def _persist_table(self, table_name: str, df: pd.DataFrame) -> None:
        conn = data_service.get_conn()
        with data_service._lock:
            conn.register("snapshot_df", df)
            try:
                conn.execute(f"CREATE OR REPLACE TABLE {table_name} AS SELECT * FROM snapshot_df")
            finally:
                try:
                    conn.unregister("snapshot_df")
                except Exception:
                    pass

    def refresh_snapshots(self, max_company_count: int = 75) -> Dict[str, Any]:
        company_candidates = self._load_company_candidates(max_company_count=max_company_count)
        country_candidates = self._load_country_candidates()

        company_rows = [
            self._build_company_feature_row(row.company_name, row.country)
            for row in company_candidates.itertuples(index=False)
        ]
        country_rows = [self._build_country_feature_row(country) for country in country_candidates]

        company_df = pd.DataFrame(company_rows)
        country_df = pd.DataFrame(country_rows)

        if company_df.empty:
            company_df = pd.DataFrame(columns=["company_name", "company_name_normalized", "country", "snapshot_at", *COMPANY_EXTERNAL_FEATURE_COLS])
        if country_df.empty:
            country_df = pd.DataFrame(columns=["country", "country_normalized", "snapshot_at", *COUNTRY_MARKET_FEATURE_COLS])

        self._persist_table("company_external_features", company_df)
        self._persist_table("country_market_features", country_df)

        return {
            "status": "ok",
            "company_feature_rows": int(len(company_df)),
            "country_feature_rows": int(len(country_df)),
            "company_feature_columns": COMPANY_EXTERNAL_FEATURE_COLS,
            "country_feature_columns": COUNTRY_MARKET_FEATURE_COLS,
        }


external_feature_service = ExternalFeatureService()