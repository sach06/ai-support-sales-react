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
        from app.services.ranking_reranker_service import ranking_reranker_service
        self._feat_df = None
        self._labels  = None
        ranking_reranker_service.clear_cache()

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
                        feat_df, equipment_type=equipment_type, top_k=None
                    )
                    if country and "country" in result.columns:
                        result = result[result["country"].str.contains(country, case=False, na=False)]
                    result = self._apply_recent_signal_rerank(result, top_k=top_k)
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

    def _load_bcg_crm_via_data_service(self) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """Load BCG/CRM data via DataIngestionService thread-safe queries.

        This avoids opening a second DuckDB connection, which is prone to
        WinError 32 on Windows when the app already holds an exclusive lock.
        """
        from app.services.data_service import data_service as _ds

        tables_df = _ds.execute_df("SHOW TABLES")
        table_names = set(tables_df.iloc[:, 0].astype(str).tolist()) if not tables_df.empty else set()

        bcg_candidates = ["bcg_installed_base", "bcg_data", "installed_base", "bcg"]
        crm_candidates = ["crm_data", "crm", "customers", "unified_companies"]

        bcg_table = next((t for t in bcg_candidates if t in table_names), None)
        crm_table = next((t for t in crm_candidates if t in table_names), None)

        if not bcg_table:
            raise RuntimeError("No BCG table available in DuckDB")

        bcg_df = _ds.execute_df(f"SELECT * FROM {bcg_table}")
        crm_df = _ds.execute_df(f"SELECT * FROM {crm_table}") if crm_table else pd.DataFrame()
        return bcg_df, crm_df

    def _load_external_features_via_data_service(self) -> Tuple[pd.DataFrame, pd.DataFrame]:
        from app.services.data_service import data_service as _ds

        tables_df = _ds.execute_df("SHOW TABLES")
        table_names = set(tables_df.iloc[:, 0].astype(str).tolist()) if not tables_df.empty else set()

        company_df = _ds.execute_df("SELECT * FROM company_external_features") if "company_external_features" in table_names else pd.DataFrame()
        country_df = _ds.execute_df("SELECT * FROM country_market_features") if "country_market_features" in table_names else pd.DataFrame()
        return company_df, country_df

    def retrain_model(self, data_snapshot_id: str = "live_duckdb") -> Dict:
        """
        Retrain XGBoost model on current DuckDB data and persist artifact/metadata.

        Returns metrics and model paths.
        """
        try:
            from src.features.feature_engineering import (
                build_labels,
                extract_equipment_features,
                load_external_feature_data,
                load_raw_data,
            )
            from src.models.xgb_ranking_model import XGBPriorityModel
        except Exception as exc:
            raise RuntimeError(f"Training dependencies unavailable: {exc}") from exc

        bcg_df = crm_df = external_company_df = external_country_df = None
        try:
            bcg_df, crm_df = self._load_bcg_crm_via_data_service()
            external_company_df, external_country_df = self._load_external_features_via_data_service()
        except Exception as shared_err:
            logger.debug("Thread-safe shared training load failed (%s), falling back to direct open", shared_err)

        if bcg_df is None:
            bcg_df, crm_df = load_raw_data(self._db_path)
            external_company_df, external_country_df = load_external_feature_data(self._db_path)

        if bcg_df is None or bcg_df.empty:
            raise RuntimeError("No BCG installed-base data available for retraining")

        feat_df, meta = extract_equipment_features(
            bcg_df,
            crm_df,
            external_company_df=external_company_df,
            external_country_df=external_country_df,
        )
        feature_columns = meta.get("feature_columns", [])
        if not feature_columns:
            raise RuntimeError("Feature engineering produced no model columns")

        labels = build_labels(bcg_df, crm_df)
        if labels is None or labels.empty:
            raise RuntimeError("Label generation failed; no training labels available")

        model = XGBPriorityModel(model_path=self._model_path)
        metrics = model.train(
            X=feat_df,
            y=labels,
            feature_columns=feature_columns,
            data_snapshot_id=data_snapshot_id,
        )
        model_path, meta_path = model.save(model_path=self._model_path)

        self._model = model
        self.clear_cache()

        return {
            "status": "ok",
            "metrics": metrics,
            "feature_count": len(feature_columns),
            "sample_count": int(len(feat_df)),
            "model_path": str(model_path),
            "meta_path": str(meta_path),
        }

    def get_feature_importance(self) -> Optional[pd.Series]:
        """Return feature importances as a pd.Series, or None."""
        if self._model and hasattr(self._model, "feature_importances_"):
            return self._model.feature_importances_
        return None

    def _apply_recent_signal_rerank(self, ranked_df: pd.DataFrame, top_k: Optional[int]) -> pd.DataFrame:
        from app.services.ranking_reranker_service import ranking_reranker_service

        if ranked_df is None or ranked_df.empty:
            return ranked_df

        df = ranked_df.copy()
        if "base_priority_score" not in df.columns:
            df["base_priority_score"] = pd.to_numeric(df["priority_score"], errors="coerce").fillna(0.0)
        df["rerank_adjustment"] = 0.0
        df["rerank_recent_mentions"] = 0
        df["rerank_recent_sources"] = 0
        df["rerank_reasons"] = [[] for _ in range(len(df))]

        candidate_count = min(len(df), max(min((top_k or 50) * 2, 100), 50))
        candidate_df = df.head(candidate_count).copy()

        for idx, row in candidate_df.iterrows():
            payload = ranking_reranker_service.score_recent_signals(
                company_name=row.get("company", ""),
                country=row.get("country", ""),
            )
            candidate_df.at[idx, "rerank_adjustment"] = float(payload.get("rerank_adjustment", 0.0) or 0.0)
            candidate_df.at[idx, "rerank_recent_mentions"] = int(payload.get("rerank_recent_mentions", 0) or 0)
            candidate_df.at[idx, "rerank_recent_sources"] = int(payload.get("rerank_recent_sources", 0) or 0)
            candidate_df.at[idx, "rerank_reasons"] = payload.get("rerank_reasons", []) or []

        candidate_df["priority_score"] = (candidate_df["base_priority_score"] + candidate_df["rerank_adjustment"]).clip(0, 100).round(1)
        untouched_df = df.iloc[candidate_count:].copy()
        if not untouched_df.empty:
            untouched_df["priority_score"] = pd.to_numeric(untouched_df["base_priority_score"], errors="coerce").fillna(0.0).round(1)

        combined = pd.concat([candidate_df, untouched_df], ignore_index=True)
        combined = combined.sort_values("priority_score", ascending=False).reset_index(drop=True)
        combined.index += 1
        if "rank" in combined.columns:
            combined["rank"] = combined.index
        if top_k:
            combined = combined.head(top_k)
        return combined

    # ── Private helpers ───────────────────────────────────────────────────────

    def _get_features(self) -> Optional[pd.DataFrame]:
        """Lazily extract and cache the feature matrix, reusing the app's open DB connection."""
        if self._feat_df is not None:
            return self._feat_df
        try:
            from src.features.feature_engineering import (
                extract_equipment_features,
                load_external_feature_data,
                load_raw_data,
            )

            # ── Preferred path: reuse the already-open data_service connection ──
            # data_service holds an exclusive Windows lock on the DB file, so
            # opening a second connection would fail. Borrowing its connection
            # avoids that entirely.
            bcg_df = crm_df = external_company_df = external_country_df = None
            try:
                bcg_df, crm_df = self._load_bcg_crm_via_data_service()
                external_company_df, external_country_df = self._load_external_features_via_data_service()
            except Exception as shared_err:
                logger.debug("Thread-safe shared load failed (%s), falling back to file open", shared_err)

            # ── Fallback: open the file directly (works when no Streamlit lock) ─
            if bcg_df is None:
                bcg_df, crm_df = load_raw_data(self._db_path)
                external_company_df, external_country_df = load_external_feature_data(self._db_path)

            if bcg_df is None or bcg_df.empty:
                return None

            self._feat_df, _ = extract_equipment_features(
                bcg_df,
                crm_df,
                external_company_df=external_company_df,
                external_country_df=external_country_df,
            )

            # Prefer per-row city from BCG so Ranking "Site / City" matches Overview tables.
            city_col = next((c for c in ["city_internal", "City", "city", "site_name"] if c in bcg_df.columns), None)
            if city_col is not None:
                self._feat_df["_site_city"] = bcg_df[city_col].fillna("").astype(str)

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
            if "_site_city" not in feat_df.columns:
                feat_df["_site_city"] = ""

            feat_df["_site_city"] = feat_df.apply(
                lambda r: r.get("_site_city") if str(r.get("_site_city", "")).strip() else _lookup_city(r.get("_company", "")),
                axis=1
            )
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
            load_external_feature_data,
            load_raw_data,
        )
        _empty = pd.DataFrame(columns=["rank", "company", "equipment_type",
                                        "country", "equipment_age", "priority_score"])
        try:
            bcg_df = crm_df = external_company_df = external_country_df = None
            try:
                bcg_df, crm_df = self._load_bcg_crm_via_data_service()
                external_company_df, external_country_df = self._load_external_features_via_data_service()
            except Exception:
                pass

            if bcg_df is None:
                bcg_df, crm_df = load_raw_data(self._db_path)
                external_company_df, external_country_df = load_external_feature_data(self._db_path)

            feat_df, _ = extract_equipment_features(
                bcg_df,
                crm_df,
                external_company_df=external_company_df,
                external_country_df=external_country_df,
            )
        except Exception as e:
            logger.warning("Heuristic fallback data load failed: %s", e)
            return _empty

        df = feat_df.copy()
        df["base_priority_score"] = (
            df["equipment_age"].clip(0, 30) * 3.0
            + df["is_sms_oem"] * 15.0
            + df["crm_rating_num"] * 2.0
        ).clip(0, 100).round(1)
        df["priority_score"] = df["base_priority_score"]

        if equipment_type:
            df = df[df["_equipment_type"].str.contains(equipment_type, case=False, na=False)]
        if country:
            df = df[df["_country"].str.contains(country, case=False, na=False)]

        df = df.sort_values("priority_score", ascending=False).reset_index(drop=True)
        df.index += 1

        cols_to_keep = ["_company", "_equipment_type", "_country", "_equipment_age", "priority_score", "base_priority_score"]
        final_cols = ["company", "equipment_type", "country", "equipment_age", "priority_score", "base_priority_score"]
        if "_site_city" in df.columns:
            cols_to_keep.append("_site_city")
            final_cols.append("site_city")

        knowledge_cols = [
            "knowledge_doc_count",
            "knowledge_best_match_score",
            "knowledge_avg_match_score",
            "knowledge_service_signal",
            "knowledge_inspection_signal",
            "knowledge_modernization_signal",
            "knowledge_digital_signal",
            "knowledge_decarbonization_signal",
            "knowledge_project_signal",
            "knowledge_quality_signal",
        ]
        for col in knowledge_cols:
            if col in df.columns:
                cols_to_keep.append(col)
                final_cols.append(col)

        out = df[cols_to_keep].copy()
        out.columns = final_cols
        out.insert(0, "rank", out.index)
        return self._apply_recent_signal_rerank(out, top_k=top_k)



# Singleton (uses settings.DB_PATH automatically)
def _make_service() -> MLRankingService:
    try:
        from app.core.config import settings
        return MLRankingService(db_path=settings.DB_PATH)
    except Exception:
        return MLRankingService(db_path=Path(__file__).parent.parent.parent / "data" / "sales_app.db")


ml_ranking_service = _make_service()
