"""Exerce les révisions et l’idempotence via HTTP et des transactions PostgreSQL réelles."""

from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from copy import deepcopy
import json
import sys
from time import monotonic
from uuid import uuid4

import psycopg
from jsonschema import Draft202012Validator

from journal_test import ROOT, build_jar, java_service, journal_db, persisted, request
from t08_peer import controlled_peer
from verify_t05 import run_cli
from verify_t06 import check_oracle, salt_catalog


def read(relative_path):
    return json.loads((ROOT / relative_path).read_text())


def post(port, domain, body, key=None, *, headers=None, **options):
    if key is not None:
        headers = {**(headers or {}), "Idempotency-Key": key}
    return request(port, "POST", f"/{domain}", body, headers=headers, **options)


def declaration_path(domain, body):
    return f"/{domain}/{body['entry_id']}/revisions/{body['entry_revision']}/declaration"


def declare(port, domain, body, **options):
    content = {k: v for k, v in body.items() if k not in {"entry_id", "entry_revision"}}
    return request(port, "PUT", declaration_path(domain, body), content, **options)


def content(entry_id, revision, text, **parts):
    return {"entry_id": entry_id, "entry_revision": revision, "text": text, **parts}


def snapshot(db):
    return tuple(db.execute(f"SELECT xmin::text, * FROM {table} ORDER BY {columns}").fetchall()
                 for table, columns in [
                     ("journal_entry", "entry_id"),
                     ("journal_declaration", "entry_id,entry_revision"),
                     ("journal_result", "entry_id,entry_revision"),
                     ("journal_idempotency", "request_key"),
                 ])


def revisions(db, entry):
    return (
        db.execute("SELECT current_revision FROM journal_entry WHERE entry_id=%s", (entry,)).fetchone(),
        db.execute("SELECT entry_revision FROM journal_declaration WHERE entry_id=%s ORDER BY 1", (entry,)).fetchall(),
        db.execute("SELECT entry_revision FROM journal_result WHERE entry_id=%s ORDER BY 1", (entry,)).fetchall(),
        db.execute("SELECT request_key FROM journal_idempotency WHERE entry_id=%s ORDER BY 1", (entry,)).fetchall(),
    )


def rejection(body, entry, analysis, current, proposal=None):
    schema = read("contracts/analysis.schema.json")
    Draft202012Validator({**schema, "oneOf": [{"$ref": "#/$defs/java_analysis_rejection"}]}).validate(body)
    assert (body["code"], body["entry_id"], body["analysis_revision"], body["current_revision"]) == (
        "stale_revision", entry, analysis, current)
    if proposal is not None:
        assert body["proposal_id"] == proposal


def late_response(db, port, peer):
    r2 = content("MEAL-001", 2, "100 g de riz cuit, 100 g de poulet cuit et 100 g de courgettes cuites.",
                 selected_nutrients=["salt", "energy", "protein", "carbohydrate", "fat"], corrected_mentions=["m1"])
    r1 = content("MEAL-001", 1, r2["text"].replace("100 g de riz", "150 g de riz"),
                 selected_nutrients=r2["selected_nutrients"])
    original = declare(port, "meals", r1)
    assert revisions(db, "MEAL-001") == ((1,), [(1,)], [], [])
    reached, release = peer.gate("MEAL-001", 1)
    with ThreadPoolExecutor(max_workers=1) as pool:
        late = pool.submit(post, port, "meals", r1, "late-r1", expected=409)
        try:
            assert reached.wait(5), "Java n’a pas demandé la proposition pour r1"
            corrected = declare(port, "meals", r2)
            assert revisions(db, "MEAL-001") == ((2,), [(1,), (2,)], [], [])
            request(port, "GET", "/meals/MEAL-001", expected=404)
            report = check_oracle(db, port, r2, "java-salt-reference.json")
            before = snapshot(db)
        finally:
            release.set()
        rejection(late.result(8), "MEAL-001", 1, 2, "PROP-OLD")
    assert snapshot(db) == before
    assert revisions(db, "MEAL-001") == ((2,), [(1,), (2,)], [(2,)], [])
    assert request(port, "GET", declaration_path("meals", r1)) == original
    assert request(port, "GET", declaration_path("meals", r2)) == corrected
    assert original["text"].startswith("150 g de riz cuit")
    assert corrected["text"] == original["text"].replace("150 g de riz", "100 g de riz")
    assert request(port, "GET", "/meals/MEAL-001") == report
    request(port, "GET", "/meals/MEAL-001/revisions/1", expected=404)
    assert declare(port, "meals", r1) == original and snapshot(db) == before
    print("PASS T03-STALE-001 : premier calcul r1 (150 g) en vol, correction r2 (100 g), "
          "HTTP 409 canonique PROP-OLD, aucun bilan r1, deux déclarations et bilan r2 inchangés en SQL")


