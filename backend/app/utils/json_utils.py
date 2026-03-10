import math
import numpy as np
import pandas as pd

def json_safe_sanitize(obj):
    """
    Recursively sanitize objects to be JSON-compliant.
    Converts:
    - NaN, Inf, -Inf -> None
    - numpy types -> python native types
    - numpy.ndarray (from DuckDB LIST columns) -> python list (recursed)
    - pandas Timestamp -> ISO string
    - bytes -> None (non-serializable)
    - DataFrames -> list of dicts (already sanitized)
    """
    # --- numpy array: DuckDB LIST columns come back as ndarray ---
    if isinstance(obj, np.ndarray):
        return [json_safe_sanitize(v) for v in obj.tolist()]
    # --- dict ---
    elif isinstance(obj, dict):
        return {k: json_safe_sanitize(v) for k, v in obj.items()}
    # --- list / tuple ---
    elif isinstance(obj, (list, tuple)):
        return [json_safe_sanitize(v) for v in obj]
    # --- plain float ---
    elif isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
        return obj
    # --- numpy scalars ---
    elif isinstance(obj, np.generic):
        if isinstance(obj, (np.floating, np.float64, np.float32, np.float16)):
            val = float(obj)
            if math.isnan(val) or math.isinf(val):
                return None
            return val
        elif isinstance(obj, np.integer):
            return int(obj)
        elif isinstance(obj, np.bool_):
            return bool(obj)
        return obj.item()  # fallback for any other numpy scalar
    # --- pandas DataFrame: convert to list of records then recurse ---
    elif isinstance(obj, pd.DataFrame):
        if obj.empty:
            return []
        return json_safe_sanitize(obj.to_dict(orient="records"))
    # --- pandas Series: convert to list ---
    elif isinstance(obj, pd.Series):
        return json_safe_sanitize(obj.tolist())
    # --- pandas Timestamp ---
    elif isinstance(obj, (pd.Timestamp,)):
        try:
            return None if pd.isnull(obj) else obj.isoformat()
        except Exception:
            return None
    # --- pandas NA / NaT ---
    elif obj is pd.NaT or obj is pd.NA:
        return None
    # --- bytes: skip ---
    elif isinstance(obj, (bytes, bytearray)):
        return None
    return obj

def df_to_json_safe(df):
    """Convert a DataFrame to a JSON-safe list of dicts."""
    if df is None or df.empty:
        return []
    records = df.to_dict(orient="records")
    return json_safe_sanitize(records)
