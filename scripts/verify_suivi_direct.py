"""Contrôle de l’API, des PIDs et de la reprise sur --essai avec une session fictive."""

from datetime import datetime, timedelta, timezone
import json
import subprocess
import time
from uuid import uuid4

from suivi_tokens import timestamp
from test_suivi_direct import NEXT_TURN, TURN, entry, usage
from verify_ecran_local import ROOT, read, request


ENDPOINT = "/api/local/suivi/direct"


def command(*args, expected=0):
    completed = subprocess.run([str(ROOT / "scripts/ecran-local"), "--essai", *args],
                               check=False, capture_output=True, text=True)
    assert completed.returncode == expected, (args, completed.returncode, completed.stderr)
    return completed.stdout


def eventually(predicate):
    until = time.monotonic() + 20
    while time.monotonic() < until:
        data = read(ENDPOINT)
        result = predicate(data)
        if result:
            return result
        time.sleep(.2)
    raise AssertionError("Le relevé attendu n’est pas paru sur l’instance d’essai.")


def find(data, list_key, identifier):
    return next((task for task in data[list_key] if task["id"] == identifier), None)


def main():
    page, _ = request("GET", "/")
    assert "Suivi en direct" in page and "Résultat de la séance" in page
    request("GET", ENDPOINT + "?path=PROJECT.md", expected=400)
    request("POST", ENDPOINT, expected=405)
    request("HEAD", ENDPOINT, expected=405)
    request("GET", ENDPOINT + "/historique.sqlite3", expected=404)
    request("GET", "/ecran/preuves-lots/affichage.json", expected=404)
    request("GET", "/ecran/preuves-lots/" + "a" * 65, expected=404)

    identifier = f"essai-{uuid4().hex[:10]}"
    request("GET", f"/ecran/preuves-lots/{identifier}", expected=404)
    session_id = str(uuid4())
    current = datetime.now(timezone.utc)
    started = timestamp((current - timedelta(seconds=8)).isoformat())
    collected = timestamp((current - timedelta(seconds=3)).isoformat())
    changed = timestamp((current - timedelta(seconds=2)).isoformat())
    outside = timestamp((current - timedelta(seconds=1)).isoformat())
    scope = ROOT.resolve()
    neighbor = scope.parent / f"voisin-fictif-{session_id}"
    # --essai utilise une racine source dédiée. Il ne parcourt jamais les journaux Codex de l’utilisateur.
    directory = ROOT / ".local/ecran-essai/suivi-direct/sources/sessions/2026/01/01"
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    fixture = directory / f"rollout-fictif-{session_id}.jsonl"
    counts = (10, 4, 2, 1, 12)
    fixture.write_bytes(
        entry(started, "session_meta", {"id": session_id, "cwd": str(scope), "base_instructions": "TEXTE-FICTIF"})
        + entry(started, "task_started", {"turn_id": TURN})
        + entry(started, "turn_context", {"turn_id": TURN, "cwd": str(scope), "model": "gpt-fixture"})
        + usage(collected, counts, counts)
        + entry(changed, "task_complete", {"turn_id": TURN})
        + entry(changed, "task_started", {"turn_id": NEXT_TURN})
        + entry(changed, "turn_context", {"turn_id": NEXT_TURN, "cwd": str(neighbor), "model": "gpt-voisin"})
        + usage(outside, (110, 44, 22, 11, 132), (100, 40, 20, 10, 120))
        + entry(outside, "task_complete", {"turn_id": NEXT_TURN})
    )

    command("suivi", "declarer", identifier, "--debut", started, "--estime-le", started, "--min", "25", "--max", "45")
    legacy = find(read(ENDPOINT), "active_tasks", identifier)
    assert (legacy["objective"], legacy["owner"], legacy["completion_criterion"], legacy["evidence_ids"]) == (
        None, None, None, [],
    )
    descriptions = {
        "objective": "Vérifier la collecte fictive.",
        "owner": "Rôle fictif",
        "completion_criterion": "Historique relu après redémarrage.",
        "evidence_ids": [identifier],
    }
    command("suivi", "enrichir", identifier,
            "--objectif", descriptions["objective"], "--responsable", descriptions["owner"],
            "--critere-fin", descriptions["completion_criterion"], "--preuve", identifier)
    command("suivi", "enrichir", identifier, "--preuve", "https://example.invalid/", expected=2)
    command("suivi", "session", identifier, session_id, "--role", "principal")

    def observed(data):
        assert data["rss_unit"] == "KiB" and data["postgres_scope"] == "parent"
        task = find(data, "active_tasks", identifier)
        sample = data["latest_sample"]
        if not task or not task["sessions"] or not task["sessions"][0]["snapshots"] or sample["at"] < started:
            return None
        assert all(type(sample[key]) is int and sample[key] > 0 for key in ("java", "python", "postgres"))
        assert sample["pressure"] is None or type(sample["pressure"]) is int
        assert session_id not in json.dumps(task) and "TEXTE-FICTIF" not in json.dumps(task)
        assert task["estimate_gap_seconds"] < 0 and task["started_at"] == started
        assert task["sessions"][0]["models"] == ["gpt-fixture"]
        assert task["sessions"][0]["tokens"]["total_tokens"] == 12
        assert task["sessions"][0]["turns_completed"] == 1
        assert {key: task[key] for key in descriptions} == descriptions
        return task

    active = eventually(observed)
    print("OK GET local fermé, RAM authentifiée, fenêtre active, estimation et jetons hors projet exclus.")

    print(command("restart").strip())
    after = eventually(observed)
    assert after["elapsed_seconds"] > active["elapsed_seconds"]
    assert after["sessions"][0]["snapshots"] == 1
    assert after["memory"]["count"] >= active["memory"]["count"]

    command("suivi", "finir", identifier)
    closed = find(read(ENDPOINT), "history", identifier)
    assert closed["finished_at"] and closed["status"] == "termine"
    assert {key: closed[key] for key in descriptions} == descriptions
    assert not find(read(ENDPOINT), "active_tasks", identifier)
    saved = json.loads(command("suivi", "historique", identifier))
    assert saved["elapsed_seconds"] == closed["elapsed_seconds"]
    assert saved["memory_samples"] and saved["sessions"][0]["samples"][0]["total_tokens"] == 12
    command("suivi", "session", identifier, session_id, "--role", "principal")
    replayed = eventually(lambda data: (
        task if (task := find(data, "history", identifier)) and task["sessions"][0]["source_status"] == "lu" else None
    ))
    assert replayed["elapsed_seconds"] == closed["elapsed_seconds"]
    assert replayed["sessions"][0]["snapshots"] == 1
    print("OK fiche enrichie, preuve fermée, redémarrage, clôture, historique et rattrapage sans doublon.")


if __name__ == "__main__":
    main()