def wait_for_blockers(db, query, blockers):
    deadline = monotonic() + 6
    while monotonic() < deadline:
        waits = db.execute("""
            SELECT pid, pg_blocking_pids(pid) FROM pg_stat_activity
            WHERE datname=current_database() AND wait_event_type='Lock' AND query LIKE %s
            ORDER BY pid""", (query,)).fetchall()
        if blockers(waits):
            return waits
    raise AssertionError(f"Attentes PostgreSQL attendues pour {query!r}, observé {waits!r}")


@contextmanager
def hold_lock(db, expression, *parameters):
    db.execute(f"SELECT pg_advisory_lock({expression})", parameters)
    try:
        yield db.info.backend_pid
    finally:
        assert db.execute(f"SELECT pg_advisory_unlock({expression})", parameters).fetchone() == (True,)


def check_locked_revision(db, port, peer):
    r1 = content("T08-ROW-LOCK", 1, "Course 5 km en 30 min")
    r2 = content(r1["entry_id"], 2, "Course 5 km en 25 min")
    declare(port, "workouts", r1)
    db.execute("""
        CREATE FUNCTION t08_wait_before_revision() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF NEW.entry_id = 'T08-ROW-LOCK' THEN
                PERFORM pg_advisory_xact_lock(8108, 1);
            END IF;
            RETURN NEW;
        END;
        $$;
        CREATE TRIGGER t08_hold_revision BEFORE UPDATE ON journal_entry
        FOR EACH ROW EXECUTE FUNCTION t08_wait_before_revision();
        """, prepare=False)
    reached, release = peer.gate(r1["entry_id"], 1)
    with ThreadPoolExecutor(max_workers=2) as pool:
        with hold_lock(db, "8108, 1") as supervisor:
            correction = pool.submit(declare, port, "workouts", r2)
            (corrector, _), = wait_for_blockers(db, "UPDATE journal_entry%",
                                                lambda w: len(w) == 1 and supervisor in w[0][1])
            try:
                analyzing = pool.submit(post, port, "workouts", r1, "row-lock-r1", expected=409)
                assert reached.wait(5), "La lecture préparatoire doit permettre la proposition r1"
                assert revisions(db, r1["entry_id"]) == ((1,), [(1,)], [], [])
            finally:
                release.set()
            (analyzer, _), = wait_for_blockers(
                db, "SELECT entry_kind,current_revision%FOR UPDATE",
                lambda w: len(w) == 1 and corrector in w[0][1])
            assert analyzer != corrector
            assert not analyzing.done() and not correction.done()
        corrected = correction.result(8)
        rejection(analyzing.result(8), r1["entry_id"], 1, 2)
    assert request(port, "GET", declaration_path("workouts", r2)) == corrected
    assert revisions(db, r1["entry_id"]) == ((2,), [(1,), (2,)], [], [])
    result = post(port, "workouts", r2)
    duration = result["summary"]["duration"]
    assert (duration["value"], duration["unit"], result["energy_burned"]) == (25, "min", None)
    assert duration["sources"] == [{"kind": "user_correction", "input_id": r1["entry_id"],
                                    "input_revision": 2, "text": "25 min"}]
    assert request(port, "GET", f"/workouts/{r1['entry_id']}") == persisted(db, "workout", r1["entry_id"], 2) == result
    assert revisions(db, r1["entry_id"]) == ((2,), [(1,), (2,)], [(2,)], [])
    print("PASS sport : lecture préparatoire r1, verrou final bloqué par la correction r2 selon pg_blocking_pids, "
          "puis HTTP 409 r1 et résultat r2 de 25 min avec source user_correction")


