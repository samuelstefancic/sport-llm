"""Laboratoire d'extraction local, monté uniquement par le lanceur de l'écran."""

import asyncio
import fcntl
import hmac
import http.client
import json
import os
import re
import socket
import threading
import time
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Literal

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from starlette.concurrency import run_in_threadpool
from starlette.requests import ClientDisconnect

from qwen_measure import RssSampler, server_identity


OLLAMA_HOST = "127.0.0.1"
OLLAMA_PORT = 11434
MODEL = "qwen3:4b"
KEEP_ALIVE = "2m"
CONTEXT_TOKENS = 2048
TIMEOUT = 60
CONTROL_TIMEOUT = 2
MAX_INPUT = 24_576
MAX_OLLAMA_RESPONSE = 131_072
TEXT_BYTES = 4_096
PROMPT_BYTES = 8_192
MAX_TOKENS = 512
F10_TEXT = "Correction du repas : pour le riz cuit, 100 g et non 150 g ; le poulet cuit reste à 100 g."
F10_ANCHORS = ("riz cuit, 100 g et non 150 g", "poulet cuit reste à 100 g")
CITATION_PROMPT = """Extrais les faits explicitement déclarés dans le texte français. Réponds avec un seul objet JSON, sans balises Markdown, commentaire ni autre clé.

Utilise exactement : {"mentions":[{"text":"citation","state":"unknown","quantity":null}]}. Une mention par aliment, dans l’ordre du texte. « text » est une citation contiguë, recopiée à l’identique, qui contient l’aliment, son état et sa quantité s’ils sont écrits. Les citations des différents aliments ne se chevauchent pas. « state » vaut "cooked", "raw" ou "unknown" selon le texte. « quantity » vaut null si aucune quantité avec unité n’est déclarée, sinon {"value":nombre,"unit":unité} avec unité parmi "g", "kg", "ml", "l", "portion". Un bol déclaré vaut une portion, sans lui attribuer de masse. Si le texte corrige un aliment, garde la nouvelle quantité et cite aussi le passage qui exclut l’ancienne. Pour un aliment maintenu, cite le passage qui dit qu’il reste à la même quantité. Ignore les demandes d’affichage et les références de catalogue.

Conserve les unités écrites et les zéros déclarés. Une virgule décimale dans la citation s’écrit avec un point dans le nombre JSON. N’invente aucune quantité, unité ou état. Ne convertis rien. Ne calcule aucun total ni apport alimentaire."""

REFERENCE_PROMPT = """Extrais les faits explicitement déclarés dans le texte français. Réponds avec un seul objet JSON, sans balises Markdown, commentaire ni autre clé. Le domaine est fourni.

Pour « meal », utilise exactement : {"mentions":[{"text":"citation","state":"unknown","quantity":null}]}. Une mention par aliment, dans l’ordre du texte. « text » est une citation contiguë, recopiée à l’identique, qui contient l’aliment, son état et sa quantité s’ils sont écrits. Les citations des différents aliments ne se chevauchent pas. « state » vaut "cooked", "raw" ou "unknown" selon le texte. « quantity » vaut null si aucune quantité avec unité n’est déclarée, sinon {"value":nombre,"unit":unité} avec unité parmi "g", "kg", "ml", "l", "portion". Un bol déclaré vaut une portion, sans lui attribuer de masse. Si le texte corrige un aliment, garde la nouvelle quantité et cite aussi le passage qui exclut l’ancienne. Pour un aliment maintenu, cite le passage qui dit qu’il reste à la même quantité. Ignore les demandes d’affichage et les références de catalogue.

Pour « workout », utilise exactement : {"activity":"running","measures":[{"id":"duration","value":15,"unit":"min","text":"15 min"}]}. « activity » vaut "running" (course), "cycling" (vélo), "squat", "mobility" ou null. « measures » contient les mesures individuelles dans l’ordre du texte, ou [] quand aucune n’est donnée. Pour « id », utilise "duration", "distance", "sets", "repetitions" ou "load". Les unités admises sont "s", "min", "h" pour une durée, "m", "km" pour une distance, "count" pour des séries ou des répétitions, et "kg" pour une charge. Garde le nombre écrit avec "unit":null si l’unité de la mesure manque. Par convention, un nombre seul juste après un verbe de déplacement désigne une distance à préciser, d’unité null. La clé « text » recopie à l’identique une citation contiguë qui contient le nombre et son unité si présente. Garde les mesures corrigées et ignore les anciennes valeurs explicitement écartées.

Conserve les unités écrites et les zéros déclarés. Une virgule décimale dans la citation s’écrit avec un point dans le nombre JSON. Extrais ce qui a été consommé ou réalisé, sans inclure un objectif non réalisé. N’invente aucune quantité, unité, activité ou état. Ne convertis rien. Ne calcule aucun total, apport alimentaire ni dépense énergétique.
"""

