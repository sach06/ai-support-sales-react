"""
app/services/ml_ranking_service.py
====================================
Streamlit-friendly wrapper around the XGBoost priority-ranking model.

Responsibilities
----------------
* Load the persisted model once at startup (with graceful heuristic fallback)
* Expose `get_ranked_list(equipment_type, top_k)` for the UI
* Expose `score_customer(bcg_rows, crm_row)` for the customer-detail page
* Provide `is_model_available()` so the UI can show a "train model" prompt
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class MLRankingService:
    """
    High-level service that bridges the Streamlit app and the XGBoost model.

    The model is loaded lazily on first use.  If the model file does not exist
    the service falls back to the heuristic scoring already implemented in
    PredictionService, so the app never breaks.
    """

    def __init__(self, db_path: str | Path, model_path: Optional[str | Path] = None):
        from app.core.config import settings
        self._db_path    = Path(db_path)
        self._model_path = Path(model_path) if model_path else Path(settings.XGB_MODEL_PATH)
        self._model      = None    # lazy
        self._feat_df    = None    # cached feature matrix
        self._labels     = None    # cached labels (if available)

    # ── Public API ────────────────────────────────────────────────────────────

    def is_model_available(self) -> bool:
        return self._model_path.exists()

    def clear_cache(self) -> None:
        """Invalidate the cached feature matrix (call after data is reloaded)."""
        self._feat_df = None
        self._labels  = None

    def load_model(self) -> bool:
        """Load model from disk. Returns True on success."""
        if not self.is_model_available():
            logger.info("No trained model found at %s", self._model_path)
            return False
        try:
            from src.models.xgb_ranking_model import XGBPriorityModel
            self._model = XGBPriorityModel()
            self._model.load(self._model_path)
            logger.info("XGBoost model loaded from %s", self._model_path)
            return True
        except Exception as e:
            logger.warning("Could not load XGBoost model: %s", e)
            self._model = None
            return False

    def get_ranked_list(
        self,
        equipment_type: Optional[str] = None,
        country: Optional[str] = None,
        top_k: Optional[int] = 50,
        force_heuristic: bool = False,
    ) -> pd.DataFrame:
        """
        Return a ranked DataFrame of equipment units.

        Columns: rank, company, equipment_type, country, equipment_age, priority_score

        Falls back to the heuristic model if XGBoost model is unavailable.
        """
        if self._model is None and not force_heuristic:
            self.load_model()

        if self._model is not None:
            feat_df = self._get_features()
            if feat_df is not None and not feat_df.empty:
                try:
                    result = self._model.rank_by_equipment_type(
                        feat_df, equipment_type=equipment_type, top_k=top_k if not country else None
                    )
                    if country and "country" in result.columns:
                        result = result[result["country"].str.contains(country, case=False, na=False)]
                    if top_k:
                        result = result.head(top_k)
                    return result
                except Exception as e:
                    logger.warning("XGBoost ranking failed, falling back: %s", e)

        # ── Heuristic fallback ────────────────────────────────────────────────
        return self._heuristic_ranked_list(equipment_type, country, top_k)

    def score_customer(
        self,
        company_name: str,
        equipment_type: Optional[str] = None,
    ) -> Tuple[float, str]:
        """
        Return (priority_score [0-100], source) for a single company.
        source is "xgboost" or "heuristic".
        """
        ranked = self.get_ranked_list(equipment_type=equipment_type)
        if ranked.empty:
            return 50.0, "heuristic"

        mask = ranked["company"].str.lower().str.contains(
            company_name.lower()[:8], na=False
        )
        if mask.any():
            row = ranked[mask].iloc[0]
            source = "xgboost" if self._model is not None else "heuristic"
            return float(row["priority_score"]), source

        return 50.0, "heuristic"

    def get_equipment_types(self) -> List[str]:
        """Return sorted list of unique EquipmentType values from BCG data."""
        feat_df = self._get_features()
        if feat_df is not None and "_equipment_type" in feat_df.columns:
            vals = feat_df["_equipment_type"].dropna().unique().tolist()
            return sorted(v for v in vals if v and v != "Unknown")
        return []

    def get_countries(self) -> List[str]:
        """Return sorted list of unique country values from BCG data."""
        feat_df = self._get_features()
        if feat_df is not None and "_country" in feat_df.columns:
            vals = feat_df["_country"].dropna().unique().tolist()
            return sorted(v for v in vals if v and v != "Unknown")
        return []

    def get_company_names(self) -> List[str]:
        """Return sorted list of unique company names from BCG data."""
        feat_df = self._get_features()
        if feat_df is not None and "_company" in feat_df.columns:
            vals = feat_df["_company"].dropna().unique().tolist()
            return sorted(v for v in vals if v and v != "Unknown")
        return []

    def get_model_metadata(self) -> Dict:
        """Return the metadata JSON stored alongside the model file."""
        meta_path = self._model_path.with_suffix(".meta.json")
        if meta_path.exists():
            import json
            try:
                return json.loads(meta_path.read_text())
            except Exception:
                pass
        return {}

    def get_feature_importance(self) -> Optional[pd.Series]:
        """Return feature importances as a pd.Series, or None."""
        if self._model and hasattr(self._model, "feature_importances_"):
            return self._model.feature_importances_
        return None

    # ── Private helpers ───────────────────────────────────────────────────────

    def _get_features(self) -> Optional[pd.DataFrame]:
        """Lazily extract and cache the feature matrix, reusing the app's open DB connection."""
        if self._feat_df is not None:
            return self._feat_df
        try:
            from src.features.feature_engineering import (
                extract_equipment_features,
                load_raw_data,
                load_raw_data_from_conn,
            )

            # ── Preferred path: reuse the already-open data_service connection ──
            # data_service holds an exclusive Windows lock on the DB file, so
            # opening a second connection would fail. Borrowing its connection
            # avoids that entirely.
            bcg_df = crm_df = None
            try:
                from app.services.data_service import data_service as _ds
                conn = _ds.get_conn()
                if conn is not None:
                    bcg_df, crm_df = load_raw_data_from_conn(conn)
            except Exception as shared_err:
                logger.debug("Shared-conn load failed (%s), falling back to file open", shared_err)

            # ── Fallback: open the file directly (works when no Streamlit lock) ─
            if bcg_df is None:
                bcg_df, crm_df = load_raw_data(self._db_path)

            if bcg_df is None or bcg_df.empty:
                return None

            self._feat_df, _ = extract_equipment_features(bcg_df, crm_df)

            # ── Enrich with Axel IB location data (site city, last startup) ──
            self._feat_df = self._enrich_with_ib(self._feat_df)

            return self._feat_df
        except Exception as e:
            logger.warning("Feature extraction failed: %s", e)
            return None

    def _enrich_with_ib(self, feat_df: pd.DataFrame) -> pd.DataFrame:
        """Join Axel's IB list to add site_city, last_startup, capacity columns."""
        try:
            from app.services.historical_service import _load_ib
            ib = _load_ib()
            if ib.empty or "_company" not in feat_df.columns:
                return feat_df

            customer_col = next((c for c in ["ib_customer", "account_name"] if c in ib.columns), None)
            city_col     = next((c for c in ["ib_city", "city"] if c in ib.columns), None)
            year_col     = next((c for c in ["ib_startup"] if c in ib.columns), None)

            if not customer_col:
                return feat_df

            # Build lookup: normalised company name -> (city list, max startup year)
            import re
            def _n(s): return re.sub(r"[^a-z0-9]", "", str(s).lower())

            ib_lookup: dict = {}
            for _, row in ib.iterrows():
                key = _n(str(row.get(customer_col, "")))
                if not key:
                    continue
                city = str(row.get(city_col, "")).strip() if city_col else ""
                yr   = row.get(year_col, None) if year_col else None
                try:
                    yr = int(float(yr)) if yr and str(yr).strip() else None
                except (ValueError, TypeError):
                    yr = None
                if key not in ib_lookup:
                    ib_lookup[key] = {"cities": set(), "years": []}
                if city:
                    ib_lookup[key]["cities"].add(city)
                if yr:
                    ib_lookup[key]["years"].append(yr)

            def _lookup_city(company):
                key = _n(str(company))[:10]
                for k, v in ib_lookup.items():
                    if key in k or k in _n(str(company)):
                        return ", ".join(sorted(v["cities"]))[:60]
                return ""

            def _lookup_year(company):
                key = _n(str(company))[:10]
                for k, v in ib_lookup.items():
                    if key in k or k in _n(str(company)):
                        if v["years"]:
                            return max(v["years"])
                return None

            feat_df = feat_df.copy()
            feat_df["_site_city"]     = feat_df["_company"].apply(_lookup_city)
            feat_df["_last_startup"]  = feat_df["_company"].apply(_lookup_year)
        except Exception as e:
            logger.debug("IB enrichment skipped: %s", e)

        return feat_df

    def get_ib_enriched_row(self, company: str) -> dict:
        """Return IB enrichment fields for a single company (for explanation card)."""
        feat_df = self._get_features()
        if feat_df is None or "_company" not in feat_df.columns:
            return {}
        mask = feat_df["_company"].str.lower().str.contains(company[:8].lower(), na=False)
        rows = feat_df[mask]
        if rows.empty:
            return {}
        row = rows.iloc[0]
        return {
            "site_city":    row.get("_site_city", ""),
            "last_startup": row.get("_last_startup", None),
        }


    def _heuristic_ranked_list(
        self,
        equipment_type: Optional[str],
        country: Optional[str],
        top_k: Optional[int],
    ) -> pd.DataFrame:
        """
        Build a heuristic ranking directly from BCG data.
        Score = age × 3 + sms_oem × 15 + crm_rating × 2  (capped at 100).
        """
        from src.features.feature_engineering import (
            extract_equipment_features,
            load_raw_data,
            load_raw_data_from_conn,
        )
        _empty = pd.DataFrame(columns=["rank", "company", "equipment_type",
                                        "country", "equipment_age", "priority_score"])
        try:
            bcg_df = crm_df = None
            try:
                from app.services.data_service import data_service as _ds
                conn = _ds.get_conn()
                if conn is not None:
                    bcg_df, crm_df = load_raw_data_from_conn(conn)
            except Exception:
                pass

            if bcg_df is None:
                bcg_df, crm_df = load_raw_data(self._db_path)

            feat_df, _ = extract_equipment_features(bcg_df, crm_df)
        except Exception as e:
            logger.warning("Heuristic fallback data load failed: %s", e)
            return _empty

        df = feat_df.copy()
        df["priority_score"] = (
            df["equipment_age"].clip(0, 30) * 3.0
            + df["is_sms_oem"] * 15.0
            + df["crm_rating_num"] * 2.0
        ).clip(0, 100).round(1)

        if equipment_type:
            df = df[df["_equipment_type"].str.contains(equipment_type, case=False, na=False)]
        if country:
            df = df[df["_country"].str.contains(country, case=False, na=False)]

        df = df.sort_values("priority_score", ascending=False).reset_index(drop=True)
        df.index += 1

        out = df[["_company", "_equipment_type", "_country", "_equipment_age", "priority_score"]].copy()
        out.columns = ["company", "equipment_type", "country", "equipment_age", "priority_score"]
        out.insert(0, "rank", out.index)

        if top_k:
            out = out.head(top_k)
        return out



# Singleton (uses settings.DB_PATH automatically)
def _make_service() -> MLRankingService:
    try:
        from app.core.config import settings
        return MLRankingService(db_path=settings.DB_PATH)
    except Exception:
        return MLRankingService(db_path=Path(__file__).parent.parent.parent / "data" / "sales_app.db")


ml_ranking_service = _make_service()