def race_key(db, port, peer, first, second, key):
    # Hold the actual key lock until both independent write transactions have reached it.
    request_ids = [str(uuid4()), str(uuid4())]
    with ThreadPoolExecutor(max_workers=2) as pool:
        with hold_lock(db, "hashtextextended('llmsport:journal:idempotency:' || %s, 0)", key) as supervisor:
            futures = [pool.submit(post, port, "meals", body, key, expected=(200, 409), with_status=True,
                                   headers={"X-Correlation-ID": request_id})
                       for body, request_id in zip((first, second), request_ids)]
            waits = wait_for_blockers(db, "SELECT pg_advisory_xact_lock(hashtextextended%",
                                      lambda w: len(w) == 2 and any(supervisor in pids for _, pids in w))
            assert len({pid for pid, _ in waits}) == 2 and not any(f.done() for f in futures)
            assert peer.count(first["entry_id"], 1) == 2
        return [f.result(8) for f in futures], request_ids


def idempotency(db, port, peer, java_log):
    r1 = content("T08-SAME-KEY", 1, "150 g de riz cuit")
    r1_reordered = {"selected_nutrients": ["energy", "protein", "carbohydrate", "fat"], **r1}
    paired, request_ids = race_key(db, port, peer, r1, r1_reordered, "same-key-r1")
    assert paired[0] == paired[1] and paired[0][0] == 200
    report = paired[0][1]
    assert revisions(db, r1["entry_id"]) == ((1,), [(1,)], [(1,)], [("same-key-r1",)])
    assert persisted(db, "meal", r1["entry_id"], 1) == report
    traces = java_log.read_text()
    assert all(f"correlation={request_id} outcome=proposal_accepted" in traces for request_id in request_ids)
    outcomes = {request_id: [outcome for outcome in ("journal_committed", "idempotent_replay")
                             if f"correlation={request_id} outcome={outcome}" in traces]
                for request_id in request_ids}
    assert sorted(outcomes.values()) == [["idempotent_replay"], ["journal_committed"]], outcomes
    print("PASS clé/charge identiques : deux transactions PostgreSQL concurrentes, deux HTTP 200 identiques, "
          "une déclaration, un bilan et une clé ; "
          + ", ".join(f"{outcome[0]}={request_id}" for request_id, outcome in outcomes.items()))

    first = content("T08-CONFLICT-KEY", 1, "150 g de riz cuit")
    second = {**first, "text": "100 g de riz cuit"}
    paired, _ = race_key(db, port, peer, first, second, "conflict-key")
    assert sorted(code for code, _ in paired) == [200, 409]
    (winner, saved), = [(body, result) for body, (code, result) in zip((first, second), paired) if code == 200]
    loser, = [body for body, (code, result) in zip((first, second), paired)
              if code == 409 and result == {"error": "idempotency_conflict"}]
    assert request(port, "GET", declaration_path("meals", winner))["text"] == winner["text"]
    assert revisions(db, winner["entry_id"]) == ((1,), [(1,)], [(1,)], [("conflict-key",)])
    assert saved == persisted(db, "meal", winner["entry_id"], 1)
    before = snapshot(db)
    assert post(port, "meals", loser, "conflict-key", expected=409) == {"error": "idempotency_conflict"}
    assert post(port, "workouts", winner, "conflict-key", expected=409) == {"error": "idempotency_conflict"}
    assert post(port, "meals", {**winner, "entry_id": "T08-OTHER-ID"},
                "conflict-key", expected=409) == {"error": "idempotency_conflict"}
    assert post(port, "meals", {**winner, "entry_revision": 2},
                "conflict-key", expected=409) == {"error": "idempotency_conflict"}
    assert post(port, "meals", {**winner, "selected_nutrients": ["protein"]},
                "conflict-key", expected=409) == {"error": "idempotency_conflict"}
    assert snapshot(db) == before and peer.count(winner["entry_id"], 1) == 2
    print("PASS clé identique/contenu différent : HTTP 200 et 409 idempotency_conflict, "
          "un seul résultat ; domaine, identifiant, révision, texte et sélection dans la comparaison")

    r2 = content(r1["entry_id"], 2, "100 g de riz cuit", corrected_mentions=["m1"])
    adjusted = post(port, "meals", r2, "same-key-r2")
    before = snapshot(db)
    assert post(port, "meals", r1, "same-key-r1") == report
    assert post(port, "meals", {**r2, "corrected_mentions": []},
                "same-key-r2", expected=409) == {"error": "idempotency_conflict"}
    assert declare(port, "meals", {**r2, "text": "110 g de riz cuit"}, expected=409) == {"error": "revision_conflict"}
    assert post(port, "meals", {**r2, "text": "110 g de riz cuit"},
                expected=409) == {"error": "revision_conflict"}
    for revision, result in [(1, report), (2, adjusted)]:
        assert request(port, "GET", f"/meals/{r1['entry_id']}/revisions/{revision}") == result
    assert request(port, "GET", f"/meals/{r1['entry_id']}") == adjusted
    assert peer.count(r1["entry_id"], 1) == 2 and snapshot(db) == before
    print("PASS rejeu de la clé r1 après r2 : charge initiale rendue sans nouvel appel au pair ni écriture ; "
          "correction dans la comparaison et bilan r2 courant conservé")
    return r1, report


