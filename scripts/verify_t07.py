"""Contrôles HTTP et PostgreSQL du journal sportif sur les déclarations fictives de développement."""

import json
import sys

from jsonschema import Draft202012Validator

from journal_test import ROOT, build_jar, java_service, journal_db, persisted, request, running, uvicorn
from t07_faults import proposal


def read(path):
    return json.loads((ROOT / path).read_text())


def body(entry_id, text):
    return {"entry_id": entry_id, "entry_revision": 1, "text": text}


def source(entry, text):
    assert text in entry["text"]
    return {"kind": "user_declaration", "input_id": entry["entry_id"],
            "input_revision": entry["entry_revision"], "text": text}


def saved(db, port, entry, activity, *, headers=None):
    result = request(port, "POST", "/workouts", entry, headers=headers)
    entry_id = entry["entry_id"]
    assert (result["entry_kind"], result["entry_id"], result["entry_revision"], result["activity"]) == (
        "workout", entry_id, 1, activity)
    assert result["source"] == source(entry, entry["text"])
    assert result["proposal_schema_version"] == "0.1.0" and result["proposal_id"]
    assert result["energy_burned"] is None and "report" not in result
    assert persisted(db, "workout", entry_id, 1) == result
    assert request(port, "GET", f"/workouts/{entry_id}/revisions/1") == result
    request(port, "GET", f"/meals/{entry_id}/revisions/1", expected=404)
    return result


def known(result, field, value, unit, entry, *fragments):
    row = result["summary"][field]
    assert (row["status"], row["value"], row["unit"]) == ("known", value, unit), row
    assert row["sources"] == [source(entry, fragment) for fragment in fragments], row


def absent(result, field):
    row = result["summary"][field]
    assert (row["status"], row["value"], row["unit"], row["sources"]) == ("absent", None, None, []), row


def unresolved(result, field, value, entry, fragment):
    measure, = [measure for measure in result["measures"] if measure["id"] == field]
    assert (measure["value"], measure["unit"], measure["source"]) == (value, None, source(entry, fragment))
    row = result["summary"][field]
    assert (row["status"], row["value"], row["unit"], row["sources"]) == (
        "unresolved", None, None, [source(entry, fragment)])
    clarification, = result["clarifications"]
    assert clarification["field"] == f"{field}.unit" and clarification["reason"] == "unit_absent"
    return clarification["question"]


def refused(db, port, entry, status, code):
    entry_id = entry["entry_id"]
    assert request(port, "POST", "/workouts", entry, expected=status) == {"error": code}
    assert db.execute("SELECT count(*) FROM journal_result WHERE entry_id=%s", (entry_id,)).fetchone() == (0,)
    request(port, "GET", f"/workouts/{entry_id}/revisions/1", expected=404)


