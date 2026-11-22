"""Vérifie les fichiers locaux et les séries avec Ollama simulé."""

import asyncio
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import threading
import unittest
from unittest.mock import patch

from fastapi import FastAPI

from test_qwen_lab import BODY, CHICKEN, F10, RICE, TOKEN, item, lab, native, request
import qwen_sets as sets


QUINOA = "quinoa cuit, 120 g et non 180 g"
TOFU = "tofu cuit reste à 80 g"
QUINOA_TEXT = f"Correction du repas : pour le {QUINOA} ; le {TOFU}."
SETTINGS = {key: value for key, value in BODY.items() if key != "text"}


def anchor(text, value, unit="g", state="cooked"):
    return {"anchor": text, "state": state, "quantity": {"value": value, "unit": unit}}


def fixture_game():
    return {"name": "Deux corrections fictives", "cases": [
        {"name": "F10", "text": F10, "expected": [anchor(RICE, 100), anchor(CHICKEN, 100)]},
        {"name": "Quinoa-tofu", "text": QUINOA_TEXT, "expected": [anchor(QUINOA, 120), anchor(TOFU, 80)]},
    ]}


def evaluated(raw, text=F10, expected=None, mode="reference", reason="stop"):
    passages = lab.passages_for(text) if mode == "passages" else None
    checks, _, rows = lab.validate_extraction(raw, text, reason, passages)
    return sets.comparison(expected, {"checks": checks, "mentions": rows, "done_reason": reason})


class OracleTests(unittest.TestCase):
    def test_distinguishes_structure_citation_oracle_and_exploration(self):
        f10, quinoa = fixture_game()["cases"]
        self.assertEqual(evaluated(native(item(RICE), item(CHICKEN)), expected=f10["expected"])["verdict"], "success")
        error = evaluated(native(item("quinoa cuit, 120 g", 180), item(TOFU, 80) | {"state": "raw"}),
                          text=QUINOA_TEXT, expected=quinoa["expected"])
        self.assertEqual(error["verdict"], "oracle_failed")
        first, second = error["differences"]
        self.assertEqual((first["anchor_ok"], first["quantity_ok"], first["state_ok"]), (False, False, True))
        self.assertEqual((second["anchor_ok"], second["quantity_ok"], second["state_ok"]), (True, True, False))
        self.assertEqual(evaluated(native(item(RICE), item(CHICKEN)))["verdict"], "exploratory")
        self.assertEqual(evaluated(native(item("absent")))["verdict"], "citation_error")
        self.assertEqual(evaluated(native(), expected=[])["verdict"], "success")
        self.assertEqual(evaluated(native(), expected=f10["expected"])["verdict"], "oracle_failed")
        self.assertEqual(evaluated(native(), reason="length")["verdict"], "structure_error")

    def test_recorded_f10_json_invalid_shape_stops_before_citations(self):
        # Sortie native du premier essai F10 passages, 76 jetons sur 256.
        raw = '{"mentions":[{"passage_id":"p1","state":"cooked","quantity":{"value":100,"unit":"g"}},{"passage_id":"p2",": ":":","  ":""}]}'
        checks, _, rows = lab.validate_extraction(raw, F10, "stop", lab.passages_for(F10))
        self.assertTrue(checks["json"])
        self.assertFalse(checks["structure"])
        self.assertIsNone(checks["citations"])
        self.assertEqual(rows, [])
        self.assertEqual(evaluated(raw, mode="passages")["verdict"], "structure_error")

    def test_same_passages_prompt_and_options_with_only_format_different(self):
        reply = {"model": lab.MODEL, "done": True, "message": {"content": native()}}
        with patch.object(lab, "ollama", return_value=reply) as ollama, patch.object(lab, "server_identity", return_value=None):
            for mode in ("passages", "passages_schema"):
                result = lab.run_once(lab.RunInput(**(BODY | {"mode": mode, "prompt": lab.PROMPTS[mode]})))
                self.assertEqual(result["generation"]["format"], ollama.call_args.args[1]["format"])
        original, structured = [call.args[1].copy() for call in ollama.call_args_list]
        self.assertEqual(original.pop("format"), "json")
        schema = structured.pop("format")
        self.assertEqual(original, structured)
        self.assertFalse(schema["additionalProperties"])
        mention = schema["properties"]["mentions"]["items"]
        self.assertEqual(set(mention["required"]), {"passage_id", "state", "quantity"})
        self.assertEqual(mention["properties"]["passage_id"]["enum"], ["p1", "p2"])
        self.assertFalse(mention["additionalProperties"])
        self.assertFalse(mention["properties"]["quantity"]["anyOf"][1]["additionalProperties"])