def unkeyed_revision_race(dsn, db, port):
    initial = content("T08-UNKEYED", 1, "150 g de riz cuit")
    original = declare(port, "meals", initial)
    with ThreadPoolExecutor(max_workers=2) as pool:
        with psycopg.connect(dsn) as lock:
            lock.execute("SELECT 1 FROM journal_entry WHERE entry_id=%s FOR UPDATE", (initial["entry_id"],))
            valid = pool.submit(post, port, "meals", initial)
            invalid = pool.submit(post, port, "meals", {**initial, "text": "100 g de riz cuit"}, expected=409)
            wait_for_blockers(db, "SELECT entry_kind,current_revision%FOR UPDATE",
                              lambda w: len(w) == 2 and any(lock.info.backend_pid in pids for _, pids in w))
        assert invalid.result(8) == {"error": "revision_conflict"}
        accepted = valid.result(8)
    assert request(port, "GET", declaration_path("meals", initial)) == original
    assert persisted(db, "meal", initial["entry_id"], 1) == accepted
    protein = next(row for row in accepted["report"]["nutrients"] if row["id"] == "protein")
    assert protein["provenance"][0]["quantity"]["value"] == 150
    assert revisions(db, initial["entry_id"]) == ((1,), [(1,)], [(1,)], [])
    print("PASS même révision sans clé : deux analyses concurrentes, HTTP 200 pour les 150 g déclarés, "
          "HTTP 409 pour les 100 g divergents, un bilan et déclaration intacte")