PASSAGE_PROMPT = """Extrais les aliments déclarés dans les passages numérotés. Réponds avec un seul objet JSON de forme {"mentions":[{"passage_id":"p1","state":"unknown","quantity":null}]}.
Choisis l'identifiant d'un passage qui contient la déclaration complète pertinente pour chaque aliment. Garde l’ordre du texte. Utilise l’identifiant tel qu’il est fourni. L’état vaut "cooked", "raw" ou "unknown". La quantité est null si elle manque, sinon {"value":nombre,"unit":unité} avec une unité parmi "g", "kg", "ml", "l", "portion". Si une quantité est corrigée, prends la quantité retenue et sélectionne le passage qui conserve aussi le rejet de l’ancienne. Pour un aliment maintenu, sélectionne le passage qui l’indique. N’invente aucune mesure et ne convertis rien."""
PROMPTS = {"reference": REFERENCE_PROMPT, "citations": CITATION_PROMPT, "passages": PASSAGE_PROMPT}
PASSAGE_DELIMITERS = re.compile(r"[;!?\n]|(?<!\d)\.|\.(?!\d)")


class RunInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    mode: Literal["reference", "citations", "passages"]
    text: str = Field(min_length=1, max_length=TEXT_BYTES)
    prompt: str = Field(min_length=1, max_length=PROMPT_BYTES)
    temperature: float = Field(ge=0, le=1, allow_inf_nan=False)
    max_tokens: int = Field(ge=1, le=MAX_TOKENS)


class LabError(Exception):
    def __init__(self, code, status):
        self.code = code
        self.status = status


def reject_constant(_):
    raise ValueError("Invalid JSON number")


def unique_keys(pairs):
    record = dict(pairs)
    if len(record) != len(pairs):
        raise ValueError("Duplicate JSON key")
    return record


def strict_json(raw, **options):
    return json.loads(raw, object_pairs_hook=unique_keys, parse_constant=reject_constant, **options)


def interrupt_socket(sock):
    try:
        sock.shutdown(socket.SHUT_RDWR)
    except OSError:
        pass


def ollama(path, payload=None, timeout=CONTROL_TIMEOUT):
    connection = http.client.HTTPConnection(OLLAMA_HOST, OLLAMA_PORT, timeout=min(timeout, CONTROL_TIMEOUT))
    timer = None
    deadline = time.monotonic() + timeout
    try:
        connection.connect()
        # Fermer la lecture sur le même socket à l'échéance, même si le serveur envoie au compte-gouttes.
        timer = threading.Timer(max(0, deadline - time.monotonic()), interrupt_socket, args=(connection.sock,))
        timer.start()
        connection.sock.settimeout(timeout)
        body = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
        connection.request("GET" if body is None else "POST", path, body, {"Content-Type": "application/json"})
        with connection.getresponse() as response:
            if response.status != 200:
                raise LabError("ollama_http_error", 502)
            length = response.length
            if length is not None and length > MAX_OLLAMA_RESPONSE:
                raise LabError("ollama_response_too_large", 502)
            raw = response.read(MAX_OLLAMA_RESPONSE + 1)
            if time.monotonic() >= deadline:
                raise LabError("ollama_timeout", 504)
            if len(raw) > MAX_OLLAMA_RESPONSE:
                raise LabError("ollama_response_too_large", 502)
            if length is not None and len(raw) != length:
                raise LabError("ollama_invalid_response", 502)
        value = strict_json(raw.decode("utf-8"))
        if not isinstance(value, dict):
            raise ValueError("Expected an object")
        return value
    except TimeoutError:
        raise LabError("ollama_timeout", 504) from None
    except (OSError, http.client.HTTPException):
        if time.monotonic() >= deadline:
            raise LabError("ollama_timeout", 504) from None
        raise LabError("ollama_unavailable", 503) from None
    except (ValueError, RecursionError):
        raise LabError("ollama_invalid_response", 502) from None
    finally:
        if timer:
            timer.cancel()
            timer.join()
        connection.close()


