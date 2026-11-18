"""T10 : deux mesures locales, versionnées, des vrais services P1."""

import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import datetime, timezone
from hashlib import sha256
from http.client import HTTPConnection, HTTPException
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib.metadata import version
from io import BytesIO
import json
import os
from pathlib import Path
import platform
import re
import signal
import subprocess
import sys
from tempfile import TemporaryDirectory
from threading import Event, Thread
from time import perf_counter
from urllib.parse import quote
from uuid import uuid4
from zipfile import ZipFile

from t10_score import metrics, score
from verify_t04 import HOST, ROOT, local_ports, running


PROTOCOL = "documentation/p2/baseline-protocol.json"
FILES = {"data/dev/cases.json", "data/dev/oracles.md", "data/dev/catalog.json", "contracts/analysis.schema.json"}
TABLES = {"journal_entry": "entry_id", "journal_declaration": "entry_id, entry_revision",
          "journal_result": "entry_id, entry_revision", "journal_idempotency": "request_key"}
ROUTES = {"meal", "meal_correction", "late_meal", "reject_meal", "workout", "workout_correction", "reject_workout",
          "excluded"}
RULES_VERSION = "1.0.0"


class ProtocolError(ValueError):
    pass


def require(condition, detail):
    if not condition:
        raise ProtocolError(detail)


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT)


def identity(commit):
    require(re.fullmatch(r"[0-9a-f]{40}", commit), "Fournir un SHA Git complet de 40 caractères.")
    require(git("rev-parse", "HEAD").decode().strip() == commit, "Le SHA demandé diffère de HEAD.")
    require(not git("status", "--porcelain=v1", "--untracked-files=all"), "Le checkout doit être propre.")


def read(path):
    return json.loads(path.read_bytes())


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n",
                    encoding="utf-8")


def frozen(root):
    manifest = read(root / PROTOCOL)
    require(manifest["protocol_version"] == RULES_VERSION, "Version du protocole inattendue.")
    require(set(manifest["hashes"]) == FILES, "Périmètre des empreintes inattendu.")
    for path, digest in manifest["hashes"].items():
        require(sha256((root / path).read_bytes()).hexdigest() == digest, f"Empreinte différente : {path}")
    corpus, catalog = (read(root / "data/dev" / file) for file in ("cases.json", "catalog.json"))
    require((corpus["corpus_id"], corpus["version"], corpus["catalog_version"], corpus["fictitious"]) == (
        manifest["corpus_id"], manifest["corpus_version"], manifest["catalog_version"], True
    ), "Identité du corpus invalide.")
    require((catalog["catalog_id"], catalog["version"], catalog["fictitious"]) == (
        manifest["catalog_id"], manifest["catalog_version"], True
    ), "Identité du catalogue invalide.")
    cases = corpus["cases"]
    planned = manifest["cases"]
    require(len(cases) == len(planned) == len({c["id"] for c in cases}) == 30, "Population du corpus invalide.")
    require([(c["id"], c["group_id"]) for c in cases] == [(key, group) for key, group, _ in planned],
            "IDs ou groupes différents du manifeste.")
    require(all(route in ROUTES for _, _, route in planned), "Disposition inconnue.")
    require(Counter(c["split"] for c in cases) == manifest["partitions"] == {"development": 30},
            "Partition invalide.")
    require(all(c["fictitious"] is True for c in cases), "Le corpus doit être fictif.")
    require(Counter(c["category"] for c in cases) == {"food": 15, "sport": 10, "mixed_or_ambiguous": 5},
            "Catégories du corpus invalides.")
    for name, count in manifest["annotation_counts"].items():
        require(sum(c["manual_checks"][name] for c in cases) == count == 10, "Décompte d'oracles invalide.")
    excluded = {key for key, _, route in planned if route == "excluded"}
    require(excluded == set(manifest["exclusions"]) == {f"M{i:02}" for i in range(1, 6)},
            "Les cinq exclusions doivent avoir un motif figé.")
    return manifest, list(zip(cases, (route for _, _, route in planned))), catalog


def milliseconds(start):
    return (perf_counter() - start) * 1000


