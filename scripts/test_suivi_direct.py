"""Oracles du suivi avec des événements et des mesures intégralement fictifs."""

import json
from pathlib import Path
import sqlite3
import subprocess
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from suivi_direct import SCHEMA, Tracking, declaration, rss, session_view, task_view
from suivi_tokens import COUNTERS, ProjectScope, Reader, git_worktrees, timestamp


SESSION = "00000000-0000-7000-8000-000000000001"
TURN = "00000000-0000-7000-8000-000000000002"
NEXT_TURN = "00000000-0000-7000-8000-000000000003"
RETURN_TURN = "00000000-0000-7000-8000-000000000004"
PROJECT = Path("/travail/llmSport/ecran-local")
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
        self.scope = ProjectScope((PROJECT,))
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
        Reader(self.db, SESSION, self.root, self.scope, self.windows).scan(at(40))
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

    def test_neighbor_and_return_preserve_the_cumulative_baseline(self):
        project_counts = (10, 4, 2, 1, 12)
        neighbor_counts = (100, 40, 20, 10, 120)
        self.append(
            usage(at(6), project_counts, project_counts),
            entry(at(7), "task_complete", {"turn_id": TURN}),
            entry(at(8), "task_started", {"turn_id": NEXT_TURN}),
            entry(at(8), "turn_context", {"turn_id": NEXT_TURN, "cwd": str(PROJECT.parent / "voisin"),
                                           "model": "gpt-voisin"}),
            usage(at(9), (110, 44, 22, 11, 132), neighbor_counts),
            entry(at(10), "task_complete", {"turn_id": NEXT_TURN}),
        )
        view = self.observe()
        self.assertEqual(view["tokens"]["total_tokens"], 12)
        self.assertEqual(view["models"], ["gpt-fictif"])
        self.assertEqual(view["turns_completed"], 1)

        self.append(
            entry(at(11), "task_started", {"turn_id": RETURN_TURN}),
            entry(at(11), "turn_context", {"turn_id": RETURN_TURN, "cwd": str(PROJECT / "scripts"),
                                            "model": "gpt-retour"}),
            usage(at(12), (115, 44, 23, 11, 138), (5, 0, 1, 0, 6)),
            entry(at(13), "task_complete", {"turn_id": RETURN_TURN}),
        )
        returned = self.observe()
        self.assertEqual(returned["tokens"]["total_tokens"], 18)
        self.assertEqual(returned["models"], ["gpt-fictif", "gpt-retour"])
        self.assertEqual(returned["turns_completed"], 2)

    def test_unmeasured_neighbor_usage_is_not_attributed_on_return(self):
        counts = (10, 4, 2, 1, 12)
        self.append(
            usage(at(6), counts, counts),
            entry(at(7), "turn_context", {"turn_id": TURN, "cwd": str(PROJECT.parent / "voisin")}),
            entry(at(8), "turn_context", {"turn_id": TURN, "cwd": str(PROJECT)}),
            usage(at(9), (115, 44, 23, 11, 138), (None,) * len(COUNTERS)),
            usage(at(10), (120, 44, 24, 11, 144), (5, 0, 1, 0, 6)),
        )
        view = self.observe()
        self.assertEqual(view["tokens"]["total_tokens"], 18)
        self.assertEqual(view["missing_snapshots"], 1)

    def make_git_worktrees(self):
        project = self.root / "ecran-local"
        linked = self.root / "worktree associé"
        project.mkdir()

        def git(*args):
            subprocess.run(["git", "-C", str(project), *args], check=True, capture_output=True)

        git("init", "-q")
        git("-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
            "-c", "commit.gpgsign=false", "commit", "-q", "--allow-empty", "-m", "Fixture")
        git("worktree", "add", "-q", "--detach", str(linked))
        return project, linked

    def test_real_linked_worktree_and_exact_orchestration(self):
        project, linked = self.make_git_worktrees()
        (linked / "scripts").mkdir()
        (self.root / "voisin").mkdir()
        sibling = self.root / "voisin"
        (project / "vers-voisin").symlink_to(sibling)
        self.scope = ProjectScope(git_worktrees(linked), self.root)
        self.assertEqual(set(self.scope.worktrees), {project, linked})
        self.assertTrue(self.scope.contains(str(self.root)))
        self.assertFalse(self.scope.contains(str(sibling)))
        self.assertFalse(self.scope.contains(str(project / "vers-voisin")))
        for cwd in (linked, self.root):
            with self.subTest(cwd=cwd):
                self.source.write_bytes(
                    entry(at(0), "session_meta", {"id": SESSION, "cwd": str(cwd)})
                    + entry(at(5), "task_started", {"turn_id": TURN})
                    + entry(at(5), "turn_context", {"turn_id": TURN, "cwd": str(linked / "scripts"),
                                                   "model": "gpt-worktree"})
                    + usage(at(6), (10, 4, 2, 1, 12), (10, 4, 2, 1, 12))
                )
                self.db.execute("DELETE FROM sources")
                self.assertEqual(self.observe()["tokens"]["total_tokens"], 12)

        # Le chemin enregistré peut avoir été réutilisé par un dépôt indépendant.
        linked.rename(self.root / "déplacé")
        linked.mkdir()
        subprocess.run(["git", "-C", str(linked), "init", "-q"], check=True, capture_output=True)
        self.assertEqual(git_worktrees(project), (project,))

    def test_legacy_scope_replays_and_keeps_tasks_and_memory(self):
        project, _ = self.make_git_worktrees()
        instance = self.root / "instance"
        instance.mkdir()
        tracking = Tracking(instance, project, trial=True)
        directory = tracking.source / "sessions/2026/01/01"
        directory.mkdir(parents=True)
        missing = "00000000-0000-7000-8000-000000000005"
        window = [(at(0), at(30))]
        db = sqlite3.connect(tracking.db_path)
        db.row_factory = sqlite3.Row
        with db:
            db.executescript(SCHEMA)
            db.execute("DROP TABLE tracking_scope")
            db.execute("INSERT INTO tasks VALUES ('legacy', ?, ?, ?, 1, 2)", (at(0), at(30), at(0)))
            db.execute("INSERT INTO samples VALUES (?, 123, 456, 789, 1)", (at(5),))
            for number, session in enumerate((SESSION, missing), 1):
                db.execute("INSERT INTO sessions VALUES ('legacy', ?, 'principal', ?)", (session, number))
                source = directory / f"rollout-fictif-{session}.jsonl"
                source.write_bytes(
                    entry(at(0), "session_meta", {"id": session, "cwd": str(self.root)})
                    + entry(at(5), "task_started", {"turn_id": TURN})
                    + entry(at(5), "turn_context", {"turn_id": TURN, "cwd": str(project),
                                                   "model": "gpt-projet"})
                    + usage(at(6), (10, 4, 2, 1, 12), (10, 4, 2, 1, 12))
                    + entry(at(7), "task_started", {"turn_id": NEXT_TURN})
                    + entry(at(7), "turn_context", {"turn_id": NEXT_TURN, "cwd": str(self.root / "voisin"),
                                                   "model": "gpt-voisin"})
                    + usage(at(8), (110, 44, 22, 11, 132), (100, 40, 20, 10, 120))
                )
                Reader(db, session, tracking.source, ProjectScope((self.root,)), window).scan(at(40))
            tracking.publish(db, at(40))
        db.close()
        source.unlink()  # Seule l’archive du premier rattachement sera disponible au rejeu.
        legacy = json.loads(tracking.snapshot.read_text())["history"][0]
        self.assertEqual([session["tokens"]["total_tokens"] for session in legacy["sessions"]], [132, 132])

        with patch("suivi_direct.git_worktrees", side_effect=RuntimeError("Git temporairement indisponible")):
            with self.assertRaisesRegex(RuntimeError, "indisponible"):
                tracking.prepare(str(self.root))
        self.assertFalse(tracking.snapshot.exists())

        tracking.prepare(str(self.root))
        migrated = json.loads(tracking.snapshot.read_text())["history"][0]
        self.assertEqual([session["tokens"]["total_tokens"] for session in migrated["sessions"]], [12, None])
        self.assertEqual([session["source_status"] for session in migrated["sessions"]], ["lu", "indisponible"])
        self.assertEqual([session["models"] for session in migrated["sessions"]], [["gpt-projet"], []])
        self.assertEqual(migrated["memory"], legacy["memory"])
        self.assertEqual(migrated["finished_at"], legacy["finished_at"])
        self.assertEqual(migrated["estimate"], legacy["estimate"])
        with Tracking(instance, project, trial=True).locked() as reopened:
            self.assertEqual(reopened.execute("SELECT orchestration FROM tracking_scope").fetchone()[0],
                             str(self.root))
            self.assertEqual(reopened.execute("SELECT count(*) FROM tokens").fetchone()[0], 1)

        tracking.prepare("")
        removed = json.loads(tracking.snapshot.read_text())["history"][0]
        self.assertEqual(removed["sessions"][0]["source_status"], "hors_perimetre")
        self.assertIsNone(removed["sessions"][0]["tokens"]["total_tokens"])
        self.assertEqual(removed["memory"], legacy["memory"])

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