def model_entry(path):
    models = ollama(path).get("models")
    if not isinstance(models, list) or any(
        not isinstance(item, dict) or not isinstance(item.get("name"), str) for item in models
    ):
        raise LabError("ollama_invalid_response", 502)
    return next((item for item in models if item["name"] == MODEL), None)


def status():
    installed = None
    resident = None
    digest = None
    error = None
    try:
        entry = model_entry("/api/tags")
        installed = entry is not None
        digest = entry.get("digest") if installed else None
    except LabError as exc:
        error = exc.code
    try:
        running = model_entry("/api/ps")
        resident = running is not None
        if resident and digest and running.get("digest") != digest:
            resident = None
    except LabError as exc:
        error = error or exc.code
    return {
        "model": MODEL,
        "host": OLLAMA_HOST,
        "port": OLLAMA_PORT,
        "installed": installed,
        "resident": resident,
        "error": error,
        "example": {"id": "F10", "revision": 2, "text": F10_TEXT},
        "prompts": PROMPTS,
        "limits": {"text_bytes": TEXT_BYTES, "prompt_bytes": PROMPT_BYTES, "max_tokens": MAX_TOKENS},
    }



def passages_for(text):
    parts = (part.strip() for part in PASSAGE_DELIMITERS.split(text))
    return {f"p{index}": part for index, part in enumerate(filter(None, parts), 1)}


def valid_mention(item, source_key):
    if not isinstance(item, dict) or set(item) != {source_key, "state", "quantity"}:
        return False
    if not isinstance(item[source_key], str) or not item[source_key].strip():
        return False
    if item["state"] not in ("cooked", "raw", "unknown"):
        return False
    quantity = item["quantity"]
    if quantity is None:
        return True
    if not isinstance(quantity, dict) or set(quantity) != {"value", "unit"}:
        return False
    return (
        type(quantity["value"]) in (int, Decimal)
        and quantity["value"] >= 0
        and quantity["unit"] in ("g", "kg", "ml", "l", "portion")
    )


