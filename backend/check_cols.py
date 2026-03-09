import duckdb
conn = duckdb.connect(r"data\sales_app.db", read_only=True)
cols = conn.execute("DESCRIBE bcg_installed_base").df()["column_name"].tolist()
print("Matching cols:", [c for c in cols if "status" in c.lower() or "oper" in c.lower() or "state" in c.lower()])