@contextmanager
def proposal_relay(peer_port):
    """Relais sans modification du corps, permettant de bloquer un retour tardif réel."""
    replies = {}
    gate = {"correlation": None, "arrived": Event(), "release": Event(), "released_while_waiting": False}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            if self.path != "/internal/proposals":
                self.send_error(404)
                return
            correlation = self.headers["X-Correlation-ID"]
            raw = self.rfile.read(int(self.headers["Content-Length"]))
            upstream = HTTPConnection(HOST, peer_port, timeout=2)
            try:
                upstream.request("POST", self.path, raw, {"Content-Type": "application/json",
                                                          "X-Correlation-ID": correlation})
                response = upstream.getresponse()
                status, payload = response.status, response.read()
                headers = {name: response.getheader(name) for name in ("Content-Type", "X-Correlation-ID")}
            finally:
                upstream.close()
            try:
                parsed = json.loads(payload)
            except (ValueError, UnicodeError):
                parsed = None
            replies[correlation] = {"status": status, "body": parsed}
            if correlation == gate["correlation"]:
                gate["arrived"].set()
                gate["released_while_waiting"] = gate["release"].wait(2)
            try:
                self.send_response(status)
                for name, value in headers.items():
                    if value is not None:
                        self.send_header(name, value)
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
            except (BrokenPipeError, ConnectionResetError):
                # Java peut avoir atteint son délai avant la libération de la réponse.
                pass

    with ThreadingHTTPServer((HOST, 0), Handler) as server:
        worker = Thread(target=server.serve_forever, daemon=True)
        worker.start()
        try:
            yield server.server_port, replies, gate
        finally:
            gate["release"].set()
            server.shutdown()
            worker.join()


class CaseTrace:
    def __init__(self, port, replies, domain, entry):
        self.port, self.replies, self.domain, self.entry = port, replies, domain, entry
        self.exchanges = {}
        self.state = {}

    def call(self, label, method, path, body=None, *, correlation=None):
        correlation = correlation or str(uuid4())
        call = {"method": method, "path": path, "request": body, "correlation_id": correlation}
        self.exchanges[label] = call
        conn = HTTPConnection(HOST, self.port, timeout=8)
        start = perf_counter()
        try:
            conn.request(method, path, json.dumps(body) if body is not None else None,
                         {"Content-Type": "application/json", "X-Correlation-ID": correlation})
            response = conn.getresponse()
            payload = response.read()
            call.update(status=response.status, duration_ms=milliseconds(start))
            if response.getheader("X-Correlation-ID") != correlation:
                call["transport_error"] = "correlation_mismatch"
            call["body"] = json.loads(payload) if payload else None
        except (OSError, HTTPException, UnicodeError, ValueError) as exc:
            call.setdefault("duration_ms", milliseconds(start))
            call["transport_error"] = type(exc).__name__
        finally:
            conn.close()
            call["peer"] = self.replies.pop(correlation, None)
        return call

    def post(self, label, body, **options):
        return self.call(label, "POST", "/" + self.domain, body, **options)

    def fetch(self, label, suffix=""):
        return self.call(label, "GET", f"/{self.domain}/{self.entry}{suffix}")

    def declare(self, label, body):
        revision = body["entry_revision"]
        fields = {key: value for key, value in body.items() if key not in {"entry_revision", "entry_id"}}
        return self.call(label, "PUT", f"/{self.domain}/{self.entry}/revisions/{revision}/declaration", fields)


def declaration(trace, revision, text, **fields):
    return {"entry_id": trace.entry, "entry_revision": revision, "text": text, **fields}


def snapshot(db):
    # xmin distingue une mise à jour avec un contenu inchangé. Il reste interne à la comparaison.
    return {table: db.execute(f"SELECT xmin::text, * FROM {table} ORDER BY {order}").fetchall()
            for table, order in TABLES.items()}


def energy(body):
    rows = (body or {}).get("report", {}).get("nutrients", [])
    return next((row for row in rows if row["id"] == "energy"), {})


def side_effects(db, trace, final, revision):
    entry = db.execute("SELECT current_revision FROM journal_entry WHERE entry_id=%s", (trace.entry,)).fetchone()
    row = db.execute("SELECT payload FROM journal_result WHERE entry_id=%s AND entry_revision=%s",
                     (trace.entry, revision)).fetchone()
    current = trace.fetch("current")
    trace.state.update(
        current_revision=entry[0] if entry else None,
        saved_matches=row is not None and final.get("status") == current.get("status") == 200
        and row[0] == current.get("body") == final.get("body"),
    )


