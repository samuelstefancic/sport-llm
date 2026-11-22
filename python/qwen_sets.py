"""Jeux fictifs et reçus de séries du laboratoire local."""

from contextlib import ExitStack, contextmanager
from datetime import datetime, timezone
from decimal import Decimal
import fcntl
from hashlib import sha256
from itertools import zip_longest
import json
import logging
import os
from pathlib import Path
import re
import stat
from threading import Thread
from typing import Literal
from uuid import uuid4

from fastapi import Request
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, ConfigDict, Field, model_validator
from starlette.concurrency import run_in_threadpool

from qwen_lab import (
    F10_ANCHORS, F10_TEXT, MAX_INPUT, PROMPT_BYTES, TEXT_BYTES, LabError, RunInput, Settings,
    action_lock, bounded_text, read_json, require_model, run_with_identity, strict_json,
)


GAME_ID = r"[a-z0-9](?:[a-z0-9-]{0,38}[a-z0-9])?"
SERIES_ID = r"[0-9]{8}-[0-9]{6}-[0-9a-f]{12}"
MAX_GAME = 98_304
MAX_RECEIPT = 3 * 1024 * 1024
MAX_RECORDS = 100
SCHEMA = "1.0.0"
LOGGER = logging.getLogger("uvicorn.error")
DIRECTORY_FLAGS = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW


class Record(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class Quantity(Record):
    value: int | float = Field(ge=0, le=1_000_000_000, allow_inf_nan=False)
    unit: Literal["g", "kg", "ml", "l", "portion"]


class ExpectedMention(Record):
    anchor: str = Field(min_length=1, max_length=512)
    state: Literal["cooked", "raw", "unknown"]
    quantity: Quantity | None


class Case(Record):
    name: str = Field(min_length=1, max_length=100)
    text: str = Field(min_length=1, max_length=TEXT_BYTES)
    expected: list[ExpectedMention] | None = Field(default=None, max_length=12)

    @model_validator(mode="after")
    def validate_anchors(self):
        if not bounded_text(self.name, 300) or not bounded_text(self.text, TEXT_BYTES):
            raise ValueError("invalid_case_text")
        cursor = 0
        for row in self.expected or []:
            start = self.text.find(row.anchor, cursor)
            if not bounded_text(row.anchor, 512) or start < 0:
                raise ValueError("invalid_anchor")
            cursor = start + len(row.anchor)
        return self


class Game(Record):
    schema_version: Literal["1.0.0"] = SCHEMA
    name: str = Field(min_length=1, max_length=100)
    cases: list[Case] = Field(min_length=1, max_length=5)

    @model_validator(mode="after")
    def validate_name(self):
        if not bounded_text(self.name, 300):
            raise ValueError("invalid_game_name")
        return self


class SeriesRequest(Settings):
    game_id: str = Field(min_length=1, max_length=40)


def utcnow():
    return datetime.now(timezone.utc).isoformat()


def expected_digest(expected):
    if expected is None:
        return None
    canonical = json.dumps(expected, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return sha256(canonical.encode("utf-8")).hexdigest()


def regular_file(metadata):
    return stat.S_ISREG(metadata.st_mode) and metadata.st_nlink == 1


class Store:
    def __init__(self, project, port):
        self.project = project
        self.scope = "essai" if port == 8214 else "ecran"
        self.parts = (".local", "qwen-lab", self.scope)

    def path(self, kind, identifier):
        return "/".join((*self.parts, kind, identifier + ".json"))

    @contextmanager
    def directory(self, kind, create=False):
        with ExitStack() as stack:
            folder = os.open(self.project, DIRECTORY_FLAGS)
            stack.callback(os.close, folder)
            for part in (*self.parts, kind):
                if create:
                    try:
                        os.mkdir(part, 0o700, dir_fd=folder)
                    except FileExistsError:
                        pass
                folder = os.open(part, DIRECTORY_FLAGS, dir_fd=folder)
                stack.callback(os.close, folder)
            yield folder

    @staticmethod
    def filename(kind, identifier):
        pattern = GAME_ID if kind == "jeux" else SERIES_ID
        if not re.fullmatch(pattern, identifier):
            raise LabError("qwen_invalid_id", 400)
        return identifier + ".json"

    def entries(self, kind, folder):
        pattern = GAME_ID if kind == "jeux" else SERIES_ID
        maximum = MAX_GAME if kind == "jeux" else MAX_RECEIPT
        with os.scandir(folder) as candidates:
            identifiers = []
            for candidate in candidates:
                identifier, suffix = os.path.splitext(candidate.name)
                if suffix != ".json" or not re.fullmatch(pattern, identifier):
                    continue
                try:
                    metadata = candidate.stat(follow_symlinks=False)
                except FileNotFoundError:
                    continue
                if regular_file(metadata) and metadata.st_size <= maximum:
                    identifiers.append(identifier)
                    if len(identifiers) >= MAX_RECORDS:
                        break
        return sorted(identifiers, reverse=kind == "series")

    def index(self, kind):
        try:
            with self.directory(kind) as folder:
                return self.entries(kind, folder)
        except FileNotFoundError:
            return []
        except OSError:
            raise LabError("qwen_storage_unavailable", 503) from None

    def read(self, kind, identifier):
        filename = self.filename(kind, identifier)
        maximum = MAX_GAME if kind == "jeux" else MAX_RECEIPT
        try:
            with self.directory(kind) as folder:
                fd = os.open(filename, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=folder)
                with os.fdopen(fd, "rb") as source:
                    metadata = os.fstat(source.fileno())
                    # Un remplacement atomique peut délier l’instantané déjà ouvert.
                    if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink > 1 or metadata.st_size > maximum:
                        raise ValueError("Unexpected file")
                    raw = source.read(maximum + 1)
            if len(raw) > maximum:
                raise ValueError("Unexpected file size")
            data = strict_json(raw.decode("utf-8"))
            if kind == "jeux":
                return Game.model_validate(data).model_dump()
            if not isinstance(data, dict) or data.get("id") != identifier or data.get("schema_version") != SCHEMA:
                raise ValueError("Unexpected receipt")
            return data
        except FileNotFoundError:
            raise LabError("qwen_record_not_found", 404) from None
        except (ValueError, RecursionError):
            raise LabError("qwen_invalid_record", 422) from None
        except OSError:
            raise LabError("qwen_storage_unavailable", 503) from None

    def write(self, kind, identifier, data):
        name = self.filename(kind, identifier)
        maximum = MAX_GAME if kind == "jeux" else MAX_RECEIPT
        body = (json.dumps(data, ensure_ascii=False, allow_nan=False, indent=2) + "\n").encode("utf-8")
        if len(body) > maximum:
            raise LabError("request_too_large", 413)
        try:
            with self.directory(kind, create=True) as folder:
                # Le même verrou de répertoire couvre le quota et la publication atomique.
                fcntl.flock(folder, fcntl.LOCK_EX)
                try:
                    existing = os.stat(name, dir_fd=folder, follow_symlinks=False)
                    if not regular_file(existing) or existing.st_size > maximum:
                        raise LabError("qwen_invalid_record", 422)
                except FileNotFoundError:
                    if len(self.entries(kind, folder)) >= MAX_RECORDS:
                        raise LabError("qwen_storage_full", 409) from None
                temporary = ".tmp-" + uuid4().hex
                fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                             0o600, dir_fd=folder)
                try:
                    with os.fdopen(fd, "wb") as target:
                        target.write(body)
                        target.flush()
                        os.fsync(target.fileno())
                    os.replace(temporary, name, src_dir_fd=folder, dst_dir_fd=folder)
                    os.fsync(folder)
                finally:
                    try:
                        os.unlink(temporary, dir_fd=folder)
                    except FileNotFoundError:
                        pass
        except OSError:
            raise LabError("qwen_storage_unavailable", 503) from None


def comparison(expected, outcome):
    checks = outcome["checks"]
    if not checks["json"] or not checks["structure"] or outcome["done_reason"] == "length":
        return {"verdict": "structure_error", "expected": expected, "differences": []}
    if expected is None:
        verdict = "exploratory" if checks["citations"] else "citation_error"
        return {"verdict": verdict, "expected": None, "differences": []}
    differences = []
    for index, (reference, actual) in enumerate(zip_longest(expected, outcome["mentions"]), 1):
        observed = None if actual is None or actual["value"] is None else {
            "value": actual["value"], "unit": actual["unit"],
        }
        quantity = reference["quantity"] if reference is not None else None
        quantity_ok = reference is not None and actual is not None and (
            (observed is None and quantity is None)
            or (observed is not None and quantity is not None and observed["unit"] == quantity["unit"]
                and Decimal(observed["value"]) == Decimal(str(quantity["value"])))
        )
        checks_row = {
            "position": index,
            "expected": reference,
            "observed": None if actual is None else {"quote": actual["quote"], "state": actual["state"],
                                                       "quantity": observed, "verbatim": actual["verbatim"]},
            "anchor_ok": reference is not None and actual is not None and actual["verbatim"]
            and reference["anchor"] in actual["quote"],
            "quantity_ok": quantity_ok,
            "state_ok": reference is not None and actual is not None and reference["state"] == actual["state"],
        }
        differences.append(checks_row)
    exact = all(row["anchor_ok"] and row["quantity_ok"] and row["state_ok"] for row in differences)
    verdict = "citation_error" if not checks["citations"] else "success" if exact else "oracle_failed"
    return {"verdict": verdict, "expected": expected, "differences": differences}


def execute_series(store, receipt):
    model_digest = None
    try:
        for case in receipt["game"]["cases"]:
            started = utcnow()
            args = RunInput(**receipt["settings"], text=case["text"])
            try:
                installed = require_model()
                digest = installed.get("digest")
                if model_digest is not None and digest != model_digest:
                    raise LabError("qwen_model_changed", 409)
                model_digest = digest
                outcome = run_with_identity(args, installed)
                evaluation = comparison(case["expected"], outcome)
                error = None
            except LabError as cause:
                outcome = None
                evaluation = {"verdict": "interrupted", "expected": case["expected"], "differences": []}
                error = cause.code
            receipt["results"].append({"name": case["name"], "started_at": started, "finished_at": utcnow(),
                                       "outcome": outcome, "evaluation": evaluation, "error": error})
            store.write("series", receipt["id"], receipt)
        receipt["status"] = "completed"
    except LabError as cause:
        receipt["status"] = "interrupted"
        receipt["error"] = cause.code
    receipt["finished_at"] = utcnow()
    store.write("series", receipt["id"], receipt)


def install_sets(app, authorized, project: Path, port):
    store = Store(project, port)
    lock_path = project / ".local/ecran-qwen.lock"
    running = set()
    git_sha = os.environ.get("LLMSPORT_QWEN_GIT_SHA", "")
    lab = {
        "git_sha": git_sha if re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", git_sha) else None,
        "python_sha256": {
            name: sha256(Path(__file__).with_name(name).read_bytes()).hexdigest()
            for name in ("qwen_lab.py", "qwen_sets.py", "qwen_measure.py")
        },
    }

    async def guarded(request, handler):
        if not authorized(request):
            return Response(status_code=403)
        if request.url.query:
            return JSONResponse({"error": "invalid_request"}, status_code=400)
        try:
            return await handler()
        except LabError as cause:
            return JSONResponse({"error": cause.code}, status_code=cause.status)
        except (ValueError, RecursionError):
            return JSONResponse({"error": "qwen_invalid_record"}, status_code=400)

    @app.get("/internal/qwen/jeux", include_in_schema=False)
    async def games(request: Request):
        async def fetch():
            return {
                "ids": await run_in_threadpool(store.index, "jeux"),
                "directory": "/".join(store.parts),
                "f10": {"name": "F10 · Riz corrigé et poulet maintenu", "text": F10_TEXT, "expected": [
                    {"anchor": anchor, "state": "cooked", "quantity": {"value": 100, "unit": "g"}}
                    for anchor in F10_ANCHORS
                ]},
            }
        return await guarded(request, fetch)

    @app.get("/internal/qwen/jeux/{identifier}", include_in_schema=False)
    async def game(request: Request, identifier: str):
        async def fetch():
            return await run_in_threadpool(store.read, "jeux", identifier)
        return await guarded(request, fetch)

    @app.post("/internal/qwen/jeux/{identifier}", include_in_schema=False)
    async def save(request: Request, identifier: str):
        async def persist():
            store.filename("jeux", identifier)
            body = Game.model_validate(await read_json(request, MAX_GAME)).model_dump()
            await run_in_threadpool(store.write, "jeux", identifier, body)
            return {"id": identifier, "path": store.path("jeux", identifier)}
        return await guarded(request, persist)

    @app.get("/internal/qwen/series", include_in_schema=False)
    async def series_list(request: Request):
        async def fetch():
            return {"ids": await run_in_threadpool(store.index, "series")}
        return await guarded(request, fetch)

    @app.get("/internal/qwen/series/{identifier}", include_in_schema=False)
    async def series(request: Request, identifier: str):
        async def fetch():
            was_running = identifier in running
            receipt = await run_in_threadpool(store.read, "series", identifier)
            if receipt.get("status") == "running" and not was_running and identifier not in running:
                receipt["status"] = "interrupted"
            return receipt
        return await guarded(request, fetch)

    def background(lease, receipt):
        try:
            execute_series(store, receipt)
        except LabError:
            # Le dernier instantané reste lisible et sera présenté comme interrompu.
            LOGGER.warning("Écriture interrompue pour la série Qwen %s", receipt["id"])
        finally:
            lease.close()
            running.discard(receipt["id"])

    @app.post("/internal/qwen/series", status_code=202, include_in_schema=False)
    async def launch(request: Request):
        async def start():
            arguments = SeriesRequest.model_validate(await read_json(request, MAX_INPUT))
            if not bounded_text(arguments.prompt, PROMPT_BYTES):
                raise LabError("invalid_request", 400)
            game_data = await run_in_threadpool(store.read, "jeux", arguments.game_id)
            with ExitStack() as lease:
                lease.enter_context(action_lock(lock_path))
                identifier = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-") + uuid4().hex[:12]
                receipt = {"schema_version": SCHEMA, "id": identifier, "game_id": arguments.game_id,
                           "game": game_data, "settings": arguments.model_dump(exclude={"game_id"}), "lab": lab,
                           "expected_sha256": [expected_digest(case["expected"]) for case in game_data["cases"]],
                           "status": "running", "started_at": utcnow(), "finished_at": None, "results": []}
                running.add(identifier)
                try:
                    await run_in_threadpool(store.write, "series", identifier, receipt)
                    worker_lease = lease.pop_all()
                    try:
                        Thread(target=background, args=(worker_lease, receipt), daemon=True).start()
                    except RuntimeError:
                        worker_lease.close()
                        raise LabError("qwen_backend_unavailable", 503) from None
                except BaseException:
                    running.discard(identifier)
                    raise
            return {"id": identifier, "path": store.path("series", identifier)}
        return await guarded(request, start)
