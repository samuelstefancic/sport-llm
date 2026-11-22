"""Stockage et agrégation des relevés locaux de l’écran de suivi."""

from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import fcntl
import json
import os
from pathlib import Path
import re
import sqlite3
import stat
import subprocess
import time
from uuid import UUID

from suivi_tokens import COUNTERS, ProjectScope, Reader, git_worktrees, timestamp


INTERVAL = 5
DRAIN = 2 * INTERVAL
RECENT_TASKS = 12
SERVICES = ("java", "python", "postgres")
ROLES = ("principal", "sous-agent", "demandeur")
TASK_ID = re.compile(r"[a-z0-9][a-z0-9-]{0,63}")
SCOPE_VERSION = 2
SCHEMA = """
CREATE TABLE IF NOT EXISTS tracking_scope (
  id INTEGER PRIMARY KEY CHECK (id = 1), version INTEGER NOT NULL, orchestration TEXT
);
CREATE TABLE IF NOT EXISTS tasks (
  id TEXT PRIMARY KEY, started_at TEXT NOT NULL, finished_at TEXT,
  estimated_at TEXT, min_minutes INTEGER, max_minutes INTEGER
);
CREATE TABLE IF NOT EXISTS sessions (
  task_id TEXT NOT NULL, id TEXT NOT NULL, role TEXT NOT NULL, number INTEGER NOT NULL,
  PRIMARY KEY (task_id, id)
);
CREATE TABLE IF NOT EXISTS samples (
  at TEXT PRIMARY KEY, java INTEGER, python INTEGER, postgres INTEGER, pressure INTEGER
);
CREATE TABLE IF NOT EXISTS sources (
  id TEXT PRIMARY KEY, cursor TEXT NOT NULL, status TEXT NOT NULL, observed_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS turns (
  session_id TEXT NOT NULL, id TEXT NOT NULL, started_at TEXT NOT NULL, observed_at TEXT NOT NULL,
  model TEXT, ended_at TEXT, status TEXT, PRIMARY KEY (session_id, id, observed_at)
);
CREATE TABLE IF NOT EXISTS tokens (
  session_id TEXT NOT NULL, at TEXT NOT NULL, turn_id TEXT NOT NULL, started_at TEXT NOT NULL,
  model TEXT, cumulative TEXT NOT NULL, status TEXT NOT NULL,
  input_tokens INTEGER, cached_input_tokens INTEGER, output_tokens INTEGER,
  reasoning_output_tokens INTEGER, total_tokens INTEGER,
  PRIMARY KEY (session_id, at, turn_id, cumulative)
);
"""


def now():
    return timestamp(datetime.now(timezone.utc).isoformat())


def seconds(started, ended):
    return max(0, (datetime.fromisoformat(ended) - datetime.fromisoformat(started)).total_seconds())


def add_commands(parser):
    commands = parser.add_subparsers(dest="suivi_action", required=True)
    declare = commands.add_parser("declarer", help="Ouvrir une tâche avec ses bornes initiales")
    declare.add_argument("id")
    declare.add_argument("--debut", help="Début réel attesté, au format ISO 8601 avec fuseau")
    declare.add_argument("--estime-le", help="Date de l’estimation initiale, avec fuseau")
    declare.add_argument("--min", type=int, dest="minimum", help="Borne basse en minutes")
    declare.add_argument("--max", type=int, dest="maximum", help="Borne haute en minutes")
    session = commands.add_parser("session", help="Inscrire une session Codex locale de llmSport")
    session.add_argument("id")
    session.add_argument("uuid")
    session.add_argument("--role", required=True, choices=ROLES)
    finish = commands.add_parser("finir", help="Clore la tâche et fixer l’horloge")
    finish.add_argument("id")
    finish.add_argument("--fin", help="Fin réelle attestée, avec fuseau")
    history = commands.add_parser("historique", help="Relire les tâches ou les échantillons d’une tâche en JSON")
    history.add_argument("id", nargs="?")


def declaration(args, at):
    started = timestamp(args.debut) if args.debut else at
    estimated = timestamp(args.estime_le) if args.estime_le else None
    minimum, maximum = args.minimum, args.maximum
    if started > at:
        raise ValueError("Le début doit être passé ou présent.")
    if (estimated, minimum, maximum) != (None, None, None):
        if estimated is None or minimum is None or maximum is None or not 0 <= minimum <= maximum <= 10**7:
            raise ValueError("L’estimation exige --estime-le, --min et --max dans l’ordre croissant.")
        if estimated > started:
            raise ValueError("L’estimation initiale doit être datée au plus tard au début.")
    return started, estimated, minimum, maximum