def meal_text(mentions):
    labels = {"D01": "riz cuit", "D02": "poulet cuit"}
    return ", ".join(f"{m['quantity']['value']} {m['quantity']['unit']} de {labels[m['food_id']]}" for m in mentions)


def run_correction(db, trace, case, route, selected):
    state = case["state"]
    if route == "meal_correction":
        old = meal_text(state["previous_food_mentions"])
        changes = {"corrected_mentions": ["m1"]}
    else:
        quantity = state["previous_duration"]
        old = f"Vélo : {quantity['value']} {quantity['unit']}."
        changes = {}
    initial = declaration(trace, state["previous_revision"], old, **selected)
    previous = trace.post("initial", initial)
    original = trace.fetch("initial_declaration", "/revisions/1/declaration")
    current = declaration(trace, state["current_revision"], case["input"], **selected, **changes)
    final = trace.post("final", current)
    side_effects(db, trace, final, state["current_revision"])
    previous_after = trace.fetch("previous_result_after", "/revisions/1")
    original_after = trace.fetch("previous_declaration_after", "/revisions/1/declaration")
    old_energy = energy(previous.get("body"))
    trace.state.update(
        history_preserved=previous.get("status") == original.get("status") == previous_after.get("status")
        == original_after.get("status") == 200
        and previous.get("body") == previous_after.get("body") and original.get("body") == original_after.get("body")
        and (original.get("body") or {}).get("text") == old,
        previous_energy={"value": old_energy.get("value"), "unit": old_energy.get("unit"),
                         "meal_revision": (previous.get("body") or {}).get("report", {}).get("meal_revision")},
    )
    if route == "workout_correction":
        duration = (previous.get("body") or {}).get("summary", {}).get("duration", {})
        trace.state["history_preserved"] &= (
            duration.get("value"), duration.get("unit")) == (quantity["value"], quantity["unit"])


def run_late(db, trace, case, gate, selected):
    state = case["state"]
    old = declaration(trace, state["analyzed_revision"], meal_text(state["proposal_food_mentions"]), **selected)
    current = declaration(trace, state["current_revision"], meal_text(state["current_food_mentions"]),
                          **selected, corrected_mentions=["m1"])
    trace.declare("initial_declaration", old)
    correlation = str(uuid4())
    gate["correlation"] = correlation
    with ThreadPoolExecutor(max_workers=1) as pool:
        late = pool.submit(trace.post, "final", old, correlation=correlation)
        try:
            reached = gate["arrived"].wait(2)
            correction = trace.post("corrected", current)
            before = snapshot(db)
            corrected_decl = trace.fetch("corrected_declaration", "/revisions/2/declaration")
            committed_before_release = correction.get("status") == 200 and not late.done()
        finally:
            gate["release"].set()
        late.result()
    after = snapshot(db)
    readback = trace.fetch("current")
    reread_decl = trace.fetch("current_declaration", "/revisions/2/declaration")
    trace.state.update(
        real_proposal_held_until_r2=reached and committed_before_release and gate["released_while_waiting"],
        sql_unchanged=after == before,
        write_count=sum(len(set(map(repr, before[table])) ^ set(map(repr, after[table]))) for table in TABLES),
        current_food_mentions_unchanged=corrected_decl.get("status") == reread_decl.get("status") == 200
        and corrected_decl.get("body") == reread_decl.get("body")
        and (reread_decl.get("body") or {}).get("text") == current["text"],
        current_report_unchanged=correction.get("status") == readback.get("status") == 200
        and correction.get("body") == readback.get("body"),
        current_energy=energy(readback.get("body")),
    )


