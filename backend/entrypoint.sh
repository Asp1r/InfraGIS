#!/usr/bin/env sh
set -e

echo "Waiting for database..."
python - <<'PY'
import os
import time
from sqlalchemy import create_engine, text

database_url = os.environ["DATABASE_URL"]
engine = create_engine(database_url, pool_pre_ping=True)

for attempt in range(60):
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        print("Database is ready")
        break
    except Exception as exc:  # pragma: no cover
        print(f"Database is not ready yet ({attempt + 1}/60): {exc}")
        time.sleep(2)
else:
    raise RuntimeError("Database did not become ready in time")
PY

echo "Applying migrations..."
alembic upgrade head

echo "Starting API..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