def verify_workouts(db, port):
    cases = {case["id"]: case for case in read("data/dev/cases.json")["cases"]}
    s01 = body("T07-S01", cases["S01"]["input"])
    result = saved(db, port, s01, "running")
    known(result, "duration", 30, "min", s01, "20 minutes", "10 minutes")
    assert result["summary"]["duration"]["operation"] == "sum"
    assert [(m["id"], m["value"], m["unit"], m["source"]) for m in result["measures"]] == [
        ("duration", v, "min", source(s01, f"{v} minutes")) for v in (20, 10)]
    absent(result, "distance")
    absent(result, "load")
    assert result["clarifications"] == []
    print("PASS S01 : 20 + 10 min = 30 min, chaque segment ancré ; POST/GET/SQL")

    s03 = body("T07-S03", cases["S03"]["input"])
    result = saved(db, port, s03, "squat")
    known(result, "sets", 3, "count", s03, "3 séries")
    known(result, "repetitions", 10, "count", s03, "10 répétitions")
    known(result, "total_repetitions", 30, "count", s03, "3 séries", "10 répétitions")
    assert result["summary"]["total_repetitions"]["operation"] == "product"
    known(result, "load", 40, "kg", s03, "40 kg")
    absent(result, "duration")
    absent(result, "distance")
    print("PASS S03 : 3 séries de 10, 30 répétitions, 40 kg déclarés ; POST/GET/SQL")

    s06 = body("T07-S06", cases["S06"]["input"])
    result = saved(db, port, s06, "running")
    known(result, "duration", 30, "min", s06, "30 minutes")
    assert unresolved(result, "distance", 5, s06, "5") == "Quelle unité correspond au nombre 5 ?"
    print("PASS S06 : nombre 5 conservé, unité demandée, distance inconnue et durée 30 min ; POST/GET/SQL")

    explicit = body("T07-KNOWN-DISTANCE", "Course 5 km en 30 min")
    result = saved(db, port, explicit, "running")
    known(result, "distance", 5000, "m", explicit, "5 km")
    known(result, "duration", 30, "min", explicit, "30 min")
    assert result["clarifications"] == []
    print("PASS témoin : 5 km explicites normalisés en 5 000 m ; POST/GET/SQL")

    s02 = body("T07-S02", cases["S02"]["input"])
    known(saved(db, port, s02, "running"), "distance", 2750, "m", s02, "2 km", "750 m")
    s04 = body("T07-S04", cases["S04"]["input"])
    known(saved(db, port, s04, "cycling"), "duration", 75, "min", s04, "1 h", "15 min")
    s10 = body("T07-S10", cases["S10"]["input"])
    known(saved(db, port, s10, "mobility"), "distance", 0, "m", s10, "0 km")
    alternate = body("T07-DECIMAL", "Vélo : 1,25 km puis 250 m à 45 s.")
    result = saved(db, port, alternate, "cycling")
    known(result, "distance", 1500, "m", alternate, "1,25 km", "250 m")
    known(result, "duration", 45, "s", alternate, "45 s")
    print("PASS S02/S04/S10 et variante décimale : conversions exactes, secondes et zéro explicite ; POST/GET/SQL")

    s05 = body("T07-S05", cases["S05"]["input"])
    result = saved(db, port, s05, "running")
    absent(result, "duration")
    absent(result, "distance")
    assert result["measures"] == []
    assert [q["field"] for q in result["clarifications"]] == ["duration"]
    s07 = body("T07-S07", cases["S07"]["input"])
    result = saved(db, port, s07, "squat")
    known(result, "total_repetitions", 30, "count", s07, "3 séries", "10 répétitions")
    assert unresolved(result, "load", 40, s07, "40") == "Dans quelle unité est exprimée la charge de 40 ?"
    print("PASS S05/S07 : inconnues conservées et une question par séance ; POST/GET/SQL")

    refused(db, port, body("T07-S08", cases["S08"]["input"]), 400, "negative_duration")
    refused(db, port, body("T07-INPUT-DIMENSION", "Course : distance 5 kg, durée 30 min."), 400,
            "invalid_measure_unit")
    print("PASS S08 et dimension incohérente dans le texte : HTTP 400, aucune écriture")


def verify_faults(db, port):
    schema = read("contracts/analysis.schema.json")
    validator = Draft202012Validator({**schema, "oneOf": [{"$ref": "#/$defs/python_proposal"}]})
    for suffix in ("WRONG-DIMENSION", "FORGED-VALUE", "FORGED-UNIT", "OMITTED", "WRONG-SOURCE"):
        entry = body(f"T07-{suffix}", "Course 5 km en 30 min")
        assert validator.is_valid(proposal(entry)) == (suffix != "WRONG-DIMENSION")
        refused(db, port, entry, 502, "invalid_proposal")
    print("PASS erreurs du pair Python : dimension, valeur, unité plausible, omission, révision de source ; "
          "HTTP 502, aucune écriture")


def duration_choice(result, entry, branches):
    row = result["summary"]["duration"]
    assert (row["status"], row["value"], row["unit"]) == ("unresolved", None, None), row
    measures = [measure for measure in result["measures"] if measure["id"] == "duration"]
    assert measures == [
        {"id": "duration", "value": value, "unit": unit, "source": source(entry, fragment)}
        for value, unit, fragment in branches], measures
    assert row["sources"] == [source(entry, fragment) for _, _, fragment in branches]
    assert result["clarifications"] == [{
        "field": "duration", "reason": "other", "question": "Quelle durée faut-il retenir pour la séance ?",
    }]


