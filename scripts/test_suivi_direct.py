"""Oracles du suivi avec des événements et des mesures intégralement fictifs."""

import json
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from suivi_direct import SCHEMA, declaration, rss, session_view, task_view
from suivi_tokens import COUNTERS, Reader, timestamp


SESSION = "00000000-0000-7000-8000-000000000001"
TURN = "00000000-0000-7000-8000-000000000002"
NEXT_TURN = "00000000-0000-7000-8000-000000000003"
PROJECT = Path("/travail/llmSport")
SENSITIVE = "TEXTE-FICTIF-IGNORE"


def at(second):
    return timestamp(f"2026-01-01T10:00:{second:02}Z")


def entry(when, kind, payload, ordinal=None):
    outer = {"timestamp": when}
    if ordinal is not None:
        outer["ordinal"] = ordinal
    if kind in ("session_meta", "turn_context", "response_item"):
        outer.update(type=kind, payload=payload)
    else:
        outer.update(type="event_msg", payload={"type": kind, **payload})
    return json.dumps(outer).encode() + b"\n"


def usage(when, cumulative, last, flag=True):
    info = {"total_token_usage": dict(zip(COUNTERS, cumulative)),
            "last_token_usage": dict(zip(COUNTERS, last))}
    if flag is not None:
        info["last_usage_includes_reasoning"] = flag
    return entry(when, "token_count", {"info": info}, ordinal=10)


