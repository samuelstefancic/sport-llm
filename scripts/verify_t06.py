"""T06. Exécuter avec PGHOST/PGPORT/PGDATABASE/PGUSER (et PGPASSWORD si nécessaire)."""

from decimal import Decimal
import json
import sys

from jsonschema import Draft202012Validator

from journal_test import ROOT, build_jar, java_service, journal_db, persisted, request, running, uvicorn
from verify_t05 import SOURCE, run_cli


def read(path):
    return json.loads(path.read_text())


def salt_catalog(path):
    # Adapter le format de la fixture historique à l’importeur T05, sans emprunter ses teneurs à 0.2.0.
    historic = read(ROOT / "documentation/verification-skills-2026-11-17/T03-SEL-001.json")["catalog"]
    catalog = read(SOURCE)
    catalog.update(version=historic["version"], lineage={"base_catalog": historic["base_version"]}, items=[])
    for item in historic["items"]:
        nutrients = {key: {**cell, "availability": "known" if cell["value"] is not None else "absent"}
                     for key, cell in item["nutrients"].items()}
        catalog["items"].append({"food_id": item["id"], "label": item["name"], "state": item["state"],
                                 "basis": historic["basis"], "nutrients": nutrients})
    path.write_text(json.dumps(catalog))


def references(parts):
    return sorted((c["reference"]["source"]["record_id"], c["reference"]["source"]["catalog_id"],
                   c["reference"]["source"]["catalog_version"], c["reference"]["source"]["field"],
                   c["reference"]["value"], c["reference"]["unit"], c["reference"]["basis_mass_g"],
                   c["quantity"]["value"], c["value"]) for c in parts)


def missing(parts):
    return sorted((c["reason"], c["source"]["record_id"], c["source"]["catalog_version"],
                   c["source"]["field"]) for c in parts)


def check_oracle(db, port, meal, oracle_name):
    expected = read(ROOT / "contracts/examples" / oracle_name)
    result = request(port, "POST", "/meals", meal)
    actual = result["report"]
    schema = read(ROOT / "contracts/analysis.schema.json")
    Draft202012Validator({**schema, "oneOf": [{"$ref": "#/$defs/java_nutrition_report"}]}).validate(actual)
    assert (actual["meal_id"], actual["meal_revision"]) == (meal["entry_id"], meal["entry_revision"])
    ids = meal.get("selected_nutrients", expected["selected_nutrients"])
    assert set(actual["selected_nutrients"]) == set(ids) and len(actual["nutrients"]) == len(ids)
    actual_rows = {row["id"]: row for row in actual["nutrients"]}
    assert set(actual_rows) == set(ids)
    for row in expected["nutrients"]:
        received = actual_rows[row["id"]]
        for field in ("unit", "status", "value"):
            assert received[field] == row[field], (row["id"], field, received)

        assert references(received["provenance"]) == references(row["provenance"]), row["id"]
        for part in received["provenance"]:
            source = part["quantity"]["source"]
            assert (source["input_id"], source["input_revision"]) == (meal["entry_id"], meal["entry_revision"])
            assert source["text"] in meal["text"]
            corrected_rice = oracle_name == "java-salt-reference.json" and part["reference"]["source"]["record_id"] == "D01"
            assert source["kind"] == ("user_correction" if corrected_rice else "user_declaration")
        assert missing(received["missing"]) == missing(row["missing"]), row["id"]
    assert persisted(db, "meal", meal["entry_id"], meal["entry_revision"]) == result
    assert request(port, "GET", f"/meals/{meal['entry_id']}/revisions/{meal['entry_revision']}") == result
    return result