def invalid_attempts(db, port, peer):
    old = content("T08-MISMATCH", 1, "150 g de riz cuit")
    declare(port, "meals", old)
    before = snapshot(db)
    assert post(port, "meals", {**old, "text": "100 g de riz cuit"},
                expected=409) == {"error": "revision_conflict"}
    assert post(port, "meals", {**old, "entry_revision": 3},
                expected=409) == {"error": "revision_conflict"}
    assert declare(port, "meals", content("T08-NEW-GAP", 2, old["text"]),
                   expected=409) == {"error": "revision_conflict"}
    assert snapshot(db) == before
    for entry, revision, fault in (("T08-BAD-NEW", 1, "shape"), ("T08-MISMATCH", 2, "quantity")):
        peer.faults[(entry, revision)] = fault
        assert post(port, "meals", content(entry, revision, old["text"]), "invalid-" + fault,
                    expected=502) == {"error": "invalid_proposal"}
        assert snapshot(db) == before
    result = post(port, "meals", old)
    assert request(port, "GET", "/meals/T08-MISMATCH") == result
    assert revisions(db, old["entry_id"]) == ((1,), [(1,)], [(1,)], [])
    before = snapshot(db)
    correction = {**old, "entry_revision": 2}
    for fields, code in [({"text": "-100 g de riz cuit"}, "negative_quantity"),
                         ({"selected_nutrients": ["not_in_catalog"]}, "invalid_selection"),
                         ({"corrected_mentions": ["m2"]}, "invalid_correction")]:
        assert declare(port, "meals", {**correction, **fields}, expected=400) == {"error": code}
        assert request(port, "GET", "/meals/T08-MISMATCH") == result and snapshot(db) == before
    peer.faults.pop((old["entry_id"], 2))
    unknown = {**correction, "text": "riz cuit", "corrected_mentions": ["m1"]}
    assert declare(port, "meals", unknown)["text"] == "riz cuit"
    unknown_report = post(port, "meals", unknown)["report"]
    assert all(row["status"] == "indéterminé" and row["value"] is None for row in unknown_report["nutrients"])
    print("PASS déclaration immuable avant calcul même sans clé, saut interdit et réponses Python invalides "
          "sans changement (dont rollback de la correction implicite après une proposition contradictoire)")
    print("PASS correction PUT : masse négative, apport hors catalogue et mention invalide refusés en HTTP 400, "
          "r1 conserve le bilan courant ; quantité inconnue acceptée et conservée en r2")


LEGACY = [
    ("T08-LEGACY-MEAL", 4, "meal", {"origin": "T06", "report": {"meal_id": "T08-LEGACY-MEAL", "meal_revision": 4}}),
    ("T08-LEGACY-MEAL", 1, "meal", {"origin": "T06", "report": {"meal_id": "T08-LEGACY-MEAL", "meal_revision": 1}}),
    ("T08-LEGACY-MEAL", 3, "workout", {"origin": "T07", "entry_id": "T08-LEGACY-MEAL",
                                      "entry_kind": "workout", "entry_revision": 3, "energy_burned": None}),
    ("T08-LEGACY-WORKOUT", 1, "workout", {"origin": "T07", "entry_id": "T08-LEGACY-WORKOUT",
                                        "entry_kind": "workout", "entry_revision": 1, "energy_burned": None}),
]


def prepare_legacy(db):
    db.execute("""CREATE TABLE journal_result (
        entry_id text NOT NULL,
        entry_revision bigint NOT NULL CHECK (entry_revision > 0),
        entry_kind text NOT NULL,
        payload jsonb NOT NULL,
        PRIMARY KEY (entry_id, entry_revision))""")
    insert_legacy(db, LEGACY)


def insert_legacy(db, results):
    for entry, revision, kind, payload in results:
        db.execute("""INSERT INTO journal_result(entry_id,entry_revision,entry_kind,payload)
                      VALUES (%s,%s,%s,%s::jsonb) ON CONFLICT (entry_id,entry_revision) DO NOTHING""",
                   (entry, revision, kind, json.dumps(payload)))


def reject_legacy(db, row, constraint):
    before = snapshot(db)
    try:
        insert_legacy(db, [row])
    except psycopg.errors.CheckViolation as error:
        assert error.diag.constraint_name == constraint
    else:
        raise AssertionError(f"Le résultat historique divergent a été accepté pour {row[:3]}")
    assert snapshot(db) == before


