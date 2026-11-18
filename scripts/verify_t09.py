"""Vérifie l'intégration Compose, avec les régressions P0/T04–T08 si --all."""

import argparse
import hashlib
from http.client import HTTPConnection
import json
import os
from pathlib import Path
import secrets
import signal
import subprocess
import sys
import tempfile
import time
from uuid import uuid4

import psycopg

from journal_test import HOST, ROOT, request
from verify_t05 import SOURCE, counts
from verify_t06 import check_oracle
from verify_t07 import absent, body, known, saved, unresolved
from verify_t08 import revisions, snapshot


SUITES = ("p0", "t04", "t05", "t06", "t07", "t08")
CASES = {case["id"]: case["input"] for case in json.loads((ROOT / "data/dev/cases.json").read_text())["cases"]}
DOWN_TEXT = "100 g de riz cuit. Repère fictif T09-confidentiel-arrêt."
INVALID_TEXT = "100 g de riz cuit. Repère fictif T09-confidentiel-invalide."
REPLAY_KEY = "t09-replay-f02"


class Compose:
    def __init__(self, password_file, password):
        self.project = "llmsport-t09-" + uuid4().hex
        self.password = password
        self.env = {key: value for key, value in os.environ.items() if not key.startswith("COMPOSE_")}
        self.env["LLMSPORT_DB_SECRET"] = str(password_file)
        self.command = ["compose", "--env-file", "/dev/null", "--project-name", self.project,
                        "-f", "compose.yaml", "-f", "scripts/t09-db.compose.yaml"]

    def docker(self, *args, timeout=30):
        call = subprocess.run(["docker", *args], cwd=ROOT, env=self.env, capture_output=True,
                              text=True, timeout=timeout)
        if call.returncode:
            detail = self.without_sensitive(call.stderr.strip())
            raise RuntimeError(f"docker {args[0]} a quitté avec code {call.returncode}\n{detail[-2500:]}")
        return call.stdout.strip()

    def run(self, *args, timeout=30):
        return self.docker(*self.command, *args, timeout=timeout)

    def port(self, service, port):
        binding = self.run("port", service, str(port))
        host, sep, published = binding.partition(":")
        assert sep and host == HOST and published.isnumeric() and int(published) > 0, (service, binding)
        return int(published)

    def no_published_python_port(self):
        container = self.run("ps", "-q", "python")
        assert container
        network = json.loads(self.docker("inspect", "--format", "{{json .NetworkSettings}}", container))
        assert not any((network["Ports"] or {}).values()), "Le pair Python a un port publié"
        assert set(network["Networks"]) == {self.project + "_internal"}

    def logs(self, service):
        # Sans préfixe afin de contrôler le contenu réellement écrit par chaque service.
        return self.run("logs", "--no-color", "--no-log-prefix", service)

    def without_sensitive(self, data):
        for value in (self.password, REPLAY_KEY, DOWN_TEXT, INVALID_TEXT, *CASES.values(),
                      "T09-confidentiel-arrêt", "T09-confidentiel-invalide", "100 g de riz cuit",
                      "100 g de poulet cuit", "100 g de lentilles cuites", "3 séries", "10 répétitions",
                      "40 kg", "30 minutes"):
            for rendering in {value, json.dumps(value, ensure_ascii=True)[1:-1]}:
                data = data.replace(rendering, "[masqué]")
        return data

    def clean(self):
        self.run("down", "--timeout", "5", "--volumes", "--rmi", "local", timeout=45)
        label = f"label=com.docker.compose.project={self.project}"
        for resource in ("container", "network", "volume"):
            options = ["--all"] if resource == "container" else []
            assert not self.docker(resource, "ls", *options, "--filter", label, "--quiet"), (
                f"Ressource restante dans {self.project} ({resource})")


def java_ready(compose):
    port = compose.port("java", 8103)
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        connection = HTTPConnection(HOST, port, timeout=1)
        try:
            connection.request("GET", "/meals/T09-READY")
            response = connection.getresponse()
            response.read()
            assert response.status == 404 and response.getheader("X-Correlation-ID"), response.status
            return port
        except OSError:
            time.sleep(0.2)
        finally:
            connection.close()
    raise TimeoutError("L’API Java n’a pas atteint sa disponibilité HTTP")


def correlation():
    return {"X-Correlation-ID": str(uuid4())}


def verify_catalog(db, compose):
    active, = db.execute("""SELECT catalog_id, version, source_sha256
                            FROM catalog_active JOIN catalog_version USING (catalog_id, version)""").fetchall()
    assert active == ("DEMO-FOOD", "0.2.0", hashlib.sha256(SOURCE.read_bytes()).hexdigest())
    assert counts(db) == (1, 6, 60, 1)
    assert compose.logs("catalog").split()[:3] == ["activated", "DEMO-FOOD", "0.2.0"]
    print(f"PASS import T05 : {active[0]} {active[1]}, SHA-256 {active[2]}")


