"""Lit les compteurs des seules sessions inscrites au suivi, par lignes complètes."""

import json
import os
from pathlib import Path
import re
import stat
from datetime import datetime, timezone


COUNTERS = ("input_tokens", "cached_input_tokens", "output_tokens",
            "reasoning_output_tokens", "total_tokens")
ENVELOPE = re.compile(rb'^\s*\{\s*"timestamp"\s*:\s*"([0-9TZ:+.\-]+)"\s*,\s*'
                      rb'(?:"ordinal"\s*:\s*[0-9]+\s*,\s*)?'
                      rb'"type"\s*:\s*"(session_meta|turn_context|event_msg)"\s*,\s*'
                      rb'"payload"\s*:\s*\{')
EVENT = re.compile(rb'\s*"type"\s*:\s*"(task_started|task_complete|turn_aborted|token_count)"\s*[,}]')
FIELD = re.compile(rb'\s*"([a-zA-Z0-9_]+)"\s*:\s*')
DELIMITER = re.compile(rb'\s*[,}]')
JSON_TOKEN = re.compile(rb'"(?:[^"\\]++|\\.)*+"|[^{}\[\]"\s,:]+|[{}\[\]:,]')
MODEL = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,95}")
TURN = re.compile(r"[0-9a-f-]{36}")
MAX_LINE = 2 * 1024 * 1024
READ_BUDGET = 32 * 1024 * 1024