class FileTests(unittest.TestCase):
    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.project = Path(directory.name).resolve()
        self.store = sets.Store(self.project, 8214)

    def test_read_scope_bounds_no_symlink_hardlink_or_special_file(self):
        self.assertEqual(self.store.index("jeux"), [])
        self.assertFalse((self.project / ".local").exists())
        self.store.write("jeux", "jeu", fixture_game())
        path = self.project / self.store.path("jeux", "jeu")
        self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        self.assertEqual(self.store.read("jeux", "jeu")["name"], fixture_game()["name"])
        self.assertEqual(sets.Store(self.project, 8114).index("jeux"), [])
        external = self.project / "outside.json"
        external.write_text("{}")
        for identifier in ("../outside", "UP", "a/", "a" * 41):
            with self.assertRaises(sets.LabError) as invalid:
                self.store.read("jeux", identifier)
            self.assertEqual(invalid.exception.code, "qwen_invalid_id")
        (path.parent / "symbolic.json").symlink_to(external)
        os.link(external, path.parent / "hard.json")
        os.mkfifo(path.parent / "fifo.json")
        (path.parent / "big.json").write_bytes(b" " * (sets.MAX_GAME + 1))
        for identifier in ("symbolic", "hard", "fifo", "big"):
            with self.assertRaises(sets.LabError):
                self.store.read("jeux", identifier)
        for identifier in ("symbolic", "hard", "fifo"):
            with self.assertRaises(sets.LabError):
                self.store.write("jeux", identifier, fixture_game())
        self.assertEqual(self.store.index("jeux"), ["jeu"])
        self.assertEqual(external.read_text(), "{}")
        self.assertEqual(list(path.parent.glob(".tmp-*")), [])
        (self.project / ".local").rename(self.project / "moved")
        (self.project / ".local").symlink_to(self.project / "moved", target_is_directory=True)
        with self.assertRaises(sets.LabError):
            self.store.read("jeux", "jeu")

    def test_concurrent_creations_share_the_collection_quota(self):
        def write(identifier):
            try:
                self.store.write("jeux", identifier, fixture_game())
                return "saved"
            except sets.LabError as error:
                return error.code

        with patch.object(sets, "MAX_RECORDS", 1), ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(write, ["jeu-a", "jeu-b"]))
        self.assertCountEqual(outcomes, ["saved", "qwen_storage_full"])
        self.assertEqual(len(self.store.index("jeux")), 1)

    def test_failed_replacement_keeps_previous_game(self):
        self.store.write("jeux", "jeu", fixture_game())
        with patch.object(sets.os, "replace", side_effect=OSError):
            with self.assertRaises(sets.LabError):
                self.store.write("jeux", "jeu", fixture_game() | {"name": "Autre"})
        self.assertEqual(self.store.read("jeux", "jeu")["name"], fixture_game()["name"])
        self.assertEqual(list((self.project / self.store.path("jeux", "jeu")).parent.glob(".tmp-*")), [])


class SeriesTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.project = Path(directory.name).resolve()
        self.app = self.open_app()

    def open_app(self):
        app = FastAPI()
        lab.install(app, 8214, TOKEN.encode(), self.project)
        return app

    async def http(self, url, body=None, **kwargs):
        return await request(self.app, url, "GET" if body is None else "POST",
                             body=b"" if body is None else json.dumps(body).encode(),
                             details=True, **kwargs)

    async def test_validation_bounds_and_authentication_on_store(self):
        self.assertEqual((await self.http("jeux", token=None))[0], 403)
        self.assertEqual((await self.http("jeux/demo", fixture_game(), origin="http://127.0.0.1:8213"))[0], 403)
        self.assertEqual((await self.http("jeux/demo", fixture_game(), host="example.test"))[0], 403)
        self.assertEqual((await self.http("jeux", query=b"path=../"))[0], 400)
        self.assertEqual((await self.http("jeux/invalid.dot", fixture_game()))[1]["error"], "qwen_invalid_id")
        invalid = [fixture_game() | {"cases": []}, fixture_game() | {"cases": fixture_game()["cases"] * 3},
                   fixture_game() | {"cases": [{"name": "A", "text": F10, "expected": [anchor("ne figure pas", 100)]}]},
                   fixture_game() | {"cases": [{"name": "A", "text": F10, "expected": [anchor(RICE, True)]}]},
                   fixture_game() | {"cases": [{"name": "A", "text": "é" * 3000}]}]
        for game in invalid:
            self.assertEqual((await self.http("jeux/demo", game))[0], 400)
        self.assertEqual((await self.http("jeux/demo", {"text": "x" * sets.MAX_GAME}))[0], 413)
        self.assertFalse((self.project / ".local").exists())
        self.assertEqual((await self.http("series", SETTINGS | {"game_id": "demo"}))[0], 404)

    async def test_sequential_receipts_frozen_settings_progress_and_restart(self):
        code, index = await self.http("jeux")
        self.assertEqual(code, 200)
        self.assertEqual(index["f10"]["text"], F10)
        code, saved = await self.http("jeux/corrections", fixture_game())
        self.assertEqual((code, saved["path"]), (200, ".local/qwen-lab/essai/jeux/corrections.json"))
        self.app = self.open_app()
        self.assertEqual((await self.http("jeux/corrections"))[1]["cases"], fixture_game()["cases"])
        first = threading.Event()
        finish = threading.Event()
        messages = []

        def response(path, payload=None, timeout=None):
            if path == "/api/tags":
                return {"models": [{"name": lab.MODEL, "digest": "a" * 64}]}
            if path == "/api/version":
                return {"version": "simulee"}
            messages.append(payload)
            if len(messages) == 1:
                return {"model": lab.MODEL, "done": True, "done_reason": "stop",
                        "message": {"content": native(item(RICE), item(CHICKEN))},
                        "prompt_eval_count": 123, "eval_count": 76}
            first.set()
            if not finish.wait(4):
                raise RuntimeError("Test timed out")
            return {"model": lab.MODEL, "done": True, "done_reason": "stop",
                    "message": {"content": native(item(QUINOA, 180), item(TOFU, 80))}}

        with patch.object(lab, "ollama", side_effect=response), patch.object(lab, "server_identity", return_value=None):
            try:
                code, created = await self.http("series", SETTINGS | {"game_id": "corrections"})
                self.assertEqual(code, 202)
                identifier = created["id"]
                self.assertTrue(await asyncio.to_thread(first.wait, 2))
                self.assertEqual((await self.http("series", SETTINGS | {"game_id": "corrections"}))[0], 409)
                self.assertEqual((await self.http("series"))[1]["ids"], [identifier])
                reading = (await self.http("series/" + identifier))[1]
                self.assertEqual(reading["status"], "running")
                self.assertEqual(len(reading["results"]), 1)
                self.assertEqual((await self.http("jeux/corrections", fixture_game() | {"name": "Écrasé"}))[0], 200)
            finally:
                finish.set()
            for _ in range(100):
                reading = (await self.http("series/" + identifier))[1]
                if reading["status"] == "completed":
                    break
                await asyncio.sleep(.01)
        self.assertEqual(reading["status"], "completed")
        self.assertEqual(reading["settings"], SETTINGS)
        self.assertEqual(reading["game"], {"schema_version": sets.SCHEMA, **fixture_game()})
        self.assertTrue(all(len(value) == 64 for value in reading["expected_sha256"]))
        self.assertTrue(all(len(value) == 64 for value in reading["lab"]["python_sha256"].values()))
        self.assertEqual([row["evaluation"]["verdict"] for row in reading["results"]], ["success", "oracle_failed"])
        output = reading["results"][0]["outcome"]
        self.assertEqual(output["metrics"]["output_tokens"], 76)
        self.assertEqual(output["model"]["digest"], "a" * 64)
        self.assertIsNone(output["metrics"]["peak_tree_rss_kib"])
        self.assertEqual([module["messages"][1]["content"] for module in messages],
                         ["Domaine : meal\nTexte : " + F10, "Domaine : meal\nTexte : " + QUINOA_TEXT])
        self.assertTrue(all(payload["messages"][0]["content"] == SETTINGS["prompt"] for payload in messages))
        self.assertEqual(messages[0]["options"], messages[1]["options"])
        self.app = self.open_app()
        self.assertEqual((await self.http("series/" + identifier))[1], reading)
        self.assertEqual(json.loads((self.project / created["path"]).read_text()), reading)

    async def test_incomplete_receipt_is_readable_after_restart(self):
        store = sets.Store(self.project, 8214)
        identifier = "20261122-150000-1234567890ab"
        store.write("series", identifier, {"schema_version": sets.SCHEMA, "id": identifier, "status": "running", "results": []})
        self.app = self.open_app()
        self.assertEqual((await self.http("series/" + identifier))[1]["status"], "interrupted")


if __name__ == "__main__":
    unittest.main()