def nominal(db, port):
    f02 = body("T09-F02", CASES["F02"])
    f02_headers = {**correlation(), "Idempotency-Key": REPLAY_KEY}
    meal = check_oracle(db, port, f02, "java-macros-complete.json", headers=f02_headers)
    assert revisions(db, f02["entry_id"]) == ((1,), [(1,)], [(1,)], [(REPLAY_KEY,)])
    print("PASS F02 : 415 kcal, 42,5 g, 46 g et 4,3 g, catalogue fictif 0.2.0 ; POST/GET/SQL")

    s03 = body("T09-S03", CASES["S03"])
    s03_headers = correlation()
    workout = saved(db, port, s03, "squat", headers=s03_headers)
    known(workout, "sets", 3, "count", s03, "3 séries")
    known(workout, "repetitions", 10, "count", s03, "10 répétitions")
    known(workout, "load", 40, "kg", s03, "40 kg")
    known(workout, "total_repetitions", 30, "count", s03, "3 séries", "10 répétitions")
    assert workout["summary"]["total_repetitions"]["operation"] == "product"
    absent(workout, "distance")
    absent(workout, "duration")
    print("PASS S03 : 3 × 10, 30 répétitions et 40 kg, sources conservées ; POST/GET/SQL")

    s06 = body("T09-S06", CASES["S06"])
    s06_headers = correlation()
    ambiguous = saved(db, port, s06, "running", headers=s06_headers)
    known(ambiguous, "duration", 30, "min", s06, "30 minutes")
    assert unresolved(ambiguous, "distance", 5, s06, "5") == "Quelle unité correspond au nombre 5 ?"
    print("PASS S06 : 30 min, 5 sans unité conservé, distance inconnue et clarification ; POST/GET/SQL")

    return f02, meal, [headers["X-Correlation-ID"] for headers in (f02_headers, s03_headers, s06_headers)]


def refused(db, port, entry, expected):
    headers = {**correlation(), "Idempotency-Key": "failed-" + entry["entry_id"]}
    before = snapshot(db)
    started = time.monotonic()
    status, response = request(port, "POST", "/meals", entry, headers=headers,
                               expected=tuple(expected), with_status=True)
    reason = expected[status]
    elapsed = time.monotonic() - started
    assert response == {"error": reason}
    assert elapsed < 5, f"Réponse au-delà du délai attendu ({elapsed:.3f} s)"
    assert request(port, "GET", f"/meals/{entry['entry_id']}/revisions/1", expected=404) == {"error": "not_found"}
    assert revisions(db, entry["entry_id"]) == (None, [], [], [])
    assert snapshot(db) == before, "Le rejet a modifié au moins une table du journal"
    print(f"PASS {entry['entry_id']} : HTTP {status} {reason} en {elapsed:.3f} s, quatre tables intactes, "
          f"correlation={headers['X-Correlation-ID']}")
    return headers["X-Correlation-ID"], reason


def downtime(db, port, f02, meal):
    unavailable = refused(db, port, body("T09-DOWN", DOWN_TEXT), {502: "python_unavailable", 504: "python_timeout"})
    before = snapshot(db)
    headers = {**correlation(), "Idempotency-Key": REPLAY_KEY}
    assert request(port, "POST", "/meals", f02, headers=headers) == meal
    assert request(port, "GET", "/meals/T09-F02") == meal
    assert snapshot(db) == before and revisions(db, "T09-F02") == ((1,), [(1,)], [(1,)], [(REPLAY_KEY,)])
    replay = headers["X-Correlation-ID"]
    print(f"PASS rejeu F02 pendant l’arrêt Python : HTTP 200, résultat identique, une conséquence, correlation={replay}")

    conflict_headers = {**correlation(), "Idempotency-Key": REPLAY_KEY}
    assert request(port, "POST", "/meals", {**f02, "text": CASES["S06"]}, headers=conflict_headers, expected=409) == {
        "error": "idempotency_conflict"}
    assert snapshot(db) == before
    conflict = conflict_headers["X-Correlation-ID"]
    print(f"PASS contenu divergent pendant l’arrêt Python : HTTP 409, quatre tables intactes, correlation={conflict}")
    return unavailable, replay, conflict


