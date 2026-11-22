"""Démarrage hors ligne de l'écran, avec un cluster PostgreSQL dédié."""

import argparse
import fcntl
import json
import os
from pathlib import Path
import secrets
import shutil
import signal
import socket
import subprocess
import sys
import time
from urllib.request import ProxyHandler, build_opener

import psycopg


ROOT = Path(__file__).resolve().parents[1]
PG = Path(os.environ["LLMSPORT_T10_TOOLS"]).resolve() / "postgres-17.12/bin"
HOST = "127.0.0.1"
HTTP = build_opener(ProxyHandler({}))
USER = "llmsport"


def process_signature(pid):
    probe = subprocess.run(["ps", "-ww", "-p", str(pid), "-o", "lstart=", "-o", "command="],
                           text=True, capture_output=True)
    return probe.stdout.strip()


def signature_parts(signature):
    # macOS can report the JVM command as either java or /usr/bin/java after exec.
    fields = signature.split(maxsplit=6)
    if len(fields) == 7 and fields[5] in ("java", "/usr/bin/java"):
        fields[5] = "/usr/bin/java"
    return fields


def same_process(pid, signature):
    return bool(signature) and signature_parts(process_signature(pid)) == signature_parts(signature)


class Instance:
    def __init__(self, trial):
        self.web, self.python, self.postgres = (8213, 8214, 8215) if trial else (8113, 8114, 8115)
        self.directory = ROOT / ".local" / ("ecran-essai" if trial else "ecran")
        self.directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.data = self.directory / "postgres"
        self.state_path = self.directory / "processus.json"
        self.config = self.directory / "config"
        self.password_path = self.config / "journal.db.password"
        self.jar = self.directory / "llmsport-t04.jar"
        self.url = f"http://{HOST}:{self.web}"
        self.state = {}

    def load_state(self):
        if self.state_path.exists():
            self.state = json.loads(self.state_path.read_text())

    def store_state(self):
        temporary = self.state_path.with_suffix(".tmp")
        temporary.write_text(json.dumps(self.state, indent=2))
        temporary.replace(self.state_path)

    def stop(self):
        for name in ("java", "python", "postgres"):
            if name not in self.state:
                continue
            process = self.state[name]
            pid, signature = process["pid"], process["signature"]
            if same_process(pid, signature):
                # SIGINT requests a fast, clean shutdown of the dedicated PostgreSQL server.
                os.kill(pid, signal.SIGINT if name == "postgres" else signal.SIGTERM)
                for _ in range(100):
                    if not same_process(pid, signature):
                        break
                    time.sleep(.1)
                else:
                    raise RuntimeError(f"{name} ne s’arrête pas (PID {pid}).")
            del self.state[name]
            self.store_state()
        print(f"Services arrêtés. Journal conservé dans {self.data}.")

    def launch(self, name, args, env=None):
        path = self.directory / f"{name}.log"
        with path.open("a") as log:
            process = subprocess.Popen([str(arg) for arg in args], env=env, cwd=self.directory,
                                       stdin=subprocess.DEVNULL, stdout=log, stderr=log, start_new_session=True)
        signature = process_signature(process.pid)
        if not signature:
            raise RuntimeError(f"{name} n’a pas démarré. Voir {path}.")
        self.state[name] = {"pid": process.pid, "signature": signature}
        self.store_state()
        return process

    def ready(self, name, process, probe):
        until = time.monotonic() + 30
        while time.monotonic() < until and process.poll() is None:
            try:
                if probe():
                    return
            except (OSError, psycopg.Error):
                pass
            time.sleep(.2)
        raise RuntimeError(f"{name} indisponible. Voir {self.directory / (name + '.log')}.")

    def database(self):
        return psycopg.connect(host=HOST, port=self.postgres, dbname="postgres", user=USER,
                               password=self.password_path.read_text().strip(), sslmode="disable",
                               connect_timeout=2, autocommit=True)

    def check_database(self):
        with self.database() as connection:
            if connection.execute("SHOW data_directory").fetchone() != (str(self.data),):
                raise RuntimeError("Le port PostgreSQL ne répond pas depuis le cluster dédié.")
            return True

    def init_database(self):
        self.config.mkdir(mode=0o700, exist_ok=True)
        if not self.password_path.exists():
            if self.data.exists():
                raise RuntimeError("Mot de passe du cluster existant introuvable.")
            fd = os.open(self.password_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "w") as out:
                out.write(secrets.token_urlsafe(32) + "\n")
        if self.data.exists():
            if not (self.data / "PG_VERSION").is_file():
                raise RuntimeError(f"Initialisation incomplète. Répertoire préservé : {self.data}.")
            return
        env = {**os.environ, "LC_ALL": "C"}
        subprocess.run([str(PG / "initdb"), "-D", str(self.data), "-U", USER, "--no-locale",
                        "--encoding=UTF8", "--auth-host=scram-sha-256", "--auth-local=reject",
                        f"--pwfile={self.password_path}"], env=env, check=True)

    def initialize_schema(self):
        with self.database() as connection:
            connection.execute((ROOT / "java/src/main/resources/journal.sql").read_text(), prepare=False)
        env = {k: v for k, v in os.environ.items() if not k.startswith("PG") and k != "DATABASE_URL"}
        env.update(PGHOST=HOST, PGPORT=str(self.postgres), PGDATABASE="postgres", PGUSER=USER,
                   PGPASSWORD=self.password_path.read_text().strip(), PGSSLMODE="disable", PGCONNECT_TIMEOUT="3")
        subprocess.run([sys.executable, "-IB", str(ROOT / "catalog/import_catalog.py"), "--init-schema"],
                       env=env, check=True)

    def build(self):
        print("Assemblage Maven hors ligne…", flush=True)
        log_path = self.directory / "maven.log"
        with (self.directory.parent / "ecran-maven.lock").open("a") as lock, log_path.open("w") as log:
            fcntl.flock(lock, fcntl.LOCK_EX)
            built = subprocess.run(["mvn", "-o", "-f", str(ROOT / "java/pom.xml"), "-DskipTests", "package"],
                                   cwd=ROOT, stdout=log, stderr=subprocess.STDOUT)
            if built.returncode:
                raise RuntimeError(f"Maven a renvoyé {built.returncode}. Voir {log_path}.")
            shutil.copyfile(ROOT / "java/target/llmsport-t04.jar", self.jar)

    def start(self):
        running = self.running()
        if len(running) == 3:
            print(f"Écran déjà démarré sur {self.url}/")
            return
        if running:
            raise RuntimeError("Services partiellement actifs. Utiliser restart.")
        for port in (self.web, self.python, self.postgres):
            with socket.socket() as sock:
                try:
                    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                    sock.bind((HOST, port))
                except OSError as error:
                    raise RuntimeError(f"Port {HOST}:{port} indisponible.") from error
        for binary in ("mvn", "java", PG / "initdb", PG / "postgres"):
            if not shutil.which(str(binary)):
                raise RuntimeError(f"Outil local introuvable : {binary}")
        self.build()
        self.init_database()
        try:
            postgres = self.launch("postgres", [PG / "postgres", "-D", self.data, "-p", self.postgres,
                                                "-c", f"listen_addresses={HOST}", "-c", "unix_socket_directories="])
            self.ready("postgres", postgres, self.check_database)
            self.initialize_schema()
            python = self.launch("python", [sys.executable, "-B", "-m", "uvicorn", "app:app", "--host", HOST,
                                            "--port", self.python, "--app-dir", ROOT / "python", "--no-access-log"])
            self.ready("python", python, lambda: self.get(f"http://{HOST}:{self.python}/openapi.json"))
            java = self.launch("java", [shutil.which("java"), "-jar", self.jar, f"--server.port={self.web}",
                                       f"--server.address={HOST}", "--spring.profiles.active=ecran-local",
                                       f"--ecran.worktree={ROOT}",
                                       f"--python.base-url=http://{HOST}:{self.python}",
                                       f"--journal.jdbc.url=jdbc:postgresql://{HOST}:{self.postgres}/postgres",
                                       f"--journal.db.user={USER}", f"--spring.config.import=configtree:{self.config}/"])
            self.ready("java", java, lambda: self.get(f"{self.url}/workouts"))
        except (Exception, KeyboardInterrupt):
            self.stop()
            raise
        print(f"Écran opérationnel sur {self.url}/")

    @staticmethod
    def get(url):
        with HTTP.open(url, timeout=2) as response:
            return response.status == 200

    def running(self):
        return {name: item["pid"] for name, item in self.state.items()
                if same_process(item["pid"], item["signature"])}

    def status(self):
        active = self.running()
        if active:
            print(f"{self.url}/ · " + ", ".join(f"{name} {pid}" for name, pid in active.items()))
        else:
            print(f"Services arrêtés. Répertoire du journal : {self.data}.")
        return 0 if len(active) == 3 else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("start", "stop", "restart", "status"))
    parser.add_argument("--essai", action="store_true", help="Ports et cluster distincts pour les vérifications")
    args = parser.parse_args()
    os.umask(0o077)
    instance = Instance(args.essai)
    try:
        with (instance.directory / "commande.lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            instance.load_state()
            if args.action in ("stop", "restart"):
                instance.stop()
            if args.action in ("start", "restart"):
                instance.start()
            if args.action == "status":
                return instance.status()
    except (RuntimeError, OSError, subprocess.CalledProcessError, psycopg.Error) as error:
        parser.exit(1, f"Échec du lancement local : {error}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