def measure_case(db, port, replies, gate, case, route, catalog, validate, reason=None):
    row = {"id": case["id"], "group_id": case["group_id"], "category": case["category"], "split": case["split"],
           "input": case["input"], "expected": case["expected"], "manual_checks": case["manual_checks"],
           "expects_clarification": "clarification" in case["expected"], "disposition": route, "fictitious": True}
    if route == "excluded":
        return {**row, "reason": reason, "duration_ms": None, "score": None}
    domain = "workouts" if "workout" in route else "meals"
    trace = CaseTrace(port, replies, domain, "T10-" + case["id"])
    selection = {"selected_nutrients": case["selected_nutrients"]} if "selected_nutrients" in case else {}
    started = perf_counter()
    if route.endswith("_correction"):
        run_correction(db, trace, case, route, selection)
    elif route == "late_meal":
        run_late(db, trace, case, gate, selection)
    else:
        rejected = route.startswith("reject_")
        if rejected:
            before = snapshot(db)
        final = trace.post("final", declaration(trace, 1, case["input"], **selection))
        if rejected:
            after = snapshot(db)
            trace.state.update(sql_unchanged=after == before, created=any(
                trace.entry in record for records in after.values() for record in records
            ))
        else:
            side_effects(db, trace, final, 1)
    observed = {"exchanges": trace.exchanges, "state": trace.state, "duration_ms": milliseconds(started)}
    return {**row, **observed, "score": score(case, route, catalog, validate, observed)}


def local_environment():
    require("DATABASE_URL" not in os.environ and "PGSERVICE" not in os.environ and "PGHOSTADDR" not in os.environ,
            "Utiliser PGHOST/PGPORT/PGDATABASE/PGUSER et une instance PostgreSQL locale dédiée.")
    require(os.environ.get("PGHOST", HOST) == HOST, "PGHOST doit être 127.0.0.1.")
    for name in ("PGPORT", "PGDATABASE", "PGUSER"):
        require(bool(os.environ.get(name)), f"Renseigner {name} pour PostgreSQL local.")
    for name in list(os.environ):
        if name.startswith(("SPRING_", "SERVER_", "JOURNAL_", "MLFLOW_")) or name in {
            "JAVA_TOOL_OPTIONS", "JDK_JAVA_OPTIONS", "_JAVA_OPTIONS", "MAVEN_OPTS", "MAVEN_ARGS",
            "PYTHONPATH", "PYTHONHOME", "UVICORN_HOST", "UVICORN_PORT",
        }:
            del os.environ[name]
    os.environ["MLFLOW_DISABLE_TELEMETRY"] = "true"
    os.environ["MLFLOW_ENABLE_SYSTEM_METRICS_LOGGING"] = "false"


@contextmanager
def isolated_db(source):
    import psycopg
    from psycopg import sql
    from psycopg.conninfo import make_conninfo

    base = dict(host=HOST, hostaddr=HOST, port=os.environ["PGPORT"], dbname=os.environ["PGDATABASE"],
                user=os.environ["PGUSER"], sslmode="disable", connect_timeout=3, options="")
    schema = "t10_eval_" + uuid4().hex
    with psycopg.connect(**base, autocommit=True) as admin:
        admin.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
        try:
            settings = {**base, "options": "-c search_path=" + schema}
            dsn = make_conninfo(**settings)
            subprocess.run([sys.executable, "-B", str(source / "catalog/import_catalog.py"), "--init-schema",
                            str(source / "data/dev/catalog.json")], cwd=source, check=True, timeout=30,
                           env={**os.environ, "DATABASE_URL": dsn}, stdout=subprocess.DEVNULL)
            with psycopg.connect(**settings, autocommit=True) as db:
                db.execute((source / "java/src/main/resources/journal.sql").read_text(encoding="utf-8"), prepare=False)
                yield db, schema
        finally:
            admin.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema)))


@contextmanager
def services(source, jar, db, schema, logs):
    java_port, python_port = local_ports()
    info = db.info
    jdbc = f"jdbc:postgresql://{HOST}:{info.port}/{quote(info.dbname, safe='')}?currentSchema={schema}&sslmode=disable"
    uvicorn = [sys.executable, "-B", "-m", "uvicorn", "app:app", "--app-dir", str(source / "python"),
               "--host", HOST, "--port", str(python_port), "--no-access-log"]
    with running(uvicorn, python_port, logs / "python.log"), proposal_relay(python_port) as (relay, replies, gate):
        with running(["java", "-jar", str(jar)], java_port, logs / "java.log", SERVER_ADDRESS=HOST,
                     SERVER_PORT=str(java_port), PYTHON_BASE_URL=f"http://{HOST}:{relay}",
                     JOURNAL_JDBC_URL=jdbc, JOURNAL_DB_USER=info.user, JOURNAL_DB_PASSWORD=info.password or ""):
            yield java_port, replies, gate


