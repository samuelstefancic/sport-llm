"""Exerce le CLI T05 dans un schéma PostgreSQL neuf, sur la base locale configurée."""

from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from uuid import uuid4

import psycopg
from psycopg import sql
from psycopg.conninfo import make_conninfo


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data/dev/catalog.json"
CLI = [sys.executable, "-B", str(ROOT / "catalog/import_catalog.py")]


@contextmanager
def test_schema():
    base = os.environ.get("DATABASE_URL", "")
    schema = "t05_test_" + uuid4().hex
    with psycopg.connect(base, autocommit=True) as admin:
        admin.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
        try:
            yield make_conninfo(base, options=f"-c search_path={schema}")
        finally:
            admin.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema)))


def run_cli(dsn, source, *args, expected="activated"):
    result = subprocess.run([*CLI, *args, str(source)], capture_output=True, text=True,
                            env={**os.environ, "DATABASE_URL": dsn}, timeout=20)
    if expected is None:
        assert result.returncode != 0, "L'import aurait dû être refusé"
    else:
        assert result.returncode == 0, result.stderr
        assert result.stdout.split()[0] == expected, result.stdout
    return result


def counts(db):
    return db.execute("""SELECT (SELECT count(*) FROM catalog_version),
                                (SELECT count(*) FROM catalog_food),
                                (SELECT count(*) FROM catalog_nutrient),
                                (SELECT count(*) FROM catalog_active)""").fetchone()


def active(db):
    return db.execute("SELECT version FROM catalog_active WHERE catalog_id='DEMO-FOOD'").fetchone()[0]


def interrupt_activation(db, dsn, path):
    # Le trigger et son verrou n’existent que dans le schéma jetable. Le CLI reste celui de l'import.
    db.execute("""CREATE FUNCTION pause_activation() RETURNS trigger LANGUAGE plpgsql AS $$
                  BEGIN PERFORM pg_advisory_xact_lock(98981, 5); RETURN NEW; END $$""")
    db.execute("""CREATE TRIGGER pause_activation BEFORE INSERT OR UPDATE ON catalog_active
                  FOR EACH ROW EXECUTE FUNCTION pause_activation()""")
    db.execute("SELECT pg_advisory_lock(98981, 5)")
    proc = subprocess.Popen([*CLI, str(path)], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            env={**os.environ, "DATABASE_URL": make_conninfo(dsn, application_name="t05_interrupt")})
    try:
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            blocked = db.execute("""SELECT pid FROM pg_stat_activity WHERE application_name='t05_interrupt'
                                    AND pg_backend_pid() = ANY(pg_blocking_pids(pid))""").fetchone()
            if blocked:
                break
            if proc.poll() is not None:
                raise AssertionError("L’import s’est terminé avant l’activation")
            time.sleep(0.03)
        else:
            raise TimeoutError("Le second import n’a pas atteint le point d’activation")
        assert active(db) == "0.2.0" and counts(db) == (1, 6, 60, 1)
        assert db.execute("SELECT pg_terminate_backend(%s)", blocked).fetchone()[0]
        proc.communicate(timeout=10)
        assert proc.returncode != 0
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait()
        db.execute("SELECT pg_advisory_unlock(98981, 5)")
        db.execute("DROP TRIGGER pause_activation ON catalog_active")
    assert active(db) == "0.2.0" and counts(db) == (1, 6, 60, 1)


def verify(dsn, directory):
    run_cli(dsn, SOURCE, "--init-schema")
    with psycopg.connect(dsn, autocommit=True) as db:
        assert active(db) == "0.2.0" and counts(db) == (1, 6, 60, 1)
        expected_hash = hashlib.sha256(SOURCE.read_bytes()).hexdigest()
        assert db.execute("SELECT source_sha256, document->>'fictitious' FROM catalog_version").fetchone() == (
            expected_hash, "true")
        rows = db.execute("""SELECT n.food_id,n.value,n.availability,n.unit,f.basis_value,f.basis_unit,f.state
                             FROM catalog_nutrient n JOIN catalog_food f USING(catalog_id,version,food_id)
                             WHERE nutrient_id='salt' AND food_id IN ('D01','D02','D03') ORDER BY food_id""").fetchall()
        assert rows == [("D01", 0, "known", "g", 100, "g", "cooked"),
                        ("D02", None, "absent", "g", 100, "g", "cooked"),
                        ("D03", None, "absent", "g", 100, "g", "cooked")]
        print("PASS activation et provenance ; sel D01 = 0, D02/D03 = NULL ; base 100 g")
        run_cli(dsn, SOURCE, expected="already_imported")
        assert counts(db) == (1, 6, 60, 1)
        print("PASS rejeu : 1 version, 6 aliments, 60 apports, 1 pointeur")

        doc = json.loads(SOURCE.read_bytes())
        path = directory / "variant.json"
        doc["items"][0]["label"] = "riz fictif modifié"
        path.write_text(json.dumps(doc))
        assert "empreinte" in run_cli(dsn, path, expected=None).stderr
        assert counts(db) == (1, 6, 60, 1) and active(db) == "0.2.0"
        print("PASS même version, contenu différent : conflit, version active préservée")

        doc["version"] = "0.2.1-test"
        del doc["items"][0]["nutrients"]["salt"]
        doc["items"][1]["nutrients"]["salt"]["value"] = 0
        path.write_text(json.dumps(doc))
        assert "disponibilité" in run_cli(dsn, path, expected=None).stderr
        assert counts(db) == (1, 6, 60, 1) and active(db) == "0.2.0"
        doc["items"][1]["nutrients"]["salt"]["value"] = None
        path.write_text(json.dumps(doc))
        print("PASS donnée invalide : disponibilité absente avec valeur 0 rejetée")
        interrupt_activation(db, dsn, path)
        print("PASS interruption PostgreSQL avant activation : 0.2.0 toujours visible, aucune ligne partielle")
        run_cli(dsn, path)
        run_cli(dsn, SOURCE, expected="already_imported")
        assert active(db) == doc["version"] and counts(db) == (2, 12, 120, 1)
        assert db.execute("""SELECT value, availability FROM catalog_nutrient WHERE version=%s
                             AND food_id='D01' AND nutrient_id='salt'""", (doc["version"],)).fetchone() == (None, "absent")
        print("PASS reprise, clé omise conservée inconnue, rejeu historique sans réactivation")


if __name__ == "__main__":
    if not __debug__:
        sys.exit("Relancer sans optimisation pour activer les assertions")
    with test_schema() as dsn, tempfile.TemporaryDirectory() as temporary:
        verify(dsn, Path(temporary))
