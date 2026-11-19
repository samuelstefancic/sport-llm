"""T06. Exécuter avec PGHOST/PGPORT/PGDATABASE/PGUSER (et PGPASSWORD si nécessaire)."""

from decimal import Decimal
import json
import sys

from jsonschema import Draft202012Validator

from journal_test import ROOT, build_jar, java_service, journal_db, persisted, request, running, uvicorn
from t08_peer import controlled_peer
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


def check_correction_report(result, meal, totals, portions):
    report = result["report"]
    schema = read(ROOT / "contracts/analysis.schema.json")
    Draft202012Validator({**schema, "oneOf": [{"$ref": "#/$defs/java_nutrition_report"}]}).validate(report)
    assert (report["meal_id"], report["meal_revision"]) == (meal["entry_id"], meal["entry_revision"])
    assert report["selected_nutrients"] == meal["selected_nutrients"]
    actual = [(row["id"], row["value"], row["unit"], row["status"]) for row in report["nutrients"]]
    assert actual == totals, (meal["entry_id"], meal["entry_revision"], actual, totals)
    assert not result["clarifications"]
    catalog = read(SOURCE)
    foods = {food["food_id"]: food for food in catalog["items"]}
    for row in report["nutrients"]:
        assert not row["missing"]
        assert len(row["provenance"]) == len(portions)
        for index, (part, (food, quantity, kind, fragment)) in enumerate(zip(row["provenance"], portions), 1):
            assert part["item_id"] == f"m{index}"
            assert part["quantity"] == {"value": quantity, "unit": "g", "source": {
                "kind": kind, "input_id": meal["entry_id"], "input_revision": meal["entry_revision"],
                "text": fragment,
            }}
            assert fragment in meal["text"]
            reference = foods[food]["nutrients"][row["id"]]
            basis = foods[food]["basis"]["value"]
            assert part["reference"] == {"value": reference["value"], "unit": reference["unit"], "basis_mass_g": basis,
                                         "source": {"kind": "catalog", "record_id": food, "field": "nutrients." + row["id"],
                                                    "catalog_id": catalog["catalog_id"], "catalog_version": catalog["version"]}}
            assert Decimal(str(part["value"])) == Decimal(str(quantity)) * Decimal(str(reference["value"])) / basis


def check_f10(db, port, case, *, markers):
    entry = "T06-F10-STRUCTURED" if markers else "T06-F10"
    selection = {"selected_nutrients": case["selected_nutrients"]}
    previous, current = (f"/meals/{entry}/revisions/{revision}" for revision in (1, 2))
    r1 = {"entry_id": entry, "entry_revision": 1, "text": "150 g de riz cuit, 100 g de poulet cuit", **selection}
    initial = request(port, "POST", "/meals", r1, headers={"Idempotency-Key": entry})
    check_correction_report(initial, r1, [("energy", 360, "kcal", "complet"), ("protein", 34.75, "g", "complet")], [
        ("D01", 150, "user_declaration", "150 g de riz cuit"),
        ("D02", 100, "user_declaration", "100 g de poulet cuit"),
    ])
    original = request(port, "GET", previous + "/declaration")
    assert original["text"] == r1["text"]

    def saved_declarations():
        return db.execute("""SELECT entry_revision, body FROM journal_declaration WHERE entry_id=%s
                             ORDER BY entry_revision""", (entry,)).fetchall()

    assert saved_declarations() == [(1, original)]
    text = case["input"]
    data = {"text": text, **selection}
    if markers:
        data["corrected_mentions"] = markers
    r2 = {**data, "entry_id": entry, "entry_revision": 2}
    result = request(port, "POST", "/meals", r2)
    totals = [(row["id"], row["value"], row["unit"], row["status"]) for row in case["expected"]["nutrients"]]
    rice, chicken = (part.strip().rstrip(".") for part in text.split(";"))
    check_correction_report(result, r2, totals, [
        ("D01", 100, "user_correction", rice),
        ("D02", 100, "user_declaration", chicken),
    ])
    assert request(port, "GET", f"/meals/{entry}") == request(port, "GET", current) == persisted(db, "meal", entry, 2) == result
    assert request(port, "GET", previous) == persisted(db, "meal", entry, 1) == initial
    assert request(port, "POST", "/meals", r1, headers={"Idempotency-Key": entry}) == initial
    declaration = request(port, "GET", current + "/declaration")
    assert declaration["text"] == text and declaration["corrected_mentions"] == markers
    assert request(port, "GET", previous + "/declaration") == original
    assert saved_declarations() == [(1, original), (2, declaration)]
    assert db.execute("SELECT current_revision FROM journal_entry WHERE entry_id=%s", (entry,)).fetchone() == (2,)