def legacy_results(db, port):
    for entry, revision, kind, payload in LEGACY:
        domain = "meals" if kind == "meal" else "workouts"
        assert request(port, "GET", f"/{domain}/{entry}/revisions/{revision}") == payload
        assert persisted(db, kind, entry, revision) == payload
        request(port, "GET", declaration_path(domain, content(entry, revision, "")), expected=404)
    for current in [LEGACY[0], LEGACY[-1]]:
        entry, revision, kind, payload = current
        domain = "meals" if kind == "meal" else "workouts"
        assert request(port, "GET", f"/{domain}/{entry}") == payload
        text = "100 g de riz cuit" if kind == "meal" else "Course 5 km en 30 min"
        assert declare(port, domain, content(entry, revision, text),
                       expected=409) == {"error": "revision_conflict"}
        updated = post(port, domain, content(entry, revision + 1, text))
        assert request(port, "GET", f"/{domain}/{entry}") == updated
        assert persisted(db, kind, entry, revision) == payload
    before = snapshot(db)
    db.execute((ROOT / "java/src/main/resources/journal.sql").read_text(), prepare=False)
    assert snapshot(db) == before
    print("PASS migration depuis le journal T06/T07 peuplé : reprise de MAX(révision), historique lisible "
          "et inchangé, pas de déclaration inventée, correction courante possible, migration rejouable")

    reserved_r1 = content("T08-LEGACY-RESERVED", 1, "150 g de riz cuit", selected_nutrients=["protein"])
    original_report = post(port, "meals", reserved_r1)
    reserved_r2 = {**reserved_r1, "entry_revision": 2, "text": "100 g de riz cuit", "corrected_mentions": ["m1"]}
    declaration = declare(port, "meals", reserved_r2)
    divergent_report = deepcopy(original_report)
    divergent_report["report"]["meal_revision"] = 2
    divergent_report["report"]["nutrients"][0]["provenance"][0]["quantity"]["source"]["input_revision"] = 2
    reserved = reserved_r1["entry_id"]
    reject_legacy(db, (reserved, 2, "meal", divergent_report), "journal_result_declaration_binding")
    assert revisions(db, reserved) == ((2,), [(1,), (2,)], [(1,)], [])
    assert request(port, "GET", declaration_path("meals", reserved_r2)) == declaration
    request(port, "GET", f"/meals/{reserved}", expected=404)
    request(port, "GET", f"/meals/{reserved}/revisions/2", expected=404)
    corrected = post(port, "meals", reserved_r2)
    contribution, = corrected["report"]["nutrients"][0]["provenance"]
    assert contribution["quantity"]["value"] == 100
    assert contribution["quantity"]["source"]["kind"] == "user_correction"
    assert request(port, "GET", f"/meals/{reserved}") == persisted(db, "meal", reserved, 2) == corrected
    assert persisted(db, "meal", reserved, 1) == original_report
    assert db.execute("SELECT declaration_bound FROM journal_result WHERE entry_id=%s ORDER BY entry_revision",
                      (reserved,)).fetchall() == [(True,), (True,)]
    print("PASS ancienne écriture 150 g sur une déclaration r2 à 100 g : SQLSTATE 23514, "
          "GET courant 404 puis bilan T08 à 100 g, r1 intacte")

    meal, previous_meal_result, _, legacy_meal = LEGACY[0]
    workout, previous_workout_result, _, legacy_workout = LEGACY[-1]
    pending_workout = content(workout, previous_workout_result + 2, "Course 5 km en 25 min")
    pending = declare(port, "workouts", pending_workout)
    request(port, "GET", f"/workouts/{workout}", expected=404)

    meal_catchup = previous_meal_result + 2
    other_domain_revision = meal_catchup + 3
    legacy_correction = {**legacy_meal, "report": {**legacy_meal["report"], "meal_revision": meal_catchup}}
    legacy_other_domain = {**legacy_workout, "entry_id": meal, "entry_revision": other_domain_revision}
    insert_legacy(db, [(meal, meal_catchup, "meal", legacy_correction)])
    reject_legacy(db, (meal, other_domain_revision, "workout", legacy_other_domain), "journal_result_entry_kind")
    request(port, "GET", f"/workouts/{meal}/revisions/{other_domain_revision}", expected=404)
    assert request(port, "GET", f"/meals/{meal}")["report"]["meal_revision"] == meal_catchup - 1
    before = snapshot(db)
    db.execute((ROOT / "java/src/main/resources/journal.sql").read_text(), prepare=False)
    assert snapshot(db)[1:] == before[1:]
    assert request(port, "GET", f"/meals/{meal}") == legacy_correction
    assert db.execute("SELECT declaration_bound FROM journal_result WHERE entry_id=%s AND entry_revision=%s",
                      (meal, meal_catchup)).fetchone() == (False,)
    request(port, "GET", f"/meals/{meal}/revisions/{meal_catchup}/declaration", expected=404)
    request(port, "GET", f"/workouts/{meal}", expected=404)
    assert request(port, "GET", declaration_path("workouts", pending_workout)) == pending
    assert revisions(db, workout)[0] == (pending_workout["entry_revision"],)
    request(port, "GET", f"/workouts/{workout}", expected=404)
    for revision in range(meal_catchup + 1, other_domain_revision + 2):
        next_meal = post(port, "meals", content(meal, revision, f"{100 + revision} g de riz cuit"))
        assert next_meal == request(port, "GET", f"/meals/{meal}") == persisted(db, "meal", meal, revision)
    request(port, "GET", f"/workouts/{meal}/revisions/{other_domain_revision}", expected=404)
    assert request(port, "GET", f"/meals/{meal}/revisions/{meal_catchup}") == legacy_correction
    before = snapshot(db)
    db.execute((ROOT / "java/src/main/resources/journal.sql").read_text(), prepare=False)
    assert snapshot(db) == before
    print("PASS reprise après ancien écrivain : r6 repas reprise, r9 sport refusée en SQLSTATE 23514, "
          "r7 à r10 repas appliquées et déclaration sport r3 en attente préservée")

    new_workout = "T08-LEGACY-NEW-WORKOUT"
    new_payload = {**legacy_workout, "entry_id": new_workout}
    insert_legacy(db, [(new_workout, 1, "workout", new_payload)])
    reject_legacy(db, (new_workout, 2, "meal", legacy_meal), "journal_result_entry_kind")
    assert request(port, "GET", f"/workouts/{new_workout}") == new_payload
    print("PASS ancien premier INSERT sur un nouvel identifiant : domaine sport fixé et résultat relisible, "
          "écriture repas suivante refusée en SQLSTATE 23514")