def timestamp(value):
    if not isinstance(value, str):
        raise ValueError("Horodatage manquant.")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if not parsed.tzinfo:
        raise ValueError("Indiquer le fuseau de l’horodatage.")
    return parsed.astimezone(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def in_project(cwd, project):
    return isinstance(cwd, str) and Path(cwd).is_absolute() and Path(
        os.path.normpath(cwd)
    ).is_relative_to(project)


def project(data, offset, keys):
    """Projette les champs utiles sans décoder les autres valeurs de la source."""
    result = {}
    while offset < len(data):
        field = FIELD.match(data, offset)
        if field is None:
            break
        start = field.end()
        tokens = JSON_TOKEN.finditer(data, start)
        first = next(tokens, None)
        if first is None or first.start() != start:
            break
        end = first.end()
        if first[0] in (b"{", b"["):
            depth = 1
            for token in tokens:
                if token[0] in (b"{", b"["):
                    depth += 1
                elif token[0] in (b"}", b"]"):
                    depth -= 1
                    if depth == 0:
                        end = token.end()
                        break
            if depth:
                break
        key = field[1]
        if key in keys:
            schema = keys[key]
            if schema is None and first[0] not in (b"{", b"["):
                result[key.decode()] = json.loads(data[start:end])
            elif schema is not None and first[0] == b"{":
                result[key.decode()] = project(data, first.end(), schema)
        delimiter = DELIMITER.match(data, end)
        if delimiter is None or data[delimiter.end() - 1] == ord("}"):
            break
        offset = delimiter.end()
    return result


USAGE = {key.encode(): None for key in COUNTERS}
TOKEN_FIELDS = {b"info": {b"total_token_usage": USAGE, b"last_token_usage": USAGE,
                          b"last_usage_includes_reasoning": None}}


def source_path(root, session_id, known):
    pattern = f"rollout-*-{session_id}.jsonl"
    if known:
        candidate = root / known
        if candidate.is_relative_to(root) and candidate.match(pattern) and (
            candidate == candidate.resolve() and candidate.is_file()
        ):
            return candidate
    matches = set((root / "sessions").glob(f"*/*/*/{pattern}"))
    matches.update((root / "archived_sessions").glob(pattern))
    matches = {path for path in matches if path == path.resolve() and path.is_file()}
    return next(iter(matches)) if len(matches) == 1 else None


def counters(usage):
    values = [(usage or {}).get(key) for key in COUNTERS]
    result = [item if type(item) is int and 0 <= item < 2**53 else None for item in values]
    if any(result[index] is None for index in (0, 2, 4)):
        return None
    if result[1] is not None and result[1] > result[0]:
        result[1] = None
    return tuple(result)


def core(amounts):
    return None if amounts is None else (amounts[0], amounts[2], amounts[4])


def usage_delta(cumulative, last, previous, first_turn):
    if core(cumulative) == core(previous):
        return None, "duplique"
    reset = core(cumulative) == core(last)
    if previous is None:
        if first_turn and reset:
            return cumulative, "mesure"
        return None, "lacune"
    change = tuple(now - before if now is not None and before is not None else None
                   for now, before in zip(cumulative, previous))
    if min(core(change)) < 0 or (last is not None and core(change) != core(last)):
        # Un total égal au dernier usage signale un nouvel epoch observable.
        return (cumulative, "reinitialise") if reset else (None, "lacune")
    # Les deux détails peuvent manquer sans perdre les trois compteurs principaux.
    values = list(change)
    for index, parent in ((1, 0), (3, 2)):
        value = values[index]
        if value is not None and (not 0 <= value <= values[parent] or last is not None
                                  and last[index] is not None and value != last[index]):
            values[index] = None
    return tuple(values), "mesure"


class Reader:
    def __init__(self, connection, session_id, root, project, windows):
        self.db = connection
        self.session_id = session_id
        self.root = root
        self.project = project
        self.windows = windows
        self.last_end = None if any(end is None for _, end in windows) else max(end for _, end in windows)
        row = connection.execute("SELECT cursor FROM sources WHERE id = ?", (session_id,)).fetchone()
        self.state = json.loads(row["cursor"]) if row else {}

    def scan(self, observed_at):
        status = self.read_source()
        turn = self.state.get("turn")
        if status == "lu" and turn and self.overlaps(turn, self.last_end or observed_at):
            self.note_turn(turn)
        self.db.execute("""
            INSERT INTO sources (id, cursor, status, observed_at) VALUES (?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET cursor=excluded.cursor, status=excluded.status,
                observed_at=excluded.observed_at
        """, (self.session_id, json.dumps(self.state, separators=(",", ":")), status, observed_at))

    def read_source(self):
        try:
            source = source_path(self.root, self.session_id, self.state.get("location"))
            if source is None:
                return "indisponible"
            fd = os.open(source, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
            with os.fdopen(fd, "rb") as stream:
                info = os.fstat(stream.fileno())
                if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid():
                    return "indisponible"
                identity = [info.st_dev, info.st_ino]
                if identity != self.state.get("file") or info.st_size < self.state.get("offset", 0):
                    self.state = {"file": identity, "offset": 0}
                self.state["location"] = str(source.relative_to(self.root))
                return self.read_lines(stream, info.st_size)
        except (OSError, RuntimeError):
            return "indisponible"

    def read_lines(self, stream, size):
        offset = self.state["offset"]
        stream.seek(offset)
        limit = min(size, offset + READ_BUDGET)
        while stream.tell() < limit:
            offset = stream.tell()
            line = stream.readline(min(MAX_LINE + 1, size - offset))
            if len(line) > MAX_LINE or self.state.get("discarding"):
                if offset == 0:
                    self.state["matched"] = False
                    return "hors_perimetre"
                self.state["discarding"] = not line.endswith(b"\n")
            elif not line.endswith(b"\n"):
                break
            elif offset == 0:
                self.check_identity(line)
            elif self.state.get("matched") and self.consume(line) is False:
                # Le curseur reste au début de cet événement pour une future tâche inscrite.
                return "lu"
            if self.state.get("matched") is False:
                return "hors_perimetre"
            self.state["offset"] = stream.tell()
        if not self.state.get("matched"):
            return "indisponible"
        return "lecture_en_cours" if limit < size else "lu"

    def check_identity(self, line):
        try:
            envelope = ENVELOPE.match(line, 0, 256)
            if envelope is None or envelope[2] != b"session_meta":
                self.state["matched"] = False
                return
            meta = project(line, envelope.end(), {b"id": None, b"cwd": None})
            self.state["matched"] = (meta.get("id") == self.session_id
                                     and in_project(meta.get("cwd"), self.project))
        except (ValueError, RecursionError):
            self.state["matched"] = False

    def consume(self, line):
        try:
            envelope = ENVELOPE.match(line, 0, 256)
            if envelope is None:
                return
            offset = envelope.end()
            kind = envelope[2].decode()
            if kind == "event_msg":
                event = EVENT.match(line, offset, 256)
                if event is None:
                    return
                kind = event[1].decode()
            elif kind != "turn_context":
                return
            fields = TOKEN_FIELDS if kind == "token_count" else {b"turn_id": None}
            if kind == "turn_context":
                fields.update({b"cwd": None, b"model": None})
            payload = project(line, offset, fields)
            at = timestamp(envelope[1].decode())
            if self.last_end is not None and at > self.last_end:
                return False
        except (ValueError, RecursionError):
            return
        if kind == "token_count":
            self.token(payload, at)
        else:
            self.turn(kind, payload, at)

    def turn(self, kind, payload, at):
        ident = payload.get("turn_id")
        if not isinstance(ident, str) or not TURN.fullmatch(ident):
            return
        if kind == "task_started":
            last_turn = self.state.get("turn")
            if last_turn and last_turn["id"] != ident:
                if self.overlaps(last_turn, at):
                    self.note_turn(last_turn)
                self.db.execute("""
                    UPDATE turns SET ended_at=?, status='reprise' WHERE session_id=? AND id=? AND ended_at IS NULL
                """, (at, self.session_id, last_turn["id"]))
            self.state["turn"] = {"id": ident, "start": at}
            if "first_turn" not in self.state:
                self.state["first_turn"] = ident
        turn = self.state.get("turn", {})
        if turn.get("id") != ident:
            return
        if kind == "turn_context":
            if self.overlaps(turn, at):
                self.note_turn(turn)
            self.db.execute("""
                UPDATE turns SET ended_at=?, status='contexte_suivant'
                WHERE session_id=? AND id=? AND ended_at IS NULL AND observed_at<?
            """, (at, self.session_id, ident, at))
            turn["scoped"] = in_project(payload.get("cwd"), self.project)
            model = payload.get("model")
            turn["model"] = model if turn["scoped"] and isinstance(model, str) and MODEL.fullmatch(model) else None
            turn["context_at"] = at
        if kind in ("task_complete", "turn_aborted"):
            if self.overlaps(turn, at):
                self.note_turn(turn)
            status = "termine" if kind == "task_complete" else "interrompu"
            self.db.execute("""
                UPDATE turns SET ended_at=?, status=? WHERE session_id=? AND id=? AND ended_at IS NULL
            """, (at, status, self.session_id, ident))
            self.state.pop("turn", None)

    def overlaps(self, turn, at):
        return bool(turn.get("scoped")) and any(
            start <= at and (end is None or turn["context_at"] <= end) for start, end in self.windows
        )

    def note_turn(self, turn):
        self.db.execute("""
            INSERT OR IGNORE INTO turns (session_id, id, started_at, observed_at, model)
            VALUES (?, ?, ?, ?, ?)
        """, (self.session_id, turn["id"], turn["start"], turn["context_at"], turn.get("model")))

    def token(self, payload, at):
        info = payload.get("info", {})
        cumulative = counters(info.get("total_token_usage"))
        last = counters(info.get("last_token_usage"))
        previous = self.state.get("previous")
        turn = self.state.get("turn", {})
        interval_start = self.state.get("previous_at") if turn.get("id") == self.state.get("previous_turn") else None
        state = "lacune"
        amounts = None
        if cumulative is not None:
            first_turn = (turn.get("id") is not None and turn["id"] == self.state.get("first_turn")
                          and not self.state.get("seen_counter"))
            amounts, state = usage_delta(cumulative, last, tuple(previous) if previous is not None else None,
                                         first_turn)
            if state != "duplique":
                self.state["previous"] = cumulative
                self.state["previous_at"] = at
                self.state["previous_turn"] = turn.get("id")
            self.state["seen_counter"] = True
        if not turn.get("scoped") or state == "duplique" or not any(
            start <= at and (end is None or at <= end) for start, end in self.windows
        ):
            return
        self.note_turn(turn)
        if amounts is not None and (amounts[3] is None or amounts[3] > amounts[2]
                                    or info.get("last_usage_includes_reasoning") is not True):
            amounts = (*amounts[:3], None, amounts[4])
        values = amounts if amounts is not None else (None,) * len(COUNTERS)
        # Le triplet horodatage, tour, cumul distingue les émissions et rend un rejeu idempotent.
        self.db.execute("""
            INSERT OR IGNORE INTO tokens VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (self.session_id, at, turn["id"], interval_start or turn["start"], turn.get("model"), json.dumps(cumulative),
              state, *values))
