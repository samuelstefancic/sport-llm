"""Vérifications simulées, sans serveur Ollama et sans modèle."""

import asyncio
import fcntl
import json
from pathlib import Path
import socket
import sys
from tempfile import TemporaryDirectory
import threading
import time
import unittest
from unittest.mock import patch

from fastapi import FastAPI

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "python"))
import qwen_lab as lab
import qwen_measure as measure


F10 = "Correction du repas : pour le riz cuit, 100 g et non 150 g ; le poulet cuit reste à 100 g."
RICE = "riz cuit, 100 g et non 150 g"
CHICKEN = "poulet cuit reste à 100 g"
BODY = {"mode": "reference", "text": F10, "prompt": "Consigne fictive", "temperature": 0, "max_tokens": 256}
TOKEN = "0" * 64


def item(citation, value=100, unit="g"):
    return {"text": citation, "state": "cooked", "quantity": {"value": value, "unit": unit}}


def native(*items):
    return json.dumps({"mentions": items}, ensure_ascii=False)


def assess(raw, text=F10, reason="stop", passages=None):
    return lab.validate_extraction(raw, text, reason, passages)


class ExtractionTests(unittest.TestCase):
    def test_f10_literals_match_versioned_development_case(self):
        cases_path = Path(__file__).resolve().parents[1] / "data/dev/cases.json"
        case = next(case for case in json.loads(cases_path.read_text())["cases"] if case["id"] == "F10")
        self.assertTrue(case["fictitious"])
        self.assertEqual(case["expected"]["meal_revision"], 2)
        self.assertEqual(case["input"], lab.F10_TEXT)

    def test_exact_citations_and_quantities_pass(self):
        checks, errors, rows = assess(native(item(RICE), item(CHICKEN)))
        self.assertEqual(checks, {"json": True, "structure": True, "citations": True, "oracle_f10": "pass"})
        self.assertEqual(errors, [])
        self.assertTrue(all(row["anchor_ok"] and row["quantity_ok"] for row in rows))

    def test_both_quantities_do_not_compensate_for_missing_exclusion(self):
        checks, errors, rows = assess(native(item("riz cuit, 100 g"), item("poulet cuit reste à 100 g")))
        self.assertEqual(checks["oracle_f10"], "fail")
        self.assertTrue(rows[0]["verbatim"])
        self.assertFalse(rows[0]["anchor_ok"])
        self.assertTrue(rows[0]["quantity_ok"])
        self.assertIn("et non 150 g", errors[0])

    def test_wrong_value_is_independent_from_correct_citation(self):
        checks, _, rows = assess(native(item(RICE, 150), item(CHICKEN)))
        self.assertEqual(checks["oracle_f10"], "fail")
        self.assertTrue(rows[0]["anchor_ok"])
        self.assertFalse(rows[0]["quantity_ok"])

    def test_reject_duplicate_keys_and_reversed_overlapping_or_truncated_citations(self):
        duplicate = '{"mentions":[],"mentions":[]}'
        self.assertFalse(assess(duplicate)[0]["json"])
        self.assertFalse(assess(native(item(CHICKEN), item(RICE)))[0]["citations"])
        self.assertFalse(assess(native(item(F10), item(CHICKEN)))[0]["citations"])
        self.assertEqual(assess(native(item(RICE), item(CHICKEN)), reason="length")[0]["oracle_f10"], "fail")
        self.assertFalse(assess(native(item(RICE, True), item(CHICKEN)))[0]["structure"])

    def test_modified_text_has_no_f10_oracle(self):
        checks, _, rows = assess(native(item(RICE), item(CHICKEN)), text=F10 + " ")
        self.assertEqual(checks["oracle_f10"], "not_applicable")
        self.assertTrue(checks["citations"])
        self.assertIsNone(rows[0]["anchor_ok"])

    def test_passages_copy_literal_clauses_and_reject_unknown_ids(self):
        passages = lab.passages_for(F10)
        self.assertEqual(passages, {"p1": "Correction du repas : pour le " + RICE, "p2": "le " + CHICKEN})
        self.assertEqual(lab.passages_for("5.5 g et 1,5 l. Puis 2 kg."), {"p1": "5.5 g et 1,5 l", "p2": "Puis 2 kg"})
        first, second = ({"passage_id": identifier, "state": "cooked", "quantity": {"value": 100, "unit": "g"}}
                         for identifier in ("p1", "p2"))
        checks, _, rows = assess(native(first, second), passages=passages)
        self.assertEqual(checks["oracle_f10"], "pass")
        self.assertEqual([row["quote"] for row in rows], list(passages.values()))
        checks, _, rows = assess(native(dict(first, passage_id="p99"), second), passages=passages)
        self.assertEqual(checks["oracle_f10"], "fail")
        self.assertIsNone(rows[0]["quote"])
        self.assertFalse(checks["citations"])


    def test_identical_passages_require_the_original_id_order_without_reuse(self):
        text = "riz 100 g ; riz 100 g"
        passages = lab.passages_for(text)
        self.assertEqual(passages, {"p1": "riz 100 g", "p2": "riz 100 g"})
        examples = [
            (("p2", "p1"), False),
            (("p1", "p1"), False),
            (("p1", "p2"), True),
        ]
        for identifiers, valid in examples:
            with self.subTest(identifiers=identifiers):
                raw = native(*({"passage_id": identifier, "state": "unknown", "quantity": None}
                               for identifier in identifiers))
                checks, _, rows = assess(raw, text=text, passages=passages)
                self.assertTrue(checks["structure"])
                self.assertEqual([row["passage_id"] for row in rows], list(identifiers))
                self.assertEqual([row["quote"] for row in rows], ["riz 100 g"] * 2)
                self.assertEqual(checks["citations"], valid)
                self.assertEqual([row["verbatim"] for row in rows], [True, valid])