def verify():
    with journal_db() as (dsn, db), java_service(db) as (port, python_port, logs):
        with running(uvicorn("app:app", "python", python_port), python_port, logs / "python.log"):
            cases = {case["id"]: case["input"] for case in read(ROOT / "data/dev/cases.json")["cases"]}
            f02 = {"entry_id": "T06-F02", "entry_revision": 1,
                   "text": cases["F02"]}
            original = check_oracle(db, port, f02, "java-macros-complete.json")
            print("PASS F02 : 415 kcal, 42,5 g, 46 g, 4,3 g ; références 0.2.0 ; POST/GET/SQL")

            unknown = request(port, "POST", "/meals", {**f02, "entry_id": "T06-UNKNOWN", "text": "riz cuit"})
            assert unknown["clarifications"] and all(row["value"] is None and row["status"] == "indéterminé"
                                                      for row in unknown["report"]["nutrients"])
            assert all(any(m["reason"] == "quantity_absent" for m in row["missing"])
                       for row in unknown["report"]["nutrients"])
            print("PASS quantité absente : clarification et résultats indéterminés")

            bowl = {**f02, "entry_id": "T06-F07", "text": cases["F07"]}
            proposal = request(port, "POST", "/analysis", bowl)
            mention, = proposal["food_mentions"]
            assert (mention["quantity"]["value"], mention["quantity"]["unit"]) == (1, "portion")
            result = request(port, "POST", "/meals", {**bowl, "selected_nutrients": ["protein"]})
            protein, = result["report"]["nutrients"]
            gap, = protein["missing"]
            question, = result["clarifications"]
            assert (protein["value"], protein["status"], protein["provenance"]) == (None, "indéterminé", [])
            assert gap["source"]["text"] == "Un bol de riz cuit"
            assert gap["reason"] == question["reason"] == "portion_mass_unknown"
            assert question["field"] == "quantity" and "grammes" in question["question"]
            assert persisted(db, "meal", bowl["entry_id"], 1) == result
            assert request(port, "GET", "/meals/T06-F07/revisions/1") == result
            print("PASS F07 : bol déclaré conservé, clarification de la masse, protéines indéterminées ; POST/GET/SQL")

            fraction = request(port, "POST", "/meals", {**f02, "entry_id": "T06-DECIMAL",
                               "text": "12,5 g de riz cuit", "selected_nutrients": ["fat"]})
            fat, = fraction["report"]["nutrients"]
            assert fat["unit"] == "g" and Decimal(str(fat["value"])) == Decimal("0.0375")
            print("PASS fraction décimale : 0,0375 g de lipides")

            for entry, declaration in (("T06-F15", cases["F15"]),
                                       ("T06-F15-MIXED", f"100 g de poulet cuit et {cases['F15']}")):
                refused = request(port, "POST", "/meals", {**f02, "entry_id": entry, "text": declaration},
                                  expected=400)
                assert refused == {"error": "negative_quantity"}
                assert not db.execute("SELECT 1 FROM journal_result WHERE entry_id=%s", (entry,)).fetchone()
                request(port, "GET", f"/meals/{entry}/revisions/1", expected=404)
            print("PASS F15 et repas mixte : quantité négative rejetée, aucune écriture")

            request(port, "POST", "/meals", {**f02, "entry_id": "T06-BLANK", "text": "\u00a0"}, expected=400)
            assert not db.execute("SELECT 1 FROM journal_result WHERE entry_id='T06-BLANK'").fetchone()
            print("PASS espace insécable seul : HTTP 400, aucune écriture")

            variant = logs / "salt.json"
            salt_catalog(variant)
            run_cli(dsn, variant)
            salt = {"entry_id": "T03-SEL-001", "entry_revision": 2, "corrected_mentions": ["m1"],
                    "text": "100 g de riz cuit, 100 g de poulet cuit et 100 g de courgettes cuites.",
                    "selected_nutrients": ["salt", "energy", "protein", "carbohydrate", "fat"]}
            check_oracle(db, port, salt, "java-salt-reference.json")
            assert request(port, "GET", "/meals/T06-F02/revisions/1") == original
            print("PASS T03-SEL-001 : riz corrigé à 100 g ; sel 0 g partiel, 2 manques ; "
                  "295 kcal partielles, 34,5 g complètes, glucides/lipides indéterminés ; POST/GET/SQL")

        with running(uvicorn("t04_faults:app", "scripts", python_port), python_port, logs / "faults.log"):
            body = {"entry_id": "T06-FORGED", "entry_revision": 1, "text": "100 g de riz cuit"}
            refused = request(port, "POST", "/meals", body, expected=502)
            assert refused["error"] == "invalid_proposal"
            assert not db.execute("SELECT 1 FROM journal_result WHERE entry_id='T06-FORGED'").fetchone()
            print("PASS proposition Python structurellement valide avec quantité 150 g pour 100 g déclarés : "
                  "HTTP 502, aucune écriture")


if __name__ == "__main__":
    if not __debug__:
        sys.exit("Activer les assertions Python pour cette vérification.")
    build_jar()
    verify()
