"""
Feature engineering for XGBoost priority-ranking model.

Extracts features from:
  - BCG installed-base (equipment-level rows)
  - CRM export (company + project-level rows)
  - (optional) internet-enrichment cache stored in DuckDB

Label definition
----------------
Binary:  label = 1 if the BCG company has a matching CRM record
         with at least one project (any status).
         label = 0 for BCG-only companies with no CRM match.

This is the most reliable "doing business with SMS Group" proxy
available in the current dataset.
"""

from __future__ import annotations

import re
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple

import duckdb
import numpy as np
import pandas as pd
from sklearn.preprocessing import LabelEncoder

logger = logging.getLogger(__name__)

CURRENT_YEAR = datetime.now().year

# ── Column-name aliases that appear across BCG / CRM schemas ─────────────────
_YEAR_COLS      = ["start_year_internal", "start_year", "year", "installation_year", "commission_year", "Startup Year"]
_OEM_COLS       = ["OEM", "supplier", "oem", "manufacturer", "original_equipment_manufacturer"]
_EQ_TYPE_COLS   = ["equipment_type", "Equipment Type", "equipment", "type"]
_COMPANY_COLS   = ["company_internal", "company_name", "Company Name", "name", "customer_name", "ib_customer"]
_RATING_COLS    = ["crm_rating", "rating", "CRM Rating", "customer_rating"]
_COUNTRY_COLS   = ["country_internal", "country", "Country", "ib_customer_country", "region", "location"]


# ─────────────────────────────────────────────────────────────────────────────
# Low-level helpers
# ─────────────────────────────────────────────────────────────────────────────

def _first_col(df: pd.DataFrame, candidates: list[str]) -> Optional[str]:
    """Return the first column name from *candidates* that exists in *df*."""
    for c in candidates:
        if c in df.columns:
            return c
    return None


def _parse_int(val, default: int = 0) -> int:
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return default
    try:
        return int(float(str(val).replace(",", "").split(".")[0]))
    except Exception:
        return default


def _normalise_name(name: str) -> str:
    """Lowercase, strip legal suffixes, collapse whitespace."""
    name = str(name).lower()
    name = re.sub(r"\b(gmbh|co|kg|inc|ltd|llc|corp|ag|sa|spa|nv|bv|as|ab|oy|plc)\b\.?", "", name)
    name = re.sub(r"[^a-z0-9 ]", " ", name)
    return re.sub(r"\s+", " ", name).strip()


def _rating_num(rating: str) -> int:
    return {"A": 5, "B": 4, "C": 3, "D": 2, "E": 1}.get(str(rating).strip().upper(), 3)


# ─────────────────────────────────────────────────────────────────────────────
# Data loading
# ─────────────────────────────────────────────────────────────────────────────