async def request(app, operation, method="POST", body=b"{}", host="127.0.0.1:8214", token=TOKEN,
                  origin=None, content_type="application/json", query=b"", details=False):
    headers = [(b"host", host.encode()), (b"content-type", content_type.encode())]
    if token is not None:
        headers.append((b"x-llmsport-qwen", token.encode()))
    if origin is not None:
        headers.append((b"origin", origin.encode()))
    scope = {
        "type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1",
        "method": method, "scheme": "http", "path": "/internal/qwen/" + operation,
        "query_string": query, "headers": headers,
    }
    messages = []

    async def receive():
        return {"type": "http.request", "body": body}

    async def send(message):
        messages.append(message)

    await app(scope, receive, send)
    status = messages[0]["status"]
    if details:
        raw = b"".join(message.get("body", b"") for message in messages[1:])
        return status, json.loads(raw) if raw else None
    return status


class BoundaryTests(unittest.TestCase):
    def setUp(self):
        self.app = FastAPI()
        lab.install(self.app, 8214, TOKEN.encode())

    def request(self, *args, **kwargs):
        return asyncio.run(request(self.app, *args, **kwargs))

    def test_internal_routes_require_opt_in_and_authenticated_local_proxy(self):
        self.assertEqual(asyncio.run(request(FastAPI(), "status", "GET")), 404)
        cases = [
            {"token": None}, {"token": "f" * 64}, {"host": "attacker.example:8214"},
            {"origin": "http://127.0.0.1:8213"}, {"origin": "null"},
        ]
        with patch.object(lab, "perform") as perform:
            for case in cases:
                with self.subTest(case=case):
                    self.assertEqual(self.request("load", **case), 403)
            perform.assert_not_called()
        with patch.object(lab, "status", return_value={}) as status:
            self.assertEqual(self.request("status", "GET"), 200)
            status.assert_called_once()

    def test_input_bounds_before_ollama(self):
        invalid = [
            ({"content_type": "text/plain"}, 415), ({"body": b" " * (lab.MAX_INPUT + 1)}, 413),
            ({"body": b'{"text": 1, "text": 2}'}, 400), ({"query": b"model=elsewhere"}, 400),
        ]
        for change in ({"max_tokens": 513}, {"temperature": 1.01}, {"model": "other"},
                       {"mode": "other"}, {"max_tokens": True}, {"text": "é" * 3000}, {"text": "   "}):
            invalid.append(({"body": json.dumps(dict(BODY, **change), ensure_ascii=False).encode()}, 400))
        with patch.object(lab, "perform") as perform:
            for case, code in invalid:
                with self.subTest(code=code, length=len(case.get("body", b""))):
                    self.assertEqual(self.request("run", **case), code)
            perform.assert_not_called()
            perform.return_value = {}
            self.assertEqual(self.request("run", body=json.dumps(BODY).encode()), 200)
            self.assertEqual(perform.call_args.args[1].mode, "reference")

    def test_common_lock_refuses_second_action_and_prevents_work_if_model_is_absent(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "local.lock"
            with path.open("w") as lock, patch.object(lab, "ollama") as ollama:
                fcntl.flock(lock, fcntl.LOCK_EX)
                with self.assertRaises(lab.LabError) as busy:
                    lab.perform("load", None, path)
                self.assertEqual(busy.exception.code, "qwen_busy")
                ollama.assert_not_called()
            with patch.object(lab, "ollama", return_value={"models": []}) as ollama:
                with self.assertRaises(lab.LabError) as missing:
                    lab.perform("load", None, path)
                self.assertEqual(missing.exception.code, "qwen_not_installed")
                ollama.assert_called_once_with("/api/tags")

    def test_load_wires_only_an_empty_prompt_and_fixed_model(self):
        reply = {"model": lab.MODEL, "done": True}
        with TemporaryDirectory() as directory, patch.object(lab, "ollama", side_effect=[
            {"models": [{"name": lab.MODEL, "digest": "test"}]}, reply,
        ]) as ollama:
            self.assertEqual(lab.perform("load", None, Path(directory) / "local.lock"), {"accepted": True})
        path, body, _ = ollama.call_args.args
        self.assertEqual((path, body["model"], body["prompt"]), ("/api/generate", "qwen3:4b", ""))

    def test_run_records_model_identity_for_manual_export(self):
        digest = "1" * 64
        with TemporaryDirectory() as directory, patch.object(lab, "ollama", side_effect=[
            {"models": [{"name": lab.MODEL, "digest": digest}]}, {"version": "0.20.0"},
        ]) as ollama, patch.object(lab, "run_once", return_value={"raw": "{}"}):
            result = lab.perform("run", lab.RunInput(**BODY), Path(directory) / "local.lock")
        self.assertEqual(result["model"], {"name": "qwen3:4b", "digest": digest, "ollama_version": "0.20.0"})
        self.assertEqual([call.args[0] for call in ollama.call_args_list], ["/api/tags", "/api/version"])

    def test_run_payload_and_real_zero_vs_absent_metrics(self):
        reply = {"model": lab.MODEL, "done": True, "message": {"content": native(item(RICE), item(CHICKEN))},
                 "eval_count": 20, "eval_duration": 2_000_000_000, "load_duration": 0}
        with patch.object(lab, "server_identity", return_value=None), patch.object(lab, "ollama", return_value=reply) as call:
            result = lab.run_once(lab.RunInput(**BODY))
        endpoint, body, timeout = call.call_args.args
        self.assertEqual((endpoint, body["model"], timeout), ("/api/chat", "qwen3:4b", lab.TIMEOUT))
        self.assertEqual(body["options"]["num_predict"], 256)
        self.assertEqual(body["options"]["temperature"], 0)
        self.assertFalse(body["think"])
        self.assertEqual(result["checks"]["oracle_f10"], "pass")
        metrics = result["metrics"]
        self.assertEqual(metrics["ollama_load_ns"], 0)
        self.assertEqual(metrics["output_tokens_per_s"], 10)
        self.assertIsNone(metrics["prompt_tokens"])
        self.assertIsNone(metrics["peak_tree_rss_kib"])


class TransportAndMemoryTests(unittest.TestCase):
    def test_deadline_interrupts_a_peer_that_drips_after_headers(self):
        client, server = socket.socketpair()
        self.addCleanup(client.close)
        self.addCleanup(server.close)
        stopped = threading.Event()

        def serve():
            server.recv(20_000)
            server.sendall(b"HTTP/1.1 200 OK\r\nContent-Length: 80\r\n\r\n{")
            while not stopped.wait(.013):
                try:
                    server.sendall(b" ")
                except BrokenPipeError:
                    break

        thread = threading.Thread(target=serve, daemon=True)
        thread.start()

        def connect(connection):
            connection.sock = client

        started = time.monotonic()
        try:
            with patch.object(lab.http.client.HTTPConnection, "connect", connect):
                with self.assertRaises(lab.LabError) as timed_out:
                    lab.ollama("/api/chat", {}, timeout=.12)
            self.assertEqual(timed_out.exception.code, "ollama_timeout")
            self.assertLess(time.monotonic() - started, 1)
        finally:
            stopped.set()
            thread.join(1)

    def test_server_identity_and_tree_scope(self):
        signature = "Sun Nov 22 11:11:11 2026 /Applications/Ollama.app/Contents/Resources/ollama serve"
        with patch.object(measure, "command", side_effect=["p101\ncollama\nf4\n", signature]) as command:
            self.assertEqual(measure.server_identity(), (101, signature))
            self.assertIn("-iTCP@127.0.0.1:11434", command.call_args_list[0].args)
        with patch.object(measure, "command", return_value="p101\ncproxy\n"):
            self.assertIsNone(measure.server_identity())
        self.assertEqual(measure.tree_rss("101 1 10\n102 101 20\n103 102 40\n104 1 100\n", 101), 70)
        self.assertIsNone(measure.tree_rss("104 1 100\n", 101))


if __name__ == "__main__":
    unittest.main()
