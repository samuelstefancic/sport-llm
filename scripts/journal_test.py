"""Outils communs des contrôles HTTP du journal dans un schéma PostgreSQL jetable."""

from contextlib import contextmanager
from http.client import HTTPConnection
import json
from pathlib import Path
import subprocess
import tempfile
from urllib.parse import quote
from uuid import uuid4

import psycopg

from verify_t04 import HOST, JAR, ROOT, local_ports, running, uvicorn
from verify_t05 import SOURCE, run_cli, test_schema


def build_jar():
    subprocess.run(["mvn", "-o", "-q", "-f", "java/pom.xml", "package"], cwd=ROOT, check=True)


@contextmanager
def journal_db():
    with test_schema() as dsn:
        run_cli(dsn, SOURCE, "--init-schema")
        with psycopg.connect(dsn, autocommit=True) as db:
            db.execute((ROOT / "java/src/main/resources/journal.sql").read_text(), prepare=False)
            yield dsn, db


def java_env(db):
    info = db.info
    if info.host.startswith("/"):
        raise ValueError("Pour JDBC, utiliser le port TCP local de la base d’essai (PGHOST=127.0.0.1).")
    schema = db.execute("SELECT current_schema()").fetchone()[0]
    host = f"[{info.host}]" if ":" in info.host else info.host
    jdbc = f"jdbc:postgresql://{host}:{info.port}/{quote(info.dbname, safe='')}?currentSchema={quote(schema)}"
    return {"JOURNAL_JDBC_URL": jdbc, "JOURNAL_DB_USER": info.user, "JOURNAL_DB_PASSWORD": info.password or ""}


@contextmanager
def java_service(db):
    java_port, python_port = local_ports()
    with tempfile.TemporaryDirectory(prefix="llmsport-journal-") as temporary:
        logs = Path(temporary)
        with running(["java", "-jar", str(JAR)], java_port, logs / "java.log", **java_env(db),
                     SERVER_ADDRESS=HOST, SERVER_PORT=str(java_port),
                     PYTHON_BASE_URL=f"http://{HOST}:{python_port}"):
            yield java_port, python_port, logs


def request(port, method, path, body=None, *, headers=None, expected=200):
    correlation = str(uuid4())
    headers = {"Content-Type": "application/json", "X-Correlation-ID": correlation, **(headers or {})}
    connection = HTTPConnection(HOST, port, timeout=12)
    try:
        connection.request(method, path, json.dumps(body) if body is not None else None, headers)
        reply = connection.getresponse()
        raw = reply.read()
        assert reply.status == expected, (method, path, reply.status, raw[:600])
        assert reply.getheader("X-Correlation-ID") == headers["X-Correlation-ID"]
        return json.loads(raw) if raw else None
    finally:
        connection.close()


def persisted(db, kind, entry_id, revision):
    rows = db.execute("""SELECT payload FROM journal_result WHERE entry_kind=%s
                         AND entry_id=%s AND entry_revision=%s""", (kind, entry_id, revision)).fetchall()
    assert len(rows) == 1, (kind, entry_id, revision, len(rows))
    return rows[0][0]