def command_version(*args):
    return subprocess.check_output(args, cwd=ROOT, stderr=subprocess.STDOUT, text=True).splitlines()[0]


def semantic(value):
    ignored = {"duration_ms", "correlation_id", "proposal_id", "timestamp"}
    if isinstance(value, dict):
        return {key: semantic(item) for key, item in value.items() if key not in ignored}
    if isinstance(value, list):
        return [semantic(item) for item in value]
    return value


def runtime_manifest(commit, purpose, protocol, jar):
    return {
        "commit": commit, "purpose": purpose, "protocol": protocol, "seed": None, "fictitious": True,
        "baseline": "P1 deterministic", "model": None, "catalog_data": "development-only",
        "java": command_version("java", "-version"), "maven": command_version("mvn", "-v"),
        "jar_sha256": sha256(jar.read_bytes()).hexdigest(),
        "python": platform.python_version(), "host": {"system": platform.system(), "release": platform.release(),
                                                       "architecture": platform.machine()},
        "dependencies": {name: version(name) for name in (
            "fastapi", "pydantic", "uvicorn", "psycopg", "jsonschema", "mlflow-skinny", "SQLAlchemy", "alembic"
        )},
    }


def mlflow_session(output):
    import mlflow
    from mlflow import MlflowClient

    # Le backend SQL et le répertoire d'artefacts sont explicites. Le cwd borne aussi les défauts MLflow.
    os.chdir(output)
    uri = "sqlite:///" + str(output / "tracking.sqlite")
    mlflow.set_tracking_uri(uri)
    mlflow.set_registry_uri(uri)
    client = MlflowClient(tracking_uri=uri, registry_uri=uri)
    experiment = client.create_experiment("llmsport-t10", artifact_location=(output / "artifacts").as_uri())
    return client, experiment


def begin_run(client, experiment, folder, report):
    from mlflow.entities import Param

    run_id = client.create_run(experiment, run_name=folder.name).info.run_id
    report["mlflow_run_id"] = run_id
    write(folder / "manifest.json", report)
    client.log_batch(run_id, params=[
        Param("commit", report["commit"]), Param("purpose", report["purpose"]),
        Param("protocol_version", report["protocol"]["protocol_version"]),
        Param("corpus_version", report["protocol"]["corpus_version"]),
        Param("catalog_version", report["protocol"]["catalog_version"]),
        Param("baseline", report["baseline"]),
    ])
    return run_id


def log_scores(client, run_id, scores):
    from mlflow.entities import Metric

    when = int(datetime.now(timezone.utc).timestamp() * 1000)

    def numeric_metrics(values, prefix=""):
        for key, value in values.items():
            name = prefix + key
            if type(value) in (int, float):
                yield Metric(name, float(value), when, 0)
            elif isinstance(value, dict):
                yield from numeric_metrics(value, name + ".")

    client.log_batch(run_id, metrics=list(numeric_metrics(scores)))


def readback(client, run_id, folder, scores):
    persisted = client.get_run(run_id)
    files = sorted(item.path for item in client.list_artifacts(run_id))
    require(persisted.info.status == "FINISHED" and files == ["cases.json", "manifest.json", "metrics.json"],
            "Run ou artefacts MLflow incomplets.")
    require(persisted.data.metrics["executed_cases"] == scores["executed_cases"], "Métrique MLflow divergente.")
    with TemporaryDirectory(prefix="llmsport-t10-readback-") as directory:
        for name in files:
            artifact = Path(client.download_artifacts(run_id, name, directory))
            require(sha256(artifact.read_bytes()).digest() == sha256((folder / name).read_bytes()).digest(),
                    f"Artefact MLflow divergent : {name}")
    return {"run_id": run_id, "artifact_uri": persisted.info.artifact_uri, "files": files,
            "status": persisted.info.status, "executed_cases": persisted.data.metrics["executed_cases"]}


