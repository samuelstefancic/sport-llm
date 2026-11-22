"""Contrôle HTTP de l’écran exclusivement sur l’instance locale --essai."""

import argparse
from concurrent.futures import ThreadPoolExecutor
from http.client import HTTPConnection
import json
from pathlib import Path
import subprocess
from urllib.parse import quote
from uuid import uuid4


ROOT = Path(__file__).resolve().parents[1]
VS1 = "Sortie à vélo : objectif 10 km, mais j’ai parcouru 4,5 km."


def request(method, path, expected=200, payload=None, key=None):
    connection = HTTPConnection("127.0.0.1", 8213, timeout=12)
    headers = {"Content-Type": "application/json"} if payload is not None else {}
    if key is not None:
        headers["Idempotency-Key"] = key
    try:
        connection.request(method, path, None if payload is None else json.dumps(payload), headers)
        response = connection.getresponse()
        content = response.read().decode("utf-8")
        assert response.status == expected, (method, path, response.status, content[:500])
        return content, response.getheader("Content-Type") or ""
    finally:
        connection.close()


def read(path):
    content, _ = request("GET", path)
    return json.loads(content)


def post(value, key):
    content, _ = request("POST", "/workouts", payload=value, key=key)
    return json.loads(content)


def find_entry(identifier, revision=1):
    offset = 0
    while offset is not None:
        history = read(f"/workouts?offset={offset}")
        for entry in history["entries"]:
            if (entry["entry_id"], entry["entry_revision"]) == (identifier, revision):
                return entry
        offset = history["next_offset"]
    raise AssertionError(f"Révision introuvable : {identifier} / {revision}")


def check_screen_and_evidence(include_archives=True):
    page, media = request("GET", "/")
    assert "text/html" in media and "Journal sportif" in page and "Suivi du projet" in page
    assert "text/css" in request("GET", "/ecran/style.css")[1]
    assert "text/javascript" in request("GET", "/ecran/journal.js")[1]
    assert "text/javascript" in request("GET", "/ecran/suivi.js")[1]
    config = read("/ecran/suivi.json")
    assert "T11 reporté" in config["decision"]["titre"]
    request("GET", "/ecran/preuves/fichier-inconnu?path=PROJECT.md", expected=404)
    request("GET", "/ecran/preuves/PROJECT.md", expected=404)
    if not include_archives:
        print("OK écran, suivi et liste fermée")
        return
    for key in config["preuves"]:
        _, media = request("HEAD", f"/ecran/preuves/{key}")
        assert "text/plain" in media
    assert read("/ecran/preuves/t10-mesures")["accuracy"]["numerator"] == 22
    bench = read("/ecran/preuves/banc-mesures")
    assert len(bench["engines"]["baseline"]["stable_cases"]) == 16
    assert len(bench["engines"]["qwen3:0.6b"]["stable_cases"]) == 0
    assert len(bench["engines"]["qwen3:4b"]["stable_cases"]) == 3
    probe = read("/ecran/preuves/sonde-mesures")
    assert (probe["schema"]["schema"], probe["schema"]["exact"]) == (8, 4)
    assert sum(case["exact"] for case in probe["schema"]["by_case"]["F10"]) == 0
    delivery = read("/ecran/preuves/vs1-recu")
    assert delivery["ci"]["conclusion"] == "success"
    assert delivery["ci"]["run"].endswith("/45009385674")
    delta = read("/ecran/preuves/vs1-comparaison")
    assert all(run["accuracy"]["numerator"] == 23 and not run["different_cases"] for run in delta["runs"])
    print("OK écran, suivi, artefacts liés et liste fermée")


def check_journal():
    identifier = f"test-ecran-{uuid4()}"
    value = {"entry_id": identifier, "entry_revision": 1, "text": VS1}
    with ThreadPoolExecutor(max_workers=4) as pool:
        attempts = list(pool.map(lambda _: post(value, identifier), range(4)))
    result = attempts[0]
    assert all(attempt == result for attempt in attempts)
    assert len(result["measures"]) == 1
    assert (result["measures"][0]["value"], result["measures"][0]["unit"]) == (4.5, "km")
    distance = result["summary"]["distance"]
    assert (distance["value"], distance["unit"], distance["status"]) == (4500, "m", "known")
    assert [source["text"] for source in distance["sources"]] == ["4,5 km"]
    assert result["summary"]["duration"]["status"] == "absent" and result["energy_burned"] is None
    path = f"/workouts/{quote(identifier)}"
    assert post(value, identifier) == result == read(path)
    request("POST", "/workouts", expected=409, payload={**value, "text": "Course 7 km"}, key=identifier)
    current = post({**value, "entry_revision": 2, "text": "Sortie à vélo : objectif 10 km."}, f"{identifier}-r2")
    distance = current["summary"]["distance"]
    assert distance["status"] == "absent" and distance["value"] is None
    assert distance["unit"] is None and distance["sources"] == []
    assert current["measures"] == []
    assert read(path) == current and read(f"{path}/revisions/1") == result
    history = find_entry(identifier)
    assert history["text"] == VS1 and history["recorded_at"] and history["current_revision"] == 2
    assert find_entry(identifier, 2)["text"] == current["source"]["text"]
    print("OK POST/GET, VS1, objectif seul, source et idempotence sous concurrence")

    subprocess.run([str(ROOT / "scripts/ecran-local"), "--essai", "restart"], check=True)
    assert read(path) == current and read(f"{path}/revisions/1") == result
    assert history == find_entry(identifier)
    print("OK persistance, historique et révisions après redémarrage")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sans-archives", action="store_true", help="Vérifier l’écran sans les pièces historiques locales")
    args = parser.parse_args()
    check_screen_and_evidence(include_archives=not args.sans_archives)
    check_journal()
