import os
from dotenv import load_dotenv

load_dotenv()

dsn = os.environ.get("INVESTOR_ASSISTANT_DATABASE_URL")
print("DSN found:" , bool(dsn))
if dsn:
    print("host:", dsn.split("@")[-1])

import psycopg2
conn = psycopg2.connect(dsn, connect_timeout=5)
cur = conn.cursor()
cur.execute("SELECT COUNT(*) FROM market_snapshot")
print("rows in table:", cur.fetchone()[0])
conn.close()
print("connection OK")