def verify():
    with journal_db(prepare_legacy) as (dsn, db), java_service(db) as (port, python_port, logs):
        variant = logs / "salt.json"
        salt_catalog(variant)
        run_cli(dsn, variant)
        catalog = db.execute("SELECT xmin::text, * FROM catalog_active").fetchall()
        with controlled_peer(python_port) as peer:
            late_response(db, port, peer)
            check_locked_revision(db, port, peer)
            r1, report = idempotency(db, port, peer, logs / "java.log")
            unkeyed_revision_race(dsn, db, port)
            invalid_attempts(db, port, peer)
            legacy_results(db, port)
        before = snapshot(db)
        assert post(port, "meals", r1, "same-key-r1") == report
        assert post(port, "meals", content(r1["entry_id"], 3, "80 g de riz cuit"), "unavailable",
                    expected=502) == {"error": "python_unavailable"}
        assert snapshot(db) == before
        assert db.execute("SELECT xmin::text, * FROM catalog_active").fetchall() == catalog
        print("PASS sans pair Python : rejeu historique disponible, analyse nouvelle en HTTP 502, "
              "journal et version du catalogue actif inchangés")


if __name__ == "__main__":
    if not __debug__:
        sys.exit("Activer les assertions Python pour cette vérification.")
    build_jar()
    verify()