def evaluate(args, source, scratch, output, protocol, design, catalog):
    from jsonschema import Draft202012Validator

    schema = read(source / "contracts/analysis.schema.json")
    validators = {
        branch: Draft202012Validator({**schema, "oneOf": [{"$ref": "#/$defs/" + branch}]})
        for branch in ("python_proposal", "java_nutrition_report", "java_analysis_rejection")
    }
    validate = lambda body, branch: validators[branch].is_valid(body)
    subprocess.run(["mvn", "-o", "-q", "-f", "java/pom.xml", "package"], cwd=source, timeout=300, check=True)
    jar = source / "java/target/llmsport-t04.jar"
    common = runtime_manifest(args.commit, args.purpose, protocol, jar)
    client, experiment = mlflow_session(output)
    pair, receipts = [], []
    for index in (1, 2):
        logs = scratch / f"logs-{index}"
        logs.mkdir()
        folder = output / f"run-{index}"
        folder.mkdir()
        started = datetime.now(timezone.utc).isoformat()
        run_start = perf_counter()
        report = {**common, "repetition": index, "started_at_utc": started}
        run_id = begin_run(client, experiment, folder, report)
        rows = []
        try:
            with isolated_db(source) as (db, db_schema):
                catalog_info = db.execute("""SELECT catalog_id, version, source_sha256
                    FROM catalog_active JOIN catalog_version USING (catalog_id, version)""").fetchall()
                require(catalog_info == [(protocol["catalog_id"], protocol["catalog_version"],
                                          protocol["hashes"]["data/dev/catalog.json"])], "Le catalogue actif a dérivé.")
                report.update(postgresql=db.execute("SHOW server_version").fetchone()[0], catalog_active=catalog_info)
                with services(source, jar, db, db_schema, logs) as (port, replies, gate):
                    for case, route in design:
                        rows.append(measure_case(db, port, replies, gate, case, route, catalog, validate,
                                                 protocol["exclusions"].get(case["id"])))
            scores = metrics(rows)
            report["duration_ms"] = milliseconds(run_start)
            write(folder / "manifest.json", report)
            write(folder / "cases.json", rows)
            write(folder / "metrics.json", scores)
            identity(args.commit)
            log_scores(client, run_id, scores)
            client.log_artifacts(run_id, str(folder))
            client.set_terminated(run_id, status="FINISHED")
        except BaseException as exc:
            try:
                report.update(duration_ms=milliseconds(run_start), evaluation_error=type(exc).__name__,
                              recorded_rows=len(rows))
                write(folder / "manifest.json", report)
                write(folder / "cases.json", rows)
                client.log_artifacts(run_id, str(folder))
            finally:
                client.set_terminated(run_id, status="FAILED")
            raise
        receipts.append(readback(client, run_id, folder, scores))
        pair.append(semantic(rows))
    require(len(client.search_runs([experiment])) == 2, "Le store local doit contenir exactement deux runs.")
    write(output / "mlflow-readback.json", {"experiment_id": experiment, "runs": receipts})
    differences = [left["id"] for left, right in zip(*pair) if left != right]
    write(output / "reproducibility.json", {"commit": args.commit, "purpose": args.purpose,
                                            "run_ids": [r["run_id"] for r in receipts],
                                            "identical_semantics": not differences, "different_cases": differences})
    require(not differences, f"Divergence sémantique entre les runs : {', '.join(differences)}")
    print("Deux runs MLflow relus, résultats sémantiques identiques :", *(r["run_id"] for r in receipts), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--commit", required=True, help="SHA complet de HEAD, incluant protocole et instrumentation.")
    parser.add_argument("--output", type=Path, required=True, help="Répertoire local de résultats à créer.")
    parser.add_argument("--purpose", choices=("reference", "validation"), default="reference")
    args = parser.parse_args()
    identity(args.commit)
    frozen(ROOT)
    local_environment()
    output = args.output.resolve()
    require(not set(str(output)) & {"?", "#", "\n"}, "Chemin incompatible avec le backend SQLite.")
    with TemporaryDirectory(prefix="llmsport-t10-") as temp:
        scratch = Path(temp)
        source = scratch / "source"
        with ZipFile(BytesIO(git("archive", "--format=zip", args.commit))) as archive:
            archive.extractall(source)
        protocol, design, catalog = frozen(source)
        output.mkdir(mode=0o700)
        evaluate(args, source, scratch, output, protocol, design, catalog)


def terminate(signum, _):
    raise SystemExit(128 + signum)


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, terminate)
    try:
        main()
    except ProtocolError as exc:
        sys.exit(str(exc))