def check_correction_variants(db, port):
    entry = "T06-CORRECTION-DECIMAL"
    base = {"entry_id": entry, "selected_nutrients": ["energy", "protein"]}
    r1 = {**base, "entry_revision": 1, "text": "87,5 g de poulet cuit, 150 g de riz cuit, 20 g de lentilles cuites"}
    initial = request(port, "POST", "/meals", r1)
    chicken = "Correction : le poulet cuit reste à 87,5 g"
    rice = "pour le riz cuit, 92.5 g et  non 150 g"
    lentils = "20 g de lentilles cuites"
    text = f"{chicken} et {rice}, {lentils}."
    current = f"/meals/{entry}/revisions/2"
    declaration = {"text": text, "selected_nutrients": base["selected_nutrients"]}
    r2 = {**base, "entry_revision": 2, "text": text}
    for method, path, body in (("PUT", current + "/declaration", declaration), ("POST", "/meals", r2)):
        denied = request(port, method, path, {**body, "corrected_mentions": ["m1"]}, expected=400)
        assert denied == {"error": "invalid_correction"}
        request(port, "GET", current + "/declaration", expected=404)
        assert request(port, "GET", f"/meals/{entry}") == initial
    assert request(port, "PUT", current + "/declaration", declaration)["text"] == text
    result = request(port, "POST", "/meals", r2)
    check_correction_report(result, r2, [("energy", 288.625, "kcal", "complet"), ("protein", 31.2375, "g", "complet")], [
        ("D02", 87.5, "user_declaration", chicken),
        ("D01", 92.5, "user_correction", rice),
        ("D04", 20, "user_declaration", lentils),
    ])
    assert request(port, "GET", current) == persisted(db, "meal", entry, 2) == result

    ambiguous = "pour le riz cuit, 90 g ou 110 g et non 150 g"
    simple = {"entry_id": "T06-CORRECTION-AMBIGUOUS", "entry_revision": 1,
              "text": "150 g de riz cuit, 75 g de poulet cuit", "selected_nutrients": ["energy"]}
    request(port, "POST", "/meals", simple)
    mixed = {**simple, "entry_revision": 2, "text": f"{ambiguous} ; le poulet cuit reste à 75 g."}
    result = request(port, "POST", "/meals", mixed)
    energy, = result["report"]["nutrients"]
    missing_rice, = energy["missing"]
    chicken_part, = energy["provenance"]
    assert (energy["value"], energy["status"]) == (123.75, "partiel")
    assert chicken_part["reference"]["source"]["record_id"] == "D02"
    assert chicken_part["quantity"]["value"] == 75
    assert missing_rice["source"]["text"] == ambiguous and result["clarifications"]

    ordinary = {**simple, "entry_id": "T06-POUR-ORDINARY",
                "text": "Pour ce repas, 100 g de riz cuit, 100 g de poulet cuit."}
    energy, = request(port, "POST", "/meals", ordinary)["report"]["nutrients"]
    assert (energy["value"], energy["status"]) == (295, "partiel")
    assert [part["reference"]["source"]["record_id"] for part in energy["provenance"]] == ["D01", "D02"]
    print("PASS corrections décimales et ordre inversé, rejet du marqueur contradictoire par PUT et POST, "
          "alternative ambiguë conservée et découpage ordinaire préservé")