def verify_duration_alternatives(db, port):
    alternatives = (
        ("SHARED", "cycling", "Vélo : 20 ou 30 minutes.", ((20, None, "20"), (30, "min", "30 minutes"))),
        ("RUN", "running", "J’ai couru 20 ou 30 minutes.", ((20, None, "20"), (30, "min", "30 minutes"))),
        ("CHAIN", "cycling", "Vélo : 10 ou 20 ou 30 minutes.",
         ((10, None, "10"), (20, None, "20"), (30, "min", "30 minutes"))),
        ("REPEATED", "cycling", "Vélo : 20 minutes ou 30 minutes.",
         ((20, "min", "20 minutes"), (30, "min", "30 minutes"))),
        ("DECIMAL", "cycling", "Vélo : 20,5\u202fou\u00a030,5\u202fmin.",
         ((20.5, None, "20,5"), (30.5, "min", "30,5\u202fmin"))),
    )
    for suffix, activity, declaration, branches in alternatives:
        entry = body(f"T07-ALTERNATIVES-{suffix}", declaration)
        result = saved(db, port, entry, activity)
        duration_choice(result, entry, branches)
        assert len(result["measures"]) == len(branches)
        absent(result, "distance")
        absent(result, "load")
    print("PASS alternatives de durée : chaque branche ancrée, durée indéterminée et une question de choix ; POST/GET/SQL")

    entry = body("T07-DISTANCE-WITH-DURATION-CHOICE", "Vélo : 20 km en 30 ou 45 min.")
    result = saved(db, port, entry, "cycling")
    known(result, "distance", 20000, "m", entry, "20 km")
    duration_choice(result, entry, ((30, None, "30"), (45, "min", "45 min")))
    print("PASS distance déclarée et choix de durée : 20 000 m et une seule question ; POST/GET/SQL")

    for suffix, start, unit, fragment in (("UNIT", "20 km", "km", "20 km"), ("LABEL", "distance 20", None, "20")):
        entry = body(f"T07-ALTERNATIVES-DISTANCE-{suffix}", f"Vélo : {start} ou 30 min.")
        result = saved(db, port, entry, "cycling")
        assert result["measures"] == [
            {"id": "distance", "value": 20, "unit": unit, "source": source(entry, fragment)},
            {"id": "duration", "value": 30, "unit": "min", "source": source(entry, "30 min")},
        ]
    print("PASS dimension explicite : nature et source des mesures candidates conservées ; POST/GET/SQL")


def verify_measure_notation(db, port):
    rates = (
        "20 km h⁻¹", "20,5\u202fkm\u00a0h⁻¹",
        "20 km/h", "20 km / h", "20 m/s", "20 m / s", "20 min/km", "20 min / km", "20 km par heure",
        "20 ou 30 min/km",
    )
    for i, rate in enumerate(rates, 1):
        entry = body(f"T07-COMPOUND-{i}", f"Vélo à {rate} pendant 30 min.")
        result = saved(db, port, entry, "cycling")
        known(result, "duration", 30, "min", entry, "30 min")
        absent(result, "distance")
        assert result["measures"] == [
            {"id": "duration", "value": 30, "unit": "min", "source": source(entry, "30 min")}]
        assert result["clarifications"] == []
    print("PASS vitesse et allure, avec ou sans espaces : 30 min seules, unités composées laissées dans le texte ; POST/GET/SQL")

    entry = body("T07-EXPLICIT-DISTANCE-AND-DURATION", "Vélo : 20 km en 1 h 30 min.")
    result = saved(db, port, entry, "cycling")
    known(result, "distance", 20000, "m", entry, "20 km")
    known(result, "duration", 90, "min", entry, "1 h", "30 min")
    assert result["clarifications"] == []
    print("PASS distance suivie d’une durée composée : 20 000 m et 90 min ; POST/GET/SQL")

    grouped = (("1 000", 1000), ("1\u202f250", 1250), ("1\u00a0250", 1250), ("1\u202f234\u202f567,25", 1234567.25))
    for i, (written, value) in enumerate(grouped, 1):
        fragment = f"{written} m"
        entry = body(f"T07-GROUPED-{i}", f"Vélo : {fragment}.")
        result = saved(db, port, entry, "cycling")
        known(result, "distance", value, "m", entry, fragment)
        assert result["measures"] == [
            {"id": "distance", "value": value, "unit": "m", "source": source(entry, fragment)}]
    refused(db, port, body("T07-GROUPED-INVALID", "Vélo : 1 25 m."), 400, "invalid_measure_number")
    refused(db, port, body("T07-GROUPED-NEGATIVE", "Vélo : -1\u202f250 m."), 400, "negative_measure")
    print("PASS milliers avec espace, espace insécable ou fine insécable : valeur et source entières ; POST/GET/SQL")


def verify():
    with journal_db() as (_, db), java_service(db) as (port, python_port, logs):
        with running(uvicorn("app:app", "python", python_port), python_port, logs / "python.log"):
            verify_workouts(db, port)
            verify_duration_alternatives(db, port)
            verify_measure_notation(db, port)
        with running(uvicorn("t07_faults:app", "scripts", python_port), python_port, logs / "faults.log"):
            verify_faults(db, port)


if __name__ == "__main__":
    if not __debug__:
        sys.exit("Activer les assertions Python pour cette vérification.")
    build_jar()
    verify()
