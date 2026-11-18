"""Vérification CI locale. Depuis la racine : <python équipé> -B scripts/verify_t04.py"""

import json
import os
from contextlib import contextmanager
from http.client import HTTPConnection
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
from uuid import UUID, uuid4

ROOT = Path(__file__).resolve().parents[1]
HOST = "127.0.0.1"
JAR = ROOT / "java" / "target" / "llmsport-t04.jar"


def local_ports():
    with socket.socket() as first, socket.socket() as second:
        first.bind((HOST, 0))
        second.bind((HOST, 0))
        return first.getsockname()[1], second.getsockname()[1]


@contextmanager
def running(command, port, log, **env):
    with log.open("wb") as stream:
        process = subprocess.Popen(command, cwd=ROOT, env={**os.environ, **env},
                                   stdout=stream, stderr=subprocess.STDOUT)
    try:
        deadline = time.monotonic() + 30
        while process.poll() is None and time.monotonic() < deadline:
            try:
                with socket.create_connection((HOST, port), timeout=0.2):
                    break
            except OSError:
                time.sleep(0.1)
        else:
            raise RuntimeError(f"Échec au démarrage : {log.read_text()[-4000:]}")
        yield
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()


def post(port, text, correlation=None):
    headers = {"Content-Type": "application/json"}
    if correlation:
        headers["X-Correlation-ID"] = correlation
    meal = {"entry_id": "MEAL-001", "entry_revision": 2, "text": text}
    started = time.monotonic()
    connection = HTTPConnection(HOST, port, timeout=8)
    try:
        connection.request("POST", "/analysis", json.dumps(meal), headers)
        reply = connection.getresponse()
        payload = json.loads(reply.read())
        returned_id = str(UUID(reply.getheader("X-Correlation-ID")))
        assert not correlation or returned_id == correlation, (returned_id, correlation)
        return reply.status, payload, returned_id, time.monotonic() - started
    finally:
        connection.close()


def uvicorn(module, app_dir, port):
    return [sys.executable, "-B", "-m", "uvicorn", module, "--app-dir", str(ROOT / app_dir),
            "--host", HOST, "--port", str(port), "--no-access-log"]


def verify(logs):
    java_port, python_port = local_ports()
    with running(["java", "-jar", str(JAR)], java_port, logs / "java.log",
                 SERVER_ADDRESS=HOST, SERVER_PORT=str(java_port),
                 PYTHON_BASE_URL=f"http://{HOST}:{python_port}"):
        app_log = logs / "python.log"
        with running(uvicorn("app:app", "python", python_port), python_port, app_log):
            example = "mon accompagnement"
            status, first, correlation, elapsed = post(java_port, example, str(uuid4()))
            assert (status, first.get("kind"), first.get("entry_id"), first.get("entry_revision")) == (
                200, "python_proposal", "MEAL-001", 2), (status, first)
            assert first["food_mentions"][0]["source"]["text"] == example
            assert first["food_mentions"][0]["quantity"] is None
            second_status, second, generated, _ = post(java_port, example)
            assert second_status == 200 and second == first and generated != correlation
            for path in (app_log, logs / "java.log"):
                log = path.read_text()
                assert correlation in log and generated in log and example not in log
            print(f"PASS valid  HTTP {status}  {first['kind']}  correlation={correlation}  {elapsed:.3f} s")
            print("PASS replay  proposition identique, UUID généré par Java, traces corrélées sans texte fictif")

        with running(uvicorn("t04_faults:app", "scripts", python_port), python_port, logs / "faults.log"):
            for case, expected_status, reason in [
                ("invalid-json", 502, "invalid_json"),
                ("java-report", 502, "invalid_proposal"),
                ("invalid-shape", 502, "invalid_proposal"),
                ("other-entry", 502, "invalid_proposal"),
                ("other-revision", 502, "invalid_proposal"),
                ("other-correlation", 502, "invalid_correlation"),
                ("slow-body", 504, "python_timeout"),
            ]:
                status, body, _, elapsed = post(java_port, case, str(uuid4()))
                assert (status, body) == (expected_status, {"error": reason}), (case, status, body)
                if case == "slow-body":
                    assert elapsed < 5, f"Réponse tardive : {elapsed:.3f} s"
                print(f"PASS {case}  HTTP {status}  {reason}  {elapsed:.3f} s")


if __name__ == "__main__":
    if not __debug__:
        sys.exit("Ce contrôle exige les assertions Python actives (retirer -O ou PYTHONOPTIMIZE).")
    subprocess.run(["mvn", "-o", "-q", "-f", "java/pom.xml", "package"], cwd=ROOT, check=True)
    with tempfile.TemporaryDirectory(prefix="llmsport-t04-") as temporary:
        verify(Path(temporary))
