import math
import numpy as np

def json_safe_sanitize(obj):
    """
    Recursively sanitize objects to be JSON-compliant.
    Converts:
    - NaN, Inf, -Inf -> None
    - numpy types -> python native types
    - DataFrames -> list of dicts (already sanitized)
    """
    if isinstance(obj, dict):
        return {k: json_safe_sanitize(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [json_safe_sanitize(v) for v in obj]
    elif isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
        return obj
    elif isinstance(obj, np.generic):
        if isinstance(obj, (np.floating, np.float64, np.float32)):
            if np.isnan(obj) or np.isinf(obj):
                return None
            return float(obj)
        elif isinstance(obj, np.integer):
            return int(obj)
        elif isinstance(obj, np.bool_):
            return bool(obj)
        return obj
    return obj

def df_to_json_safe(df):
    """Convert a DataFrame to a JSON-safe list of dicts."""
    if df is None or df.empty:
        return []
    records = df.to_dict(orient="records")
    return json_safe_sanitize(records)
