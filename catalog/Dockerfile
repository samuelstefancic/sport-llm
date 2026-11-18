FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN python -m pip install --no-cache-dir -r requirements.txt
COPY import_catalog.py schema.sql ./
CMD ["sh", "-ec", "PGPASSWORD=\"$(cat /run/secrets/db_password)\" exec python -B import_catalog.py --init-schema /fixtures/catalog.json"]