def valid_id(identifier):
    if not TASK_ID.fullmatch(identifier):
        raise ValueError("Identifiant invalide (1 à 64 caractères a-z, 0-9 ou tiret).")
    return identifier


class Tracking:
    def __init__(self, instance, project, trial):
        self.directory = instance / "suivi-direct"
        self.directory.mkdir(mode=0o700, exist_ok=True)
        info = self.directory.lstat()
        if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o700:
            raise RuntimeError("Le répertoire du suivi doit appartenir à l’utilisateur et être privé (0700).")
        self.db_path = self.directory / "historique.sqlite3"
        self.snapshot = self.directory / "affichage.json"
        self.project = project.resolve()
        codex_root = Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex")))
        self.source = self.directory / "sources" if trial else codex_root.resolve()

    @contextmanager
    def locked(self, new_orchestration=None):
        with (self.directory / "ecriture.lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            connection = sqlite3.connect(self.db_path, timeout=10)
            connection.row_factory = sqlite3.Row
            try:
                connection.executescript(SCHEMA)
                recorded = connection.execute("SELECT version, orchestration FROM tracking_scope WHERE id=1").fetchone()
                orchestration = recorded["orchestration"] if recorded else None
                if new_orchestration is not None:
                    orchestration = new_orchestration or None
                if recorded is None or tuple(recorded) != (SCOPE_VERSION, orchestration):
                    self.rebuild(connection, orchestration)
                with connection:
                    yield connection
            finally:
                connection.close()

    def rebuild(self, db, orchestration):
        with (self.directory / "collecteur.lock").open("a") as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise RuntimeError("Redémarrer l’écran pour mettre à jour le périmètre du suivi.") from None
            # Java peut lire ce fichier indépendamment de la transaction SQLite.
            self.snapshot.unlink(missing_ok=True)
            with db:
                for table in ("sources", "turns", "tokens"):
                    db.execute(f"DELETE FROM {table}")
                db.execute("INSERT OR REPLACE INTO tracking_scope VALUES (1, ?, ?)",
                           (SCOPE_VERSION, orchestration))
                self.scan_sessions(db, now(), require_scope=True)
            self.publish(db, now())

    def prepare(self, orchestration):
        with self.locked(orchestration) as db:
            self.publish(db, now())

    def publish(self, db, at):
        latest = db.execute("SELECT * FROM samples ORDER BY at DESC LIMIT 1").fetchone()
        active = db.execute("SELECT * FROM tasks WHERE finished_at IS NULL ORDER BY started_at DESC").fetchall()
        history = db.execute("""
            SELECT * FROM tasks WHERE finished_at IS NOT NULL ORDER BY started_at DESC LIMIT ?
        """, (RECENT_TASKS,)).fetchall()
        payload = {
            "schema_version": 1, "generated_at": at, "sample_interval_seconds": INTERVAL,
            "rss_unit": "KiB", "postgres_scope": "parent",
            "latest_sample": dict(latest) if latest else None,
            "active_tasks": [task_view(db, task, at) for task in active],
            "history": [task_view(db, task, at) for task in history],
        }
        temporary = self.snapshot.with_suffix(".tmp")
        temporary.write_text(json.dumps(payload, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
        temporary.replace(self.snapshot)

    def scan_sessions(self, db, at, require_scope=False):
        grace = timestamp((datetime.fromisoformat(at) - timedelta(seconds=DRAIN)).isoformat())
        identifiers = db.execute("""
            SELECT DISTINCT s.id FROM sessions s JOIN tasks t ON t.id=s.task_id
            LEFT JOIN sources r ON r.id=s.id
            WHERE t.finished_at IS NULL OR t.finished_at>=? OR r.observed_at IS NULL
                OR r.observed_at<=t.finished_at OR r.status='lecture_en_cours'
        """, (grace,)).fetchall()
        if not identifiers:
            return
        try:
            worktrees = git_worktrees(self.project)
        except RuntimeError:
            if require_scope:
                raise
            # Le prochain tick réessaiera sans avancer les curseurs de lecture.
            return
        (orchestration,) = db.execute("SELECT orchestration FROM tracking_scope WHERE id=1").fetchone()
        scope = ProjectScope(worktrees, Path(orchestration) if orchestration else None)
        for (identifier,) in identifiers:
            windows = db.execute("""
                SELECT t.started_at, t.finished_at FROM tasks t
                JOIN sessions s ON t.id=s.task_id WHERE s.id=?
            """, (identifier,)).fetchall()
            Reader(db, identifier, self.source, scope, windows).scan(at)

    def collect(self, instance, same_process):
        with (self.directory / "collecteur.lock").open("a") as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                return
            while True:
                started = time.monotonic()
                instance.load_state()
                self.tick(instance.state, same_process)
                time.sleep(max(0, INTERVAL - (time.monotonic() - started)))

    def tick(self, processes, same_process):
        sample = [rss(processes.get(name), same_process) for name in SERVICES]
        pressure = numeric_command(["/usr/sbin/sysctl", "-n", "kern.memorystatus_vm_pressure_level"])
        at = now()
        with self.locked() as db:
            db.execute("INSERT INTO samples VALUES (?, ?, ?, ?, ?)", (at, *sample, pressure))
            self.scan_sessions(db, at)
            db.commit()
            self.publish(db, now())

    def command(self, args):
        identifier = valid_id(args.id) if args.id is not None else None
        with self.locked() as db:
            at = now()
            task = db.execute("SELECT * FROM tasks WHERE id = ?", (identifier,)).fetchone()
            if args.suivi_action == "historique":
                data = history(db, identifier, task, at)
                print(json.dumps(data, ensure_ascii=False, indent=2))
                return
            if args.suivi_action == "declarer":
                declare_task(db, args, identifier, at, task)
            elif task is None:
                raise ValueError("Tâche inconnue.")
            elif args.suivi_action == "session":
                register_session(db, args, task)
            elif args.suivi_action == "finir":
                finish_task(db, args, at, task)
            db.commit()
            self.publish(db, now())
        print(f"Suivi enregistré · {identifier}")


def declare_task(db, args, identifier, at, task):
    started, estimated, minimum, maximum = declaration(args, at)
    if task is not None:
        before = tuple(task[key] for key in ("started_at", "estimated_at", "min_minutes", "max_minutes"))
        if before != (started, estimated, minimum, maximum):
            raise ValueError("Cet identifiant possède déjà d’autres bornes.")
        return
    db.execute("INSERT INTO tasks VALUES (?, ?, NULL, ?, ?, ?)",
               (identifier, started, estimated, minimum, maximum))


def register_session(db, args, task):
    try:
        identifier = str(UUID(args.uuid))
    except ValueError:
        raise ValueError("Indiquer l’UUID d’une session Codex.") from None
    existing = db.execute("SELECT role FROM sessions WHERE task_id=? AND id=?", (task["id"], identifier)).fetchone()
    if existing is not None:
        if existing["role"] != args.role:
            raise ValueError("Cette session est déjà inscrite avec un autre rôle.")
    else:
        peers = sessions(db, task)
        if len(peers) >= 16:
            raise ValueError("Cette tâche possède déjà 16 sessions inscrites.")
        db.execute("INSERT INTO sessions VALUES (?, ?, ?, ?)", (task["id"], identifier, args.role, len(peers) + 1))
    # Rejouer la source pour une borne ajoutée ou pour un rattrapage demandé explicitement.
    db.execute("DELETE FROM sources WHERE id = ?", (identifier,))


def finish_task(db, args, at, task):
    if task["finished_at"] is not None and not args.fin:
        return
    ended = timestamp(args.fin) if args.fin else at
    if not task["started_at"] <= ended <= at:
        raise ValueError("La fin doit être comprise entre le début et maintenant.")
    if task["finished_at"] not in (None, ended):
        raise ValueError("La tâche possède déjà une autre date de fin.")
    db.execute("UPDATE tasks SET finished_at=? WHERE id=?", (ended, task["id"]))


def numeric_command(command):
    try:
        completed = subprocess.run(command, capture_output=True, text=True, timeout=1, check=True)
        value = int(completed.stdout.strip())
        return value if value >= 0 else None
    except (OSError, ValueError, subprocess.SubprocessError):
        return None


def rss(process, same_process):
    if not process:
        return None
    pid, signature = process["pid"], process["signature"]
    if not same_process(pid, signature):
        return None
    value = numeric_command(["ps", "-p", str(pid), "-o", "rss="])
    return value if same_process(pid, signature) else None


def sessions(db, task):
    return db.execute("SELECT * FROM sessions WHERE task_id=? ORDER BY number", (task["id"],)).fetchall()


def session_view(db, session, started, ended, include_samples=False):
    identifier = session["id"]
    source = db.execute("SELECT status, observed_at FROM sources WHERE id = ?", (identifier,)).fetchone()
    rows = db.execute("""
        SELECT at, started_at, model, status, input_tokens, cached_input_tokens, output_tokens,
               reasoning_output_tokens, total_tokens
        FROM tokens WHERE session_id=? AND at BETWEEN ? AND ? ORDER BY at
    """, (identifier, started, ended)).fetchall()
    measured = [row for row in rows if row["total_tokens"] is not None]
    models = {row["model"] for row in db.execute("""
        SELECT model FROM turns WHERE session_id=? AND observed_at<=? AND (ended_at IS NULL OR ended_at>=?)
    """, (identifier, ended, started)) if row["model"] is not None}
    models.update(row["model"] for row in measured if row["model"] is not None)
    turns = db.execute("""
        SELECT id, MIN(started_at) AS started_at,
               MAX(CASE WHEN status='termine' THEN ended_at END) AS completed_at,
               MAX(CASE WHEN status='interrompu' THEN ended_at END) AS aborted_at
        FROM turns WHERE session_id=? AND observed_at<=?
        GROUP BY id HAVING SUM(ended_at IS NULL)>0 OR MAX(ended_at)>=?
    """, (identifier, ended, started)).fetchall()
    view = {
        "number": session["number"], "role": session["role"], "models": sorted(models),
        "source_status": source["status"] if source else "non_lu",
        "source_checked_at": source["observed_at"] if source else None,
        "first_at": measured[0]["at"] if measured else None, "last_at": measured[-1]["at"] if measured else None,
        "snapshots": len(measured), "missing_snapshots": len(rows) - len(measured),
        "counter_resets": sum(row["status"] == "reinitialise" for row in rows),
        "boundary_snapshots": sum(row["started_at"] < started for row in measured),
        "turns_started": sum(row["started_at"] >= started for row in turns),
        "turns_completed": sum(row["completed_at"] is not None and row["completed_at"] <= ended for row in turns),
        "turns_aborted": sum(row["aborted_at"] is not None and row["aborted_at"] <= ended for row in turns),
        "tokens": {key: sum(row[key] for row in measured) if measured and all(
            row[key] is not None for row in measured
        ) else None for key in COUNTERS},
    }
    if include_samples:
        view["samples"] = [dict(row) for row in rows]
    return view


def task_view(db, task, at, include_samples=False):
    started, finished = task["started_at"], task["finished_at"]
    ended = finished or at
    elapsed = seconds(started, ended)
    estimate = None
    gap = None
    if task["estimated_at"] is not None:
        estimate = {key: task[key] for key in ("estimated_at", "min_minutes", "max_minutes")}
        low, high = estimate["min_minutes"] * 60, estimate["max_minutes"] * 60
        gap = elapsed - min(max(elapsed, low), high)
    samples = db.execute("""
        SELECT MIN(at) AS first_at, MAX(at) AS last_at, COUNT(*) AS count, MAX(java) AS java,
               MAX(python) AS python, MAX(postgres) AS postgres FROM samples WHERE at BETWEEN ? AND ?
    """, (started, ended)).fetchone()
    view = {
        "id": task["id"], "status": "termine" if finished else "actif",
        "started_at": started, "finished_at": finished, "elapsed_seconds": elapsed,
        "estimate": estimate, "estimate_gap_seconds": gap,
        "sessions": [session_view(db, session, started, ended, include_samples) for session in sessions(db, task)],
        "memory": dict(samples),
        "recent_memory_samples": [dict(row) for row in db.execute("""
            SELECT * FROM samples WHERE at BETWEEN ? AND ? ORDER BY at DESC LIMIT 5
        """, (started, ended))],
    }
    if include_samples:
        view["memory_samples"] = [dict(row) for row in db.execute(
            "SELECT * FROM samples WHERE at BETWEEN ? AND ? ORDER BY at", (started, ended))]
    return view


def history(db, identifier, task, at):
    if identifier is not None:
        if task is None:
            raise ValueError("Tâche inconnue.")
        return task_view(db, task, at, include_samples=True)
    return [task_view(db, item, at) for item in db.execute("SELECT * FROM tasks ORDER BY started_at DESC")]