def load_raw_data(db_path: str | Path) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Load BCG installed-base and CRM tables from DuckDB.

    Returns
    -------
    bcg_df : pd.DataFrame   – one row per equipment unit
    crm_df : pd.DataFrame   – CRM company + project summary
    """
    # DuckDB on Windows uses exclusive file locking. If another process (e.g. the
    # running Streamlit app) has the DB open, we must read from a temp copy.
    import shutil, tempfile
    db_path = Path(db_path)

    def _connect(path: Path, read_only: bool = True):
        return duckdb.connect(str(path), read_only=read_only)

    conn = None
    tmp_path = None
    try:
        conn = _connect(db_path, read_only=True)
    except Exception as lock_err:
        logger.warning("Direct open failed (%s) – copying DB to temp file …", lock_err)
        try:
            tmp_fd, tmp_str = tempfile.mkstemp(suffix=".db")
            import os; os.close(tmp_fd)
            tmp_path = Path(tmp_str)
            shutil.copy2(db_path, tmp_path)
            conn = _connect(tmp_path, read_only=False)
            logger.info("Connected to temp copy: %s", tmp_path)
        except Exception as e2:
            raise RuntimeError(
                f"Cannot open DuckDB at {db_path}: {e2}. "
                "Try stopping the Streamlit app and re-running."
            ) from e2

    try:
        tables = {r[0] for r in conn.execute("SHOW TABLES").fetchall()}
        logger.info("Available DuckDB tables: %s", tables)

        # ── BCG (installed base) ──────────────────────────────────────────────────
        # Prefer bcg_installed_base (has internal/normalised columns) over
        # the raw bcg_data dump (which has original xlsx column names)
        bcg_candidates = ["bcg_installed_base", "bcg_data", "installed_base", "bcg"]
        bcg_table = next((t for t in bcg_candidates if t in tables), None)
        if bcg_table:
            bcg_df = conn.execute(f"SELECT * FROM {bcg_table}").df()
            logger.info("Loaded BCG table '%s': %d rows", bcg_table, len(bcg_df))
        else:
            logger.warning("No BCG table found – returning empty DataFrame")
            bcg_df = pd.DataFrame()

        # ── CRM ───────────────────────────────────────────────────────────────────
        crm_candidates = ["crm_data", "crm", "customers", "unified_companies"]
        crm_table = next((t for t in crm_candidates if t in tables), None)
        if crm_table:
            crm_df = conn.execute(f"SELECT * FROM {crm_table}").df()
            logger.info("Loaded CRM table '%s': %d rows", crm_table, len(crm_df))
        else:
            logger.warning("No CRM table found – labels will default to 0")
            crm_df = pd.DataFrame()

    finally:
        conn.close()
        if tmp_path is not None:
            try:
                tmp_path.unlink(missing_ok=True)
                logger.info("Temp DB copy removed.")
            except Exception:
                pass

    return bcg_df, crm_df


def load_raw_data_from_conn(conn) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Load BCG and CRM tables using an **already-open** DuckDB connection.

    Use this inside the Streamlit app where ``data_service.get_conn()``
    already holds the file lock — avoids the Windows exclusive-lock error
    that would occur if we tried to open a second connection to the same file.

    The caller is responsible for the connection lifecycle (do not close it
    here; it belongs to the caller).
    """
    tables = {r[0] for r in conn.execute("SHOW TABLES").fetchall()}
    logger.info("(shared conn) Available DuckDB tables: %s", tables)

    # Prefer bcg_installed_base (has normalised internal columns) over raw dump
    bcg_candidates = ["bcg_installed_base", "bcg_data", "installed_base", "bcg"]
    bcg_table = next((t for t in bcg_candidates if t in tables), None)
    if bcg_table:
        bcg_df = conn.execute(f"SELECT * FROM {bcg_table}").df()
        logger.info("Loaded BCG table '%s': %d rows", bcg_table, len(bcg_df))
    else:
        logger.warning("No BCG table found – returning empty DataFrame")
        bcg_df = pd.DataFrame()

    crm_candidates = ["crm_data", "crm", "customers", "unified_companies"]
    crm_table = next((t for t in crm_candidates if t in tables), None)
    if crm_table:
        crm_df = conn.execute(f"SELECT * FROM {crm_table}").df()
        logger.info("Loaded CRM table '%s': %d rows", crm_table, len(crm_df))
    else:
        logger.warning("No CRM table found – labels will default to 0")
        crm_df = pd.DataFrame()

    return bcg_df, crm_df


# ─────────────────────────────────────────────────────────────────────────────
# Label engineering
# ─────────────────────────────────────────────────────────────────────────────

def build_labels(bcg_df: pd.DataFrame, crm_df: pd.DataFrame) -> pd.Series:
    """
    Binary label: 1 if BCG company matches a CRM record (has done business),
    0 otherwise.

    Matching strategy
    -----------------
    1. Exact normalised-name match (fast path)
    2. Substring containment (medium path)

    Returns a pd.Series aligned with *bcg_df* index.
    """
    if crm_df.empty:
        logger.warning("CRM data empty – all labels set to 0")
        return pd.Series(0, index=bcg_df.index)

    bcg_company_col = _first_col(bcg_df, _COMPANY_COLS)
    crm_company_col = _first_col(crm_df, _COMPANY_COLS)

    if not bcg_company_col or not crm_company_col:
        logger.warning("Could not find company columns – all labels 0")
        return pd.Series(0, index=bcg_df.index)

    # Build set of normalised CRM names
    crm_names: set[str] = set(crm_df[crm_company_col].dropna().map(_normalise_name))

    def _is_match(raw_name: str) -> int:
        n = _normalise_name(raw_name)
        if n in crm_names:
            return 1
        # substring: if any CRM name contains the BCG name or vice-versa
        for cn in crm_names:
            if (len(n) >= 4 and n in cn) or (len(cn) >= 4 and cn in n):
                return 1
        return 0

    labels = bcg_df[bcg_company_col].fillna("").map(_is_match)
    pos = labels.sum()
    logger.info(
        "Label distribution: %d positive (%.1f%%) / %d negative",
        pos, 100 * pos / max(len(labels), 1), len(labels) - pos
    )
    return labels


# ─────────────────────────────────────────────────────────────────────────────
# Feature extraction  (equipment-level)
# ─────────────────────────────────────────────────────────────────────────────