class SuiviTest(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.source = self.root / "sessions/2026/01/01" / f"rollout-fictif-{SESSION}.jsonl"
        self.source.parent.mkdir(parents=True)
        self.db = self.connect()
        self.addCleanup(lambda: self.db.close())
        self.windows = [(at(5), at(30))]
        self.source.write_bytes(
            entry(at(0), "session_meta", {"id": SESSION, "cwd": str(PROJECT), "base_instructions": SENSITIVE}, 1)
            + entry(at(1), "task_started", {"turn_id": TURN}, 2)
            + entry(at(1), "turn_context", {"turn_id": TURN, "cwd": str(PROJECT), "model": "gpt-fictif",
                                           "extra": [SENSITIVE, {"type": "token_count"}]}))

    def connect(self):
        db = sqlite3.connect(self.root / "test.sqlite3")
        db.row_factory = sqlite3.Row
        db.executescript(SCHEMA)
        return db

    def append(self, *events):
        with self.source.open("ab") as stream:
            for event in events:
                stream.write(event)

    def observe(self, start=5, end=30):
        Reader(self.db, SESSION, self.root, PROJECT, self.windows).scan(at(40))
        self.db.commit()
        return session_view(self.db, {"id": SESSION, "number": 1, "role": "principal"}, at(start), at(end))

    def test_bounds_duplicates_partial_line_and_reopen(self):
        first = (10, 4, 2, 1, 12)
        next_ = (20, 8, 5, 2, 25)
        increment = (10, 4, 3, 1, 13)
        third = (25, 8, 6, 2, 31)
        third_event = usage(at(9), third, (5, 0, 1, 0, 6))
        self.append(usage(at(2), first, first), usage(at(6), next_, increment), usage(at(7), next_, increment),
                    entry(at(8), "response_item", {"text": SENSITIVE, "type": "token_count"}), third_event[:-1])
        first_view = self.observe()
        self.assertEqual(first_view["tokens"]["total_tokens"], 13)
        self.assertEqual(first_view["boundary_snapshots"], 1)
        self.assertEqual(first_view["models"], ["gpt-fictif"])
        self.assertEqual(self.db.execute("SELECT count(*) FROM tokens").fetchone()[0], 1)

        self.db.close()
        self.db = self.connect()
        self.append(b"\n", entry(at(20), "task_complete", {"turn_id": TURN, "last_agent_message": SENSITIVE}),
                    usage(at(31), (100, 25, 20, 5, 120), (75, 17, 14, 3, 89)))
        second_view = self.observe()
        self.assertEqual(second_view["tokens"], dict(zip(COUNTERS, (15, 4, 4, 1, 19))))
        self.assertEqual(second_view["snapshots"], 2)
        self.assertEqual(second_view["boundary_snapshots"], 1)
        self.assertEqual(second_view["turns_completed"], 1)
        self.assertEqual(self.db.execute("SELECT count(*) FROM tokens").fetchone()[0], 2)
        self.assertNotIn(SENSITIVE, "\n".join(self.db.iterdump()))
        self.db.execute("DELETE FROM sources")
        self.assertEqual(self.observe(), second_view)

    def test_incomplete_and_optional_fields(self):
        baseline = (3, None, 1, None, 4)
        self.append(usage(at(3), baseline, baseline, flag=None),
                    entry(at(6), "token_count", {"info": None}),
                    usage(at(8), (11, None, 3, None, 15), (8, None, 2, None, 11), flag=None))
        view = self.observe()
        self.assertEqual(view["tokens"], dict(zip(COUNTERS, (8, None, 2, None, 11))))
        self.assertEqual((view["snapshots"], view["missing_snapshots"]), (1, 1))

    def test_resets_aborts_and_two_overlapping_windows(self):
        self.windows = [(at(5), at(15)), (at(10), at(28))]
        first = (10, 4, 2, 1, 12)
        increment = (2, 1, 1, 0, 3)
        self.append(usage(at(4), first, first), usage(at(7), (12, 5, 3, 1, 15), increment),
                    usage(at(11), (13, 5, 5, 1, 18), (1, 0, 2, 0, 3)),
                    usage(at(14), increment, increment),
                    entry(at(27), "turn_aborted", {"turn_id": TURN, "reason": SENSITIVE}))
        first_task = self.observe(start=5, end=15)
        second_task = self.observe(start=10, end=28)
        self.assertEqual(first_task["tokens"]["total_tokens"], 9)
        self.assertEqual(second_task["tokens"]["total_tokens"], 6)
        self.assertEqual(first_task["counter_resets"], 1)
        self.assertEqual(second_task["turns_aborted"], 1)
        self.assertEqual(self.db.execute("SELECT count(*) FROM tokens").fetchone()[0], 3)

    def test_previous_model_is_excluded_after_a_context_change(self):
        self.windows = [(at(5), at(30))]
        self.append(entry(at(4), "turn_context", {"turn_id": TURN, "cwd": str(PROJECT), "model": "gpt-autre"}),
                    entry(at(20), "turn_aborted", {"turn_id": TURN}))
        view = self.observe()
        self.assertEqual(view["models"], ["gpt-autre"])
        self.assertEqual(view["turns_aborted"], 1)
        self.assertIsNone(view["tokens"]["total_tokens"])

    def test_missing_or_wrong_project_source_is_not_zero(self):
        self.source.unlink()
        view = self.observe()
        self.assertEqual(view["source_status"], "indisponible")
        self.assertIsNone(view["tokens"]["total_tokens"])
        self.append(entry(at(0), "session_meta", {"id": SESSION, "cwd": "/travail/autre"}))
        view = self.observe()
        self.assertEqual(view["source_status"], "hors_perimetre")
        self.assertEqual(view["models"], [])
        self.assertIsNone(view["tokens"]["total_tokens"])

    def test_memory_samples_and_wall_clock(self):
        task = {"id": "essai", "started_at": at(0), "finished_at": at(25),
                "estimated_at": at(0), "min_minutes": 1, "max_minutes": 2}
        self.db.executemany("INSERT INTO samples VALUES (?, ?, ?, ?, ?)", [
            (at(1), 25, None, 4, 1), (at(10), 20, 15, 8, 2), (at(30), 1000, 1000, 1000, 4)
        ])
        historical = task_view(self.db, task, at(40), include_samples=True)
        self.assertEqual(historical["elapsed_seconds"], 25)
        self.assertEqual(historical["estimate_gap_seconds"], -35)
        self.assertEqual(historical["memory"], {"first_at": at(1), "last_at": at(10), "count": 2,
                                                "java": 25, "python": 15, "postgres": 8})
        self.assertEqual(len(historical["memory_samples"]), 2)
        with patch("suivi_direct.numeric_command") as probe:
            self.assertIsNone(rss({"pid": 3, "signature": "essai"}, lambda *_: False))
            probe.assert_not_called()

    def test_early_bound_and_incomplete_initial_estimate(self):
        args = SimpleNamespace(debut=at(1), estime_le=at(3), minimum=25, maximum=45)
        with self.assertRaisesRegex(ValueError, "datée"):
            declaration(args, at(5))
        args.estime_le = at(1)
        self.assertEqual(declaration(args, at(5)), (at(1), at(1), 25, 45))
        args.maximum = None
        with self.assertRaisesRegex(ValueError, "ordre"):
            declaration(args, at(5))


if __name__ == "__main__":
    unittest.main()