def verify(db, compose):
    verify_catalog(db, compose)
    compose.no_published_python_port()
    port = java_ready(compose)
    print(compose.run("exec", "-T", "python", "python", "--version"))
    print(compose.run("exec", "-T", "java", "sh", "-c", "java -version 2>&1").splitlines()[0])
    print("PostgreSQL", db.execute("SHOW server_version").fetchone()[0])

    f02, meal, successful = nominal(db, port)
    blank = refused(db, port, body("T09-NBSP", "\u00a0"), {400: "invalid_request"})
    compose.run("stop", "--timeout", "5", "python")
    assert not compose.run("ps", "-q", "python"), "Python est encore en cours d’exécution"
    unavailable, replay, conflict = downtime(db, port, f02, meal)
    java_log, python_log = compose.logs("java"), compose.logs("python")
    for identifier in successful:
        assert f"correlation={identifier} outcome=proposal_accepted" in java_log
        assert f"correlation={identifier} outcome=journal_committed" in java_log
        assert f"proposal correlation={identifier}" in python_log
    for identifier, outcome in (blank, unavailable, (replay, "idempotent_replay"), (conflict, "idempotency_conflict")):
        assert f"correlation={identifier} outcome={outcome}" in java_log
        assert identifier not in python_log
    print("PASS corrélation HTTP/Java/Python pour F02, S03, S06 :", ", ".join(successful))

    # Nouveau processus Java pour résoudre l'adresse du pair remplacé via le DNS Compose.
    fault = ["-f", "scripts/t09-invalid.compose.yaml"]
    compose.run(*fault, "up", "--wait", "--wait-timeout", "40", "--no-deps", "--no-build",
                "--force-recreate", "python", timeout=60)
    compose.run(*fault, "up", "--wait", "--wait-timeout", "40", "--no-deps", "--no-build",
                "--force-recreate", "java", timeout=60)
    compose.no_published_python_port()
    invalid, _ = refused(db, java_ready(compose), body("T09-INVALID", INVALID_TEXT), {502: "invalid_proposal"})
    fault_java, fault_python = compose.logs("java"), compose.logs("python")
    assert f"correlation={invalid} outcome=invalid_proposal" in fault_java
    assert f"invalid_reply correlation={invalid}" in fault_python
    for service, log in (("java", java_log + fault_java), ("python", python_log + fault_python),
                         ("postgres", compose.logs("postgres")), ("catalog", compose.logs("catalog"))):
        assert log == compose.without_sensitive(log), f"Texte de déclaration, clé ou secret dans les logs de {service}"
    print("PASS corrélation du pair invalide et contrôle des traces Java, FastAPI, pair de test, PostgreSQL et import")


def stop_suite(process):
    # Les suites démarrent Java et Uvicorn dans une session propre. Le groupe peut
    # encore contenir ces descendants si son processus Python est déjà terminé.
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
        process.poll()
        try:
            os.killpg(process.pid, 0)
        except ProcessLookupError:
            return
        time.sleep(0.05)
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    process.wait(timeout=3)


def run_suite(command, env, timeout=180):
    with subprocess.Popen(command, cwd=ROOT, env=env, start_new_session=True) as process:
        try:
            status = process.wait(timeout)
            if status:
                raise subprocess.CalledProcessError(status, command)
        finally:
            stop_suite(process)


def run(args):
    with tempfile.TemporaryDirectory(prefix="llmsport-t09-") as directory:
        password_file = Path(directory) / "db-password"
        password_file.touch(mode=0o600, exist_ok=False)
        password = secrets.token_hex(32)
        password_file.write_text(password + "\n")
        compose = Compose(password_file, password)
        print(f"Projet Compose jetable {compose.project}", flush=True)
        print("Docker Engine", compose.docker("version", "--format", "{{.Server.Version}}"), flush=True)
        print(compose.run("version", "--short"), flush=True)

        maven = ["mvn", "-q", "-f", "java/pom.xml", "package"]
        if args.offline_maven:
            maven.insert(1, "-o")
        subprocess.run(maven, cwd=ROOT, check=True, timeout=300)
        try:
            compose.run("config", "--quiet")
            compose.run("up", "--wait", "--wait-timeout", "45", "postgres", timeout=120)
            env = {key: value for key, value in os.environ.items() if key != "DATABASE_URL" and not key.startswith("PG")}
            env.update(PGHOST=HOST, PGPORT=str(compose.port("postgres", 5432)),
                       PGDATABASE="llmsport", PGUSER="llmsport", PGPASSWORD=password)
            if args.all:
                for suite in SUITES:
                    print(f"=== {suite.upper()} ===", flush=True)
                    run_suite([sys.executable, "-B", f"scripts/verify_{suite}.py"], env)

            print("=== T09 ===", flush=True)
            compose.run("build", "catalog", timeout=300)
            compose.run("build", "python", timeout=300)
            compose.run("up", "--wait", "--wait-timeout", "70", "--no-build", timeout=120)
            with psycopg.connect(host=env["PGHOST"], port=env["PGPORT"], dbname=env["PGDATABASE"],
                                 user=env["PGUSER"], password=password, autocommit=True, connect_timeout=3) as db:
                verify(db, compose)
        finally:
            compose.clean()
            print(f"PASS nettoyage : conteneurs, réseaux et volume de {compose.project} supprimés")


def terminate(signum, _):
    raise SystemExit(128 + signum)


if __name__ == "__main__":
    if not __debug__:
        sys.exit("Activer les assertions Python pour cette vérification.")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--all", action="store_true", help="Exécuter également P0 et T04–T08.")
    parser.add_argument("--offline-maven", action="store_true", help="Réutiliser un cache Maven déjà complet.")
    signal.signal(signal.SIGTERM, terminate)
    run(parser.parse_args())