def extract_equipment_features(
    bcg_df: pd.DataFrame,
    crm_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Build the feature matrix X (one row per BCG equipment row).

    Numeric features
    ----------------
    equipment_age           years since installation / commission
    is_sms_oem              1 if SMS is the OEM / manufacturer
    crm_rating_num          0-5 rating from CRM match (3 = unknown)
    crm_projects_count      # projects in CRM for this company (0 = no match)
    log_fte                 log1p(employees from CRM)

    Encoded categoricals
    --------------------
    equipment_type_enc      LabelEncoder on EquipmentType
    country_enc             LabelEncoder on country / region
    """
    df = bcg_df.copy()

    # ── Equipment age ─────────────────────────────────────────────────────────
    year_col = _first_col(df, _YEAR_COLS)
    if year_col:
        df["equipment_age"] = df[year_col].apply(
            lambda v: max(0, CURRENT_YEAR - _parse_int(v, CURRENT_YEAR))
        )
    else:
        df["equipment_age"] = 10  # median fallback

    # ── OEM flag ─────────────────────────────────────────────────────────────
    oem_col = _first_col(df, _OEM_COLS)
    if oem_col:
        df["is_sms_oem"] = df[oem_col].fillna("").str.lower().str.contains("sms").astype(int)
    else:
        df["is_sms_oem"] = 0

    # ── Equipment type (encoded) ──────────────────────────────────────────────
    eq_col = _first_col(df, _EQ_TYPE_COLS)
    if eq_col:
        df["equipment_type_raw"] = df[eq_col].fillna("Unknown").str.strip()
    else:
        df["equipment_type_raw"] = "Unknown"

    le_eq = LabelEncoder()
    df["equipment_type_enc"] = le_eq.fit_transform(df["equipment_type_raw"].astype(str))

    # ── Country / region (encoded) ────────────────────────────────────────────
    country_col = _first_col(df, _COUNTRY_COLS)
    if country_col:
        df["country_raw"] = df[country_col].fillna("Unknown").str.strip()
    else:
        df["country_raw"] = "Unknown"

    le_country = LabelEncoder()
    df["country_enc"] = le_country.fit_transform(df["country_raw"].astype(str))

    # ── CRM enrichment (join by normalised name) ──────────────────────────────
    company_col = _first_col(df, _COMPANY_COLS)

    crm_lookup: dict[str, dict] = {}
    if not crm_df.empty:
        crm_company_col = _first_col(crm_df, _COMPANY_COLS)
        crm_rating_col = _first_col(crm_df, _RATING_COLS)
        fte_col = _first_col(crm_df, ["fte", "employees", "headcount"])
        proj_col = _first_col(crm_df, ["project_count", "projects_count", "num_projects"])

        for _, row in crm_df.iterrows():
            key = _normalise_name(str(row[crm_company_col]) if crm_company_col else "")
            crm_lookup[key] = {
                "rating": _rating_num(str(row[crm_rating_col])) if crm_rating_col else 3,
                "fte": _parse_int(row[fte_col]) if fte_col else 0,
                "proj_count": _parse_int(row[proj_col]) if proj_col else 0,
            }

    def _crm_info(raw_name: str) -> dict:
        n = _normalise_name(raw_name)
        if n in crm_lookup:
            return crm_lookup[n]
        for k, v in crm_lookup.items():
            if (len(n) >= 4 and n in k) or (len(k) >= 4 and k in n):
                return v
        return {"rating": 3, "fte": 0, "proj_count": 0}

    if company_col:
        crm_info = df[company_col].fillna("").map(_crm_info)
        df["crm_rating_num"]      = crm_info.map(lambda x: x["rating"])
        df["log_fte"]             = crm_info.map(lambda x: np.log1p(x["fte"]))
        df["crm_projects_count"]  = crm_info.map(lambda x: x["proj_count"])
    else:
        df["crm_rating_num"]     = 3
        df["log_fte"]            = 0.0
        df["crm_projects_count"] = 0

    # ── Final feature columns ────────────────────────────────────────────────
    FEATURE_COLS = [
        "equipment_age",
        "is_sms_oem",
        "equipment_type_enc",
        "country_enc",
        "crm_rating_num",
        "log_fte",
        "crm_projects_count",
    ]

    feat_df = df[FEATURE_COLS].copy()

    # Keep metadata columns alongside (not fed to the model)
    feat_df["_company"]        = df[company_col].fillna("Unknown") if company_col else "Unknown"
    feat_df["_equipment_type"] = df["equipment_type_raw"]
    feat_df["_country"]        = df["country_raw"]
    feat_df["_equipment_age"]  = df["equipment_age"]

    meta = {
        "feature_columns":    FEATURE_COLS,
        "le_equipment_type":  le_eq,
        "le_country":         le_country,
        "equipment_type_raw_col": eq_col,
        "country_raw_col":    country_col,
        "company_col":        company_col,
    }

    return feat_df, meta
