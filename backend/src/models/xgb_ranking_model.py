"""
XGBoost Priority-Ranking Model
================================
Trains a binary XGBoost classifier (binary:logistic) that produces
probability [0, 1] used to rank customers/equipment by likelihood of
"doing business" with SMS Group.

Design decisions
----------------
- Pointwise binary classifier (not rank:pairwise) for simplicity and
  interpretability; probability output is directly usable as a ranking score.
- Single global model, results filtered/sorted per EquipmentType.
- CPU-only (tree_method='hist').
- Persisted via joblib + metadata JSON.
- SHAP values computed for business-facing explanations.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import joblib
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# ─ optional heavy imports ─────────────────────────────────────────────────────
try:
    import xgboost as xgb
    XGB_AVAILABLE = True
except ImportError:
    XGB_AVAILABLE = False
    logger.warning("xgboost not installed – model training disabled")

try:
    import shap
    SHAP_AVAILABLE = True
except ImportError:
    SHAP_AVAILABLE = False
    logger.warning("shap not installed – SHAP explainability disabled")

try:
    from sklearn.model_selection import StratifiedKFold, cross_val_score
    from sklearn.metrics import roc_auc_score, precision_score
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False

# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────

DEFAULT_MODEL_PATH = Path(__file__).parent.parent.parent / "models" / "xgb_priority_v1.pkl"
DEFAULT_META_PATH  = DEFAULT_MODEL_PATH.with_suffix(".meta.json")

SEED = 42

XGB_PARAMS: Dict = {
    "objective":        "binary:logistic",
    "eval_metric":      "auc",
    "tree_method":      "hist",          # CPU-optimised
    "max_depth":        5,
    "learning_rate":    0.05,
    "n_estimators":     500,
    "subsample":        0.8,
    "colsample_bytree": 0.8,
    "min_child_weight": 5,
    "reg_alpha":        0.1,
    "reg_lambda":       1.0,
    "scale_pos_weight": 1,               # updated at train time
    "random_state":     SEED,
    "n_jobs":           -1,
    "verbosity":        0,
}


# ─────────────────────────────────────────────────────────────────────────────
# Evaluation helpers
# ─────────────────────────────────────────────────────────────────────────────

def precision_at_k(y_true: np.ndarray, y_score: np.ndarray, k: int = 10) -> float:
    """Precision@K: fraction of the top-K ranked items that are true positives."""
    k = min(k, len(y_true))
    if k == 0:
        return 0.0
    top_k_idx = np.argsort(y_score)[::-1][:k]
    return float(np.mean(y_true[top_k_idx]))


def ndcg_at_k(y_true: np.ndarray, y_score: np.ndarray, k: int = 10) -> float:
    """NDCG@K (binary relevance)."""
    k = min(k, len(y_true))
    if k == 0:
        return 0.0
    top_k_idx  = np.argsort(y_score)[::-1][:k]
    gains      = y_true[top_k_idx]
    discounts  = np.log2(np.arange(2, k + 2))
    dcg        = float((gains / discounts).sum())
    ideal_gains = np.sort(y_true)[::-1][:k]
    idcg       = float((ideal_gains / discounts[:len(ideal_gains)]).sum())
    return dcg / idcg if idcg > 0 else 0.0


# ─────────────────────────────────────────────────────────────────────────────
# Core model class
# ─────────────────────────────────────────────────────────────────────────────

class XGBPriorityModel:
    """Wraps XGBoost training, evaluation, persistence, and inference."""

    def __init__(
        self,
        model_path: str | Path = DEFAULT_MODEL_PATH,
        meta_path:  str | Path = DEFAULT_META_PATH,
    ):
        self.model_path = Path(model_path)
        self.meta_path  = Path(meta_path)
        self.model: Optional["xgb.XGBClassifier"]  = None
        self.feature_columns: List[str] = []
        self.feature_importances_: Optional[pd.Series] = None
        self._meta: dict = {}

    # ── Training ──────────────────────────────────────────────────────────────

    def train(
        self,
        X: pd.DataFrame,
        y: pd.Series,
        feature_columns: List[str],
        eval_split: float = 0.2,
        data_snapshot_id: str = "unknown",
    ) -> Dict:
        """
        Train the XGBoost model with early stopping and cross-validation.

        Parameters
        ----------
        X                 : Feature matrix (rows = equipment units)
        y                 : Binary labels
        feature_columns   : Ordered list of feature column names used
        eval_split        : Fraction held out as a temporal/random test set
        data_snapshot_id  : Identifier of the data version used for training

        Returns
        -------
        metrics : dict with auc_cv, auc_test, precision_at_10, ndcg_at_10
        """
        if not XGB_AVAILABLE:
            raise ImportError("xgboost is required for training")

        X = X[feature_columns].astype(float)
        y = y.astype(int)

        logger.info("Training XGBoost on %d samples, %d features", len(X), len(feature_columns))
        logger.info("Label distribution: %d pos / %d neg", y.sum(), (y == 0).sum())

        # ── Train / test split (stratified random; swap for time-split later) ──
        from sklearn.model_selection import train_test_split
        X_tr, X_te, y_tr, y_te = train_test_split(
            X, y, test_size=eval_split, stratify=y, random_state=SEED
        )

        # ── Adjust class weight for imbalance ─────────────────────────────────
        neg, pos = (y_tr == 0).sum(), (y_tr == 1).sum()
        scale_pos = neg / max(pos, 1)

        params = {**XGB_PARAMS, "scale_pos_weight": scale_pos}

        model = xgb.XGBClassifier(**params)

        # Early stopping on hold-out
        model.fit(
            X_tr, y_tr,
            eval_set=[(X_te, y_te)],
            verbose=False,
        )

        # ── Cross-validation AUC ──────────────────────────────────────────────
        # Cap n_splits so we never ask for more folds than training samples
        min_class_count = int(min(y_tr.sum(), (y_tr == 0).sum()))
        n_cv_splits = max(2, min(5, min_class_count))
        if n_cv_splits >= 2 and len(X_tr) >= n_cv_splits:
            cv = StratifiedKFold(n_splits=n_cv_splits, shuffle=True, random_state=SEED)
            cv_scores = cross_val_score(
                xgb.XGBClassifier(**params), X_tr, y_tr,
                cv=cv, scoring="roc_auc", n_jobs=-1
            )
        else:
            logger.warning("Too few samples for CV (%d train rows) – skipping cross-validation", len(X_tr))
            cv_scores = np.array([np.nan])

        # ── Hold-out evaluation ───────────────────────────────────────────────
        y_prob   = model.predict_proba(X_te)[:, 1]
        auc_test = roc_auc_score(y_te, y_prob)
        eval_k   = min(10, len(y_te))          # cap k to actual test-set size
        p_at_10  = precision_at_k(y_te.to_numpy(), y_prob, k=eval_k)
        ndcg     = ndcg_at_k(y_te.to_numpy(), y_prob, k=eval_k)

        metrics = {
            "auc_cv_mean":    float(cv_scores.mean()),
            "auc_cv_std":     float(cv_scores.std()),
            "auc_test":       float(auc_test),
            "precision_at_10": float(p_at_10),
            "ndcg_at_10":     float(ndcg),
            "n_estimators_used": int(model.n_estimators),
            "train_size":     len(X_tr),
            "test_size":      len(X_te),
            "pos_rate_train": float(y_tr.mean()),
        }

        logger.info(
            "Training done → AUC-CV: %.3f±%.3f | AUC-test: %.3f | P@10: %.3f | NDCG@10: %.3f",
            metrics["auc_cv_mean"], metrics["auc_cv_std"],
            metrics["auc_test"], metrics["precision_at_10"], metrics["ndcg_at_10"]
        )

        # ── Feature importance ────────────────────────────────────────────────
        self.feature_importances_ = pd.Series(
            model.feature_importances_, index=feature_columns
        ).sort_values(ascending=False)

        self.model          = model
        self.feature_columns = feature_columns
        self._meta = {
            "model_version":    "xgb_priority_v1",
            "trained_at":       datetime.now().isoformat(),
            "data_snapshot_id": data_snapshot_id,
            "feature_columns":  feature_columns,
            "xgb_params":       params,
            "metrics":          metrics,
            "feature_importance": self.feature_importances_.to_dict(),
        }

        return metrics

    # ── Inference ─────────────────────────────────────────────────────────────

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        """Return probability scores [0, 1] for each row in X."""
        if self.model is None:
            raise RuntimeError("Model not trained or loaded. Call train() or load().")
        X_feat = X[self.feature_columns].astype(float)
        return self.model.predict_proba(X_feat)[:, 1]

    def rank_by_equipment_type(
        self,
        feat_df: pd.DataFrame,
        equipment_type: Optional[str] = None,
        top_k: Optional[int] = None,
    ) -> pd.DataFrame:
        """
        Score all rows in feat_df and return a ranked DataFrame.

        Parameters
        ----------
        feat_df        : Feature DataFrame (must contain _equipment_type, _company, _country)
        equipment_type : If provided, filter to matching EquipmentType before ranking
        top_k          : If provided, return only the top-K rows

        Returns
        -------
        Ranked DataFrame with columns:
          rank | company | equipment_type | country | equipment_age | priority_score
        """
        df = feat_df.copy()
        df["priority_score"] = (self.predict_proba(df) * 100).round(1)

        # Filter
        if equipment_type:
            mask = df["_equipment_type"].str.contains(equipment_type, case=False, na=False)
            df = df[mask]

        df = df.sort_values("priority_score", ascending=False).reset_index(drop=True)
        df.index += 1  # 1-based rank

        out = df[["_company", "_equipment_type", "_country", "_equipment_age", "priority_score"]].copy()
        out.columns = ["company", "equipment_type", "country", "equipment_age", "priority_score"]
        out.insert(0, "rank", out.index)

        if top_k:
            out = out.head(top_k)

        return out

    def per_equipment_type_metrics(
        self,
        feat_df: pd.DataFrame,
        labels: pd.Series,
        k: int = 10,
    ) -> pd.DataFrame:
        """
        Compute Precision@K and NDCG@K broken down by EquipmentType.
        """
        df = feat_df.copy()
        df["_label"]         = labels.values
        df["priority_score"] = self.predict_proba(df)

        rows = []
        for eq_type, grp in df.groupby("_equipment_type"):
            if len(grp) < 2:
                continue
            y_t = grp["_label"].to_numpy()
            y_s = grp["priority_score"].to_numpy()
            try:
                auc  = roc_auc_score(y_t, y_s) if len(np.unique(y_t)) > 1 else np.nan
            except Exception:
                auc  = np.nan
            p_k  = precision_at_k(y_t, y_s, k=min(k, len(grp)))
            ndcg = ndcg_at_k(y_t, y_s, k=min(k, len(grp)))
            rows.append({
                "equipment_type": eq_type,
                "n_items":        len(grp),
                "n_positive":     int(y_t.sum()),
                "roc_auc":        round(auc, 3) if not np.isnan(auc) else None,
                f"precision_at_{k}": round(p_k, 3),
                f"ndcg_at_{k}":    round(ndcg, 3),
            })

        return pd.DataFrame(rows).sort_values("n_items", ascending=False)

    # ── SHAP explainability ───────────────────────────────────────────────────

    def compute_shap(self, X: pd.DataFrame) -> Optional[pd.DataFrame]:
        """Return a DataFrame of SHAP values (one column per feature)."""
        if not SHAP_AVAILABLE or self.model is None:
            return None
        try:
            explainer   = shap.TreeExplainer(self.model)
            X_feat      = X[self.feature_columns].astype(float)
            shap_values = explainer.shap_values(X_feat)
            return pd.DataFrame(shap_values, columns=self.feature_columns, index=X.index)
        except Exception as e:
            logger.warning("SHAP computation failed: %s", e)
            return None

    # ── Persistence ───────────────────────────────────────────────────────────

    def save(
        self,
        model_path: Optional[str | Path] = None,
        meta_path:  Optional[str | Path] = None,
    ) -> Tuple[Path, Path]:
        """
        Persist model artifact (joblib .pkl) and metadata JSON.

        Returns (model_path, meta_path).
        """
        mp = Path(model_path) if model_path else self.model_path
        ap = Path(meta_path)  if meta_path  else self.meta_path
        mp.parent.mkdir(parents=True, exist_ok=True)

        artifact = {
            "model":           self.model,
            "feature_columns": self.feature_columns,
            "meta":            self._meta,
        }
        joblib.dump(artifact, mp, protocol=4)
        ap.write_text(json.dumps(self._meta, indent=2, default=str))

        logger.info("Model saved → %s", mp)
        logger.info("Metadata   → %s", ap)
        return mp, ap

    def load(
        self,
        model_path: Optional[str | Path] = None,
    ) -> "XGBPriorityModel":
        """Load a persisted artifact. Returns self for chaining."""
        mp = Path(model_path) if model_path else self.model_path
        if not mp.exists():
            raise FileNotFoundError(f"Model file not found: {mp}")

        artifact = joblib.load(mp)
        self.model           = artifact["model"]
        self.feature_columns = artifact["feature_columns"]
        self._meta           = artifact.get("meta", {})

        if hasattr(self.model, "feature_importances_"):
            self.feature_importances_ = pd.Series(
                self.model.feature_importances_,
                index=self.feature_columns
            ).sort_values(ascending=False)

        logger.info("Model loaded from %s", mp)
        return self