def check_ordinary_food_negation(db, port):
    entry = "T06-FOOD-NEGATION"
    text = "Pour le déjeuner, 80 g de riz cuit et non du riz cru ; 120 g de poulet cuit."
    meal = {"entry_id": entry, "entry_revision": 1, "text": text, "selected_nutrients": ["energy"]}
    result = request(port, "POST", "/meals", meal)
    energy, = result["report"]["nutrients"]
    assert (energy["value"], energy["unit"], energy["status"]) == (302, "kcal", "partiel"), energy
    rice, chicken = energy["provenance"]
    for part, mention, food, grams, fragment, kcal in (
        (rice, "m2", "D01", 80, "80 g de riz cuit", 104),
        (chicken, "m4", "D02", 120, "120 g de poulet cuit", 198),
    ):
        assert (part["item_id"], part["value"]) == (mention, kcal)
        assert part["quantity"] == {"value": grams, "unit": "g", "source": {
            "kind": "user_declaration", "input_id": entry, "input_revision": 1, "text": fragment,
        }}
        assert part["reference"]["source"] == {
            "kind": "catalog", "catalog_id": "DEMO-FOOD", "catalog_version": "0.2.0",
            "record_id": food, "field": "nutrients.energy",
        }
    assert [(part["item_id"], part["source"]["text"]) for part in energy["missing"]] == [
        ("m1", "Pour le déjeuner"), ("m3", "non du riz cru"),
    ]
    assert request(port, "GET", f"/meals/{entry}/revisions/1") == persisted(db, "meal", entry, 1) == result

    meal = {**meal, "entry_id": "T06-FOOD-NEGATED-AMOUNT",
            "text": "Pour ce repas, 100 g de riz cuit et non 150 g."}
    energy, = request(port, "POST", "/meals", meal)["report"]["nutrients"]
    rice, = energy["provenance"]
    assert (energy["value"], energy["status"], rice["quantity"]["value"]) == (130, "partiel", 100)
    assert rice["quantity"]["source"]["text"] == "100 g de riz cuit"
    print("PASS négations ordinaires : 302 kcal partielles et sources vérifiées par POST/GET/SQL, "
          "aliment avec masse autonome conservé devant « et non 150 g »")


def check_oracle(db, port, meal, oracle_name, *, headers=None):
    expected = read(ROOT / "contracts/examples" / oracle_name)
    result = request(port, "POST", "/meals", meal, headers=headers)
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
            fixtures = {case["id"]: case for case in read(ROOT / "data/dev/cases.json")["cases"]}
            cases = {key: case["input"] for key, case in fixtures.items()}
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

            check_f10(db, port, fixtures["F10"], markers=[])
            check_f10(db, port, fixtures["F10"], markers=["m1"])
            print("PASS F10 : 295 kcal et 33,5 g complets sur r2, sources par aliment ; "
                  "r1 inchangée à 360 kcal et 34,75 g ; POST/GET/SQL")
            check_correction_variants(db, port)
            check_ordinary_food_negation(db, port)

            variant = logs / "salt.json"
            salt_catalog(variant)
            run_cli(dsn, variant)
            salt = {"entry_id": "T03-SEL-001", "entry_revision": 2, "corrected_mentions": ["m1"],
                    "text": "100 g de riz cuit, 100 g de poulet cuit et 100 g de courgettes cuites.",
                    "selected_nutrients": ["salt", "energy", "protein", "carbohydrate", "fat"]}
            request(port, "PUT", "/meals/T03-SEL-001/revisions/1/declaration",
                    {"text": salt["text"].replace("100 g de riz", "150 g de riz"),
                     "selected_nutrients": salt["selected_nutrients"]})
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

        with controlled_peer(python_port) as peer:
            entry = "T06-F10-FORGED"
            r1 = {"entry_id": entry, "entry_revision": 1, "text": "150 g de riz cuit, 100 g de poulet cuit"}
            initial = request(port, "POST", "/meals", r1)
            peer.faults[(entry, 2)] = "quantity"
            r2 = {**r1, "entry_revision": 2, "text": cases["F10"]}
            assert request(port, "POST", "/meals", r2, expected=502) == {"error": "invalid_proposal"}
            request(port, "GET", f"/meals/{entry}/revisions/2", expected=404)
            request(port, "GET", f"/meals/{entry}/revisions/2/declaration", expected=404)
            assert request(port, "GET", f"/meals/{entry}") == persisted(db, "meal", entry, 1) == initial
            print("PASS quantité falsifiée dans la proposition de correction : HTTP 502, aucune r2 persistée")


if __name__ == "__main__":
    if not __debug__:
        sys.exit("Activer les assertions Python pour cette vérification.")
    build_jar()
    verify()