def validate_extraction(raw, text, done_reason, passages=None):
    applicable = text == F10_TEXT
    checks = {"json": False, "structure": None, "citations": None,
              "oracle_f10": "not_evaluated" if applicable else "not_applicable"}
    errors, rows = [], []
    try:
        extraction = strict_json(raw, parse_float=Decimal)
        checks["json"] = True
    except (ValueError, InvalidOperation, RecursionError):
        return checks, ["La sortie doit être un seul objet JSON, sans clé dupliquée."], rows
    source_key = "text" if passages is None else "passage_id"
    mentions = extraction.get("mentions") if isinstance(extraction, dict) else None
    checks["structure"] = (
        isinstance(mentions, list) and len(mentions) <= 64 and set(extraction) == {"mentions"}
        and all(valid_mention(item, source_key) for item in mentions)
    )
    if not checks["structure"]:
        return checks, [f"Forme attendue : un objet « mentions » avec les champs {source_key}, state et quantity."], rows
    cursor = 0
    checks["citations"] = True
    if applicable and len(mentions) != len(F10_ANCHORS):
        errors.append("F10 attend deux mentions, dans l’ordre riz puis poulet.")
    for index, mention in enumerate(mentions):
        passage_id = mention[source_key] if passages is not None else None
        quote = mention["text"] if passages is None else passages.get(passage_id)
        quantity = mention["quantity"]
        start = -1 if quote is None else text.find(quote, cursor)
        reasons = []
        if start < 0:
            reasons.append("Passage inconnu." if quote is None else "Citation contiguë verbatim, ordonnée et sans chevauchement introuvable.")
            checks["citations"] = False
        else:
            cursor = start + len(quote)
        anchor_ok, quantity_ok, state_ok = None, None, None
        anchor = F10_ANCHORS[index] if applicable and index < len(F10_ANCHORS) else None
        if anchor:
            anchor_ok = start >= 0 and anchor in quote
            quantity_ok = quantity == {"value": 100, "unit": "g"}
            state_ok = mention["state"] == "cooked"
            if not anchor_ok:
                reasons.append(f"Citation intégrale attendue : « {anchor} ».")
            if not quantity_ok:
                reasons.append("Quantité retenue attendue : 100 g.")
            if not state_ok:
                reasons.append("État attendu : cuit.")
        if reasons:
            errors.append(f"Mention {index + 1} : " + " ".join(reasons))
        rows.append({
            "passage_id": passage_id, "quote": quote, "state": mention["state"],
            "value": str(quantity["value"]) if quantity is not None else None,
            "unit": quantity["unit"] if quantity is not None else None,
            "verbatim": start >= 0, "anchor_ok": anchor_ok, "quantity_ok": quantity_ok, "state_ok": state_ok,
            "expected_food": ("riz", "poulet")[index] if anchor else None,
            "reasons": reasons,
        })
    if done_reason == "length":
        errors.append("Ollama indique que le plafond de génération a été atteint.")
    if applicable:
        checks["oracle_f10"] = "fail" if errors else "pass"
    return checks, errors, rows


def counter(reply, key):
    value = reply.get(key)
    return value if type(value) is int and 0 <= value <= (1 << 53) - 1 else None


def run_once(args):
    passages = passages_for(args.text) if args.mode == "passages" else None
    if passages is not None and (not passages or len(passages) > 40):
        raise LabError("invalid_passages", 400)
    source = f"Domaine : meal\nTexte : {args.text}"
    if passages is not None:
        source = "Domaine : meal\nPassages : " + json.dumps(passages, ensure_ascii=False)
    payload = {
        "model": MODEL, "stream": False, "think": False, "format": "json", "keep_alive": KEEP_ALIVE,
        "messages": [
            {"role": "system", "content": args.prompt},
            {"role": "user", "content": source},
        ],
        "options": {"temperature": args.temperature, "seed": 42, "num_ctx": CONTEXT_TOKENS, "num_predict": args.max_tokens},
    }
    with RssSampler(server_identity()) as rss:
        started = time.perf_counter_ns()
        reply = ollama("/api/chat", payload, TIMEOUT)
        wall_ns = time.perf_counter_ns() - started
    message = reply.get("message")
    raw = message.get("content") if isinstance(message, dict) else None
    if reply.get("model") != MODEL or reply.get("done") is not True or not isinstance(raw, str):
        raise LabError("ollama_invalid_response", 502)
    try:
        raw.encode("utf-8")
    except UnicodeError:
        raise LabError("ollama_invalid_response", 502) from None
    stop = reply.get("done_reason")
    stop = stop if stop in ("stop", "length") else None
    checks, errors, rows = validate_extraction(raw, args.text, stop, passages)
    tokens = counter(reply, "eval_count")
    eval_ns = counter(reply, "eval_duration")
    return {
        "raw": raw, "checks": checks, "errors": errors, "done_reason": stop,
        "mentions": rows, "passages": passages,
        "generation": {key: payload[key] for key in ("options", "stream", "think", "format", "keep_alive")},
        "metrics": {
            "wall_ns": wall_ns, "ollama_total_ns": counter(reply, "total_duration"),
            "ollama_load_ns": counter(reply, "load_duration"), "prompt_tokens": counter(reply, "prompt_eval_count"),
            "output_tokens": tokens, "output_tokens_per_s": tokens * 1e9 / eval_ns if tokens is not None and eval_ns else None,
            **rss.result(),
        },
    }


