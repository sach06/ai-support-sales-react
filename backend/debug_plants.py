"""Debug script to find the 500 error in the plants endpoint."""
import sys
sys.path.insert(0, '.')
from app.services.data_service import data_service
import json
import numpy as np

print("Getting plant data...")
df = data_service.get_detailed_plant_data(region='Europe')
print(f"Shape: {df.shape}")
print(f"\nColumn types:")
for col in df.columns:
    print(f"  {col}: {df[col].dtype}")

# Check for inf values
df_filled = df.fillna("")
for col in df_filled.columns:
    try:
        if df_filled[col].dtype in ['float64', 'float32', 'int64', 'int32']:
            inf_count = np.isinf(df_filled[col]).sum()
            if inf_count > 0:
                print(f"  *** INF values in column '{col}': {inf_count}")
    except:
        pass

# Try serializing
print("\nTrying JSON serialization...")
try:
    records = df_filled.to_dict(orient="records")
    json_str = json.dumps(records[:2], default=str)
    print(f"SUCCESS: First 2 records serialized OK ({len(json_str)} chars)")
except Exception as e:
    print(f"SERIALIZATION ERROR: {e}")

# Try with the actual FastAPI/Starlette JSON encoder
try:
    records = df_filled.to_dict(orient="records")
    # Check for problematic values
    for i, rec in enumerate(records[:5]):
        for k, v in rec.items():
            try:
                json.dumps(v)
            except (TypeError, ValueError) as e:
                print(f"  Row {i}, Col '{k}': value={type(v).__name__}({repr(v)[:80]}) -> {e}")
except Exception as e:
    print(f"Checking error: {e}")

# Try full serialization
try:
    records = df_filled.to_dict(orient="records")
    result = {"plants": records, "total": len(records)}
    json_str = json.dumps(result, default=str)
    print(f"\nFull JSON: {len(json_str)} chars - OK!")
except Exception as e:
    print(f"\nFull JSON ERROR: {e}")
    # Find the problematic record
    for i, rec in enumerate(records):
        try:
            json.dumps(rec, default=str)
        except Exception as e2:
            print(f"  Failed at row {i}: {e2}")
            break
