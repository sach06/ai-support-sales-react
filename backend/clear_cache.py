import duckdb
conn = duckdb.connect(r"data\sales_app.db")
conn.execute("DROP TABLE IF EXISTS _meta;")
conn.execute("DROP TABLE IF EXISTS company_mappings;")
print("Cache cleared!")
conn.close()