def perform(operation, data, lock_path):
    try:
        descriptor = os.open(lock_path, os.O_CREAT | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
    except OSError:
        raise LabError("qwen_lock_unavailable", 503) from None
    with os.fdopen(descriptor, "wb") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise LabError("qwen_busy", 409) from None
        except OSError:
            raise LabError("qwen_lock_unavailable", 503) from None
        installed = model_entry("/api/tags")
        if installed is None:
            raise LabError("qwen_not_installed", 409)
        if operation == "run":
            try:
                version = ollama("/api/version").get("version")
            except LabError:
                version = None
            digest = installed.get("digest")
            result = run_once(data)
            result["model"] = {
                "name": MODEL,
                "digest": digest if isinstance(digest, str) and len(digest) <= 128 else None,
                "ollama_version": version if isinstance(version, str) and len(version) <= 80 else None,
            }
            return result
        reply = ollama(
            "/api/generate",
            {"model": MODEL, "prompt": "", "stream": False, "keep_alive": KEEP_ALIVE,
             "options": {"num_ctx": CONTEXT_TOKENS, "num_predict": 1}},
            TIMEOUT,
        )
        if reply.get("model") != MODEL or reply.get("done") is not True:
            raise LabError("ollama_invalid_response", 502)
        return {"accepted": True}


async def read_input(request, operation):
    content_types = request.headers.getlist("content-type")
    if len(content_types) != 1 or content_types[0].partition(";")[0].strip().lower() != "application/json":
        raise LabError("json_required", 415)
    body = bytearray()
    try:
        async with asyncio.timeout(3):
            async for chunk in request.stream():
                if len(body) + len(chunk) > MAX_INPUT:
                    raise LabError("request_too_large", 413)
                body.extend(chunk)
        data = strict_json(body.decode("utf-8"))
        if operation == "load" and data == {}:
            return None
        if operation == "run":
            arguments = RunInput.model_validate(data)
            for value, maximum in ((arguments.text, TEXT_BYTES), (arguments.prompt, PROMPT_BYTES)):
                if not value.strip() or len(value.encode("utf-8")) > maximum:
                    raise ValueError("Invalid text")
            return arguments
    except TimeoutError:
        raise LabError("input_timeout", 408) from None
    except (ValueError, RecursionError, ClientDisconnect):
        raise LabError("invalid_request", 400) from None
    raise LabError("invalid_request", 400)


def install(app, port, token):
    lock_path = Path(__file__).resolve().parents[1] / ".local/ecran-qwen.lock"
    host = f"127.0.0.1:{port}"

    def authorized(request):
        candidate = request.headers.getlist("x-llmsport-qwen")
        return (
            request.headers.getlist("host") == [host]
            and "origin" not in request.headers
            and len(candidate) == 1
            and hmac.compare_digest(candidate[0].encode("latin-1"), token)
        )

    @app.get("/internal/qwen/status", include_in_schema=False)
    async def get_status(request: Request):
        if not authorized(request):
            return Response(status_code=403)
        if request.url.query:
            return JSONResponse({"error": "invalid_request"}, status_code=400)
        return await run_in_threadpool(status)

    @app.post("/internal/qwen/{operation}", include_in_schema=False)
    async def post_action(request: Request, operation: Literal["load", "run"]):
        if not authorized(request):
            return Response(status_code=403)
        if request.url.query:
            return JSONResponse({"error": "invalid_request"}, status_code=400)
        try:
            data = await read_input(request, operation)
            return await run_in_threadpool(perform, operation, data, lock_path)
        except LabError as exc:
            return JSONResponse({"error": exc.code}, status_code=exc.status)
