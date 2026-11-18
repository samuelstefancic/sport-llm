"""Barème T10 sur les observations HTTP/SQL et les attendus P0."""

from collections import Counter
from decimal import Decimal
from math import ceil
import re


CRITICAL = {
    "invented_value", "wrong_calculation", "source_mismatch", "unsafe_write",
}
MISSING = {"field_absent": True}
MISSING_REASONS = {
    "food_state_ambiguous": "raw_cooked_unknown",
    "volume_to_mass_unavailable": "density_unknown",
    "catalog_match_unknown": "food_unresolved",
}
MEAL_QUESTIONS = {
    "D02.quantity": ("m2", "quantity", "quantity_absent", r"\b(?:masse|quantité)\b"),
    "food_state": ("m1", "food_state", "raw_cooked_unknown", r"\bcru[e]?[s]?\b.*\bcuit[e]?[s]?\b"),
    "D01.quantity_mass": ("m1", "quantity", "portion_mass_unknown", r"\b(?:masse|grammes)\b"),
    "D04.quantity_mass": ("m1", "quantity", "density_unknown", r"\b(?:masse|grammes)\b"),
    "recipe_composition": ("m1", "food", "food_unresolved", r"\b(?:ingrédients|composition)\b"),
}
# Ancrages tirés des déclarations P0, indépendants des fragments renvoyés par le pair.
MEAL_CITATIONS = {
    "F01": ("100 g de riz cuit", "100 g de poulet cuit", "100 g de courgettes cuites"),
    "F02": ("100 g de riz cuit", "100 g de poulet cuit", "100 g de lentilles cuites"),
    "F03": ("50 g de riz cuit", "100 g de poulet cuit", "100 g de courgettes cuites"),
    "F04": ("100 g de courgettes cuites",),
    "F05": ("100 g de riz cuit", "du poulet cuit"),
    "F06": ("100 g de riz",),
    "F07": ("Un bol de riz cuit",),
    "F08": ("200 ml de lentilles cuites",),
    "F09": ("100 g de galette maison",),
    "F10": ("riz cuit, 100 g", "le poulet cuit reste à 100 g"),
    "F12": ("200 g d’eau de la fiche D06",),
    "F13": ("250 g de riz cuit",),
    "F14": ("50 g de lentilles cuites",),
}
SPORT_CITATIONS = {
    "S01": {"duration": ["20 minutes", "10 minutes"]},
    "S02": {"distance": ["2 km", "750 m"]},
    "S03": {"sets": ["3 séries"], "repetitions": ["10 répétitions"], "load": ["40 kg"],
            "total_repetitions": ["3 séries", "10 répétitions"]},
    "S04": {"duration": ["1 h", "15 min"]},
    "S05": {},
    "S06": {"duration": ["30 minutes"], "distance": ["5"]},
    "S07": {"sets": ["3 séries"], "repetitions": ["10 répétitions"], "load": ["40"],
            "total_repetitions": ["3 séries", "10 répétitions"]},
    "S09": {"duration": ["45 minutes"]},
    "S10": {"duration": ["10 minutes"], "distance": ["0 km"]},
}
SPORT_UNIT_CODES = {"minutes": "min", "min": "min", "h": "h", "km": "km", "m": "m", "kg": "kg",
                    "séries": "count", "répétitions": "count"}
WORKOUT_MEASURES = {
    "duration": "duration", "distance": "distance", "load": "load", "sets": "sets",
    "repetitions_per_set": "repetitions", "total_repetitions": "total_repetitions",
}


class Checks:
    def __init__(self):
        self.failures = []
        self.count = 0

    def equal(self, field, actual, expected, category="contract"):
        self.count += 1
        if actual != expected or (isinstance(actual, bool) != isinstance(expected, bool)):
            self.failures.append({
                "field": field, "category": category, "expected": expected, "observed": actual,
            })

    def value(self, field, actual, expected):
        category = "invented_value" if expected is None and actual is not MISSING else "wrong_calculation"
        self.equal(field, actual, expected, category)


def fields(obj, keys):
    return {name: obj.get(name, MISSING) for name in keys}


def equal_source(check, field, source, request, kind, *, text=None, anchor=None):
    check.equal(field + ".binding", fields(source, ("kind", "input_id", "input_revision")), {
        "kind": kind, "input_id": request["entry_id"], "input_revision": request["entry_revision"],
    }, "source_mismatch")
    fragment = source.get("text")
    matched = isinstance(fragment, str) and bool(fragment) and fragment in request["text"] and (
        text is None or text == fragment
    )
    check.equal(field + ".text_matches_declaration", matched, True, "source_mismatch")
    if anchor:
        check.equal(field + ".text_matches_expected_mention", isinstance(fragment, str) and anchor in fragment,
                    True, "source_mismatch")


def catalog_source(check, field, source, oracle):
    check.equal(field, fields(source, ("kind", "catalog_id", "catalog_version", "record_id", "field")), {
        "kind": "catalog", "catalog_id": oracle["catalog_id"], "catalog_version": oracle["catalog_version"],
        "record_id": oracle["food_id"], "field": "nutrients." + oracle["field"],
    }, "source_mismatch")


def meal_questions(check, body, oracle):
    questions = body.get("clarifications", [])
    if "clarification" not in oracle:
        check.equal("clarifications", questions, [], "clarification")
        return
    mention, field, reason, terms = MEAL_QUESTIONS[oracle["clarification"]["field"]]
    first = questions[0] if questions else {}
    check.equal("first_clarification.target", fields(first, ("mention_id", "field", "reason")),
                {"mention_id": mention, "field": field, "reason": reason}, "clarification")
    question = first.get("question", "")
    check.equal("first_clarification.requests_expected_information",
                question.rstrip().endswith("?") and re.search(terms, question, re.I) is not None,
                True, "clarification")


def score_meal(check, case, catalog, exchange):
    request, body, oracle = exchange["request"], exchange["body"], case["expected"]
    report = body.get("report", {})
    check.equal("report.kind", report.get("kind"), "java_nutrition_report")
    check.equal("report.meal_id", report.get("meal_id"), request["entry_id"], "source_mismatch")
    check.equal("report.meal_revision", report.get("meal_revision"), request["entry_revision"], "source_mismatch")
    selection = case["selected_nutrients"]
    check.equal("report.selected_nutrients", report.get("selected_nutrients"), selection)
    rows = report.get("nutrients", [])
    check.equal("report.nutrient_ids", [row.get("id") for row in rows], selection)
    by_nutrient = {row.get("id"): row for row in rows}
    foods = {food["food_id"]: food for food in catalog["items"]}
    positions = {food["food_id"]: f"m{i}" for i, food in enumerate(case["food_mentions"], 1)}
    declarations = {food["food_id"]: food for food in case["food_mentions"]}
    peer = (exchange.get("peer") or {}).get("body") or {}
    mentions = {mention.get("mention_id"): mention for mention in peer.get("food_mentions", [])}
    check.equal("proposal.mention_count", len(peer.get("food_mentions", [])), len(positions), "source_mismatch")
    anchors = dict(zip(positions.values(), MEAL_CITATIONS[case["id"]]))
    for position, anchor in anchors.items():
        mention = mentions.get(position, {})
        equal_source(check, f"proposal.{position}.source", mention.get("source", {}), request, "user_declaration",
                     text=mention.get("text"), anchor=anchor)
    for row in oracle["nutrients"]:
        nutrient = row["id"]
        actual = by_nutrient.get(nutrient, {})
        check.value(f"{nutrient}.value", actual.get("value", MISSING), row["value"])
        check.equal(f"{nutrient}.unit", actual.get("unit"), row["unit"], "wrong_calculation")
        check.equal(f"{nutrient}.status", actual.get("status"), row["status"], "wrong_calculation")
        contributions = actual.get("provenance", [])
        check.equal(f"{nutrient}.provenance_count", len(contributions), len(row["provenance"]), "source_mismatch")
        for part, expected in zip(contributions, row["provenance"]):
            food_id = expected["food_id"]
            position = positions[food_id]
            prefix = f"{nutrient}.provenance.{position}"
            check.equal(prefix + ".mention", part.get("item_id"), position, "source_mismatch")
            quantity = part.get("quantity", {})
            value = declarations[food_id]["quantity"]["value"]
            check.equal(prefix + ".quantity", fields(quantity, ("value", "unit")),
                        {"value": value, "unit": "g"}, "source_mismatch")
            correction = food_id == case.get("state", {}).get("correction", {}).get("food_id")
            source_kind = "user_correction" if correction else "user_declaration"
            equal_source(check, prefix + ".quantity_source", quantity.get("source", {}), request, source_kind,
                         text=mentions.get(position, {}).get("text"), anchor=anchors[position])
            reference = part.get("reference", {})
            catalog_source(check, prefix + ".reference_source", reference.get("source", {}), expected)
            basis = foods[food_id]["basis"]["value"]
            ref = foods[food_id]["nutrients"][nutrient]
            check.equal(prefix + ".reference", fields(reference, ("value", "unit", "basis_mass_g")),
                        {"value": ref["value"], "unit": ref["unit"], "basis_mass_g": basis}, "source_mismatch")
            contribution = Decimal(str(value)) * Decimal(str(ref["value"])) / Decimal(str(basis))
            check.value(prefix + ".value", part.get("value", MISSING), float(contribution))
        gaps = actual.get("missing", [])
        check.equal(f"{nutrient}.missing_count", len(gaps), len(row["missing"]), "source_mismatch")
        for gap, expected in zip(gaps, row["missing"]):
            position = positions[expected["food_id"]]
            reason = MISSING_REASONS.get(expected["reason"], expected["reason"])
            prefix = f"{nutrient}.missing.{position}"
            check.equal(prefix + ".mention_reason", fields(gap, ("item_id", "reason")),
                        {"item_id": position, "reason": reason}, "source_mismatch")
            if reason == "catalog_value_absent":
                catalog_source(check, prefix + ".source", gap.get("source", {}), {
                    **expected, "catalog_id": catalog["catalog_id"], "catalog_version": catalog["version"],
                })
            else:
                equal_source(check, prefix + ".source", gap.get("source", {}), request, "user_declaration",
                             text=mentions.get(position, {}).get("text"), anchor=anchors[position])
    check.equal("report.no_energy_burned", not {"energy_burned", "net_calorie_balance"} & (body.keys() | report.keys()),
                oracle.get("no_burned_energy_inference", True), "invented_value")
    if "candidate_food_ids" in oracle:
        candidates = [candidate["record_id"] for mention in mentions.values()
                      for candidate in mention.get("catalog_candidates", [])]
        expected_candidates = sorted(oracle["candidate_food_ids"])
        category = "source_mismatch" if set(candidates) - set(expected_candidates) else "candidate_omission"
        check.equal("proposal.candidate_food_ids", sorted(candidates), expected_candidates, category)
        for mention in mentions.values():
            for candidate in mention.get("catalog_candidates", []):
                check.equal("proposal.candidate_catalog", fields(candidate, ("catalog_id", "catalog_version")),
                            {"catalog_id": catalog["catalog_id"], "catalog_version": catalog["version"]},
                            "source_mismatch")
        if oracle.get("unresolved"):
            check.equal("proposal.food_state", mentions.get("m1", {}).get("food_state"), "unknown", "source_mismatch")
            possible = {foods[food_id]["state"] for food_id in candidates if food_id in foods}
            check.equal("proposal.candidate_states", sorted(possible), sorted(oracle["unresolved"][0]["candidates"]),
                        category)
    if "preserved_quantity" in oracle:
        declared = oracle["preserved_quantity"]
        mention = mentions.get("m1", {})
        quantity = mention.get("quantity") or {}
        check.equal("proposal.preserved_quantity", fields(quantity, ("value", "unit")),
                    {"value": declared["value"], "unit": "portion" if declared["unit"] == "bol" else declared["unit"]},
                    "source_mismatch")
        if declared["unit"] == "bol":
            check.equal("proposal.preserved_bol_text", "bol" in mention.get("text", "").lower(), True, "source_mismatch")
        equal_source(check, "proposal.quantity.source", quantity.get("source", {}), request, "user_declaration")
    meal_questions(check, body, oracle)


def score_workout(check, case, exchange):
    oracle = case["expected"]
    if "sets" in oracle and "repetitions_per_set" in oracle and "total_repetitions" not in oracle:
        oracle = {**oracle, "total_repetitions": oracle["sets"] * oracle["repetitions_per_set"]}
    request, body = exchange["request"], exchange["body"]
    check.equal("workout.entry_kind", body.get("entry_kind"), "workout")
    check.equal("workout.entry_binding", fields(body, ("entry_id", "entry_revision")),
                fields(request, ("entry_id", "entry_revision")), "source_mismatch")
    check.equal("workout.activity", body.get("activity"), oracle["activity"], "source_mismatch")
    check.value("workout.energy_burned", body.get("energy_burned", MISSING), oracle["energy_burned"])
    kind = "user_correction" if request["entry_revision"] > 1 else "user_declaration"
    equal_source(check, "workout.source", body.get("source", {}), request, kind, text=request["text"])
    summary = body.get("summary", {})
    if oracle.get("derived_from"):
        field = "duration" if oracle["derived_from"] == "sum_declared_durations" else "distance"
        segment_rows = [fields(item, ("value", "unit")) for item in body.get("measures", []) if item["id"] == field]
        check.equal(field + ".segments", segment_rows, oracle["segments"], "source_mismatch")
        check.equal(field + ".operation", summary.get(field, {}).get("operation"), "sum", "wrong_calculation")
    if "total_repetitions" in oracle:
        check.equal("total_repetitions.operation", summary.get("total_repetitions", {}).get("operation"),
                    "product", "wrong_calculation")
    unresolved = {"distance": "unresolved_measure", "load": "unresolved_load"}
    for expected, field in WORKOUT_MEASURES.items():
        row = summary.get(field, {})
        if expected in oracle:
            known = oracle[expected]
            measure = known if isinstance(known, dict) else (
                {"value": known, "unit": "count"} if known is not None else {"value": None, "unit": None}
            )
            check.value(field + ".value", row.get("value", MISSING), measure["value"])
            check.equal(field + ".unit", row.get("unit", MISSING), measure["unit"], "wrong_calculation")
            status = "known" if known is not None else "unresolved" if unresolved.get(field) in oracle else "absent"
            check.equal(field + ".status", row.get("status"), oracle.get(field + "_status", status))
            if known is not None:
                check.equal(field + ".has_sources", bool(row.get("sources")), True, "source_mismatch")
        else:
            check.value(field + ".value", row.get("value", MISSING), None)
        sources = row.get("sources", [])
        check.equal(field + ".cited_fragments", [source.get("text") for source in sources],
                    SPORT_CITATIONS[case["id"]].get(field, []), "source_mismatch")
        for i, source in enumerate(sources):
            equal_source(check, f"{field}.source.{i}", source, request, kind)
        declarations = [item for item in body.get("measures", []) if item["id"] == field]
        if field != "total_repetitions":
            cited = SPORT_CITATIONS[case["id"]].get(field, [])
            expected_parts = []
            for fragment in cited:
                number, separator, written_unit = fragment.partition(" ")
                expected_parts.append({"value": int(number), "unit": SPORT_UNIT_CODES[written_unit] if separator else None})
            check.equal(field + ".declared_values", [fields(item, ("value", "unit")) for item in declarations],
                        expected_parts, "source_mismatch")
            check.equal(field + ".declared_fragments", [item.get("source", {}).get("text") for item in declarations],
                        cited, "source_mismatch")
            for item in declarations:
                equal_source(check, field + ".declared_source", item.get("source", {}), request, kind)
        if unresolved.get(field) in oracle:
            rows = [item for item in body.get("measures", []) if item["id"] == field]
            check.equal(field + ".unresolved_declaration", [fields(item, ("value", "unit")) for item in rows],
                        [oracle[unresolved[field]]], "source_mismatch")
            for item in rows:
                equal_source(check, field + ".unresolved_source", item.get("source", {}), request, kind)
    questions = body.get("clarifications", [])
    if "clarification" in oracle:
        first = questions[0] if questions else {}
        reason = "unit_absent" if oracle["clarification"]["field"].endswith(".unit") else "quantity_absent"
        check.equal("first_clarification", fields(first, ("field", "question", "reason")),
                    {**oracle["clarification"], "reason": reason}, "clarification")
    else:
        check.equal("clarifications", questions, [], "clarification")


def check_type(check, path, value, expected):
    valid = isinstance(value, expected)
    if not valid:
        check.equal(path, type(value).__name__, expected.__name__)
    return valid


def objects_in(check, path, values):
    if check_type(check, path, values, list):
        for index, value in enumerate(values):
            item_path = f"{path}[{index}]"
            if check_type(check, item_path, value, dict):
                yield item_path, value


def check_source_shape(check, path, source):
    if check_type(check, path, source, dict):
        check_type(check, path + ".text", source.get("text", ""), str)


def check_success_shape(check, label, body, *, workout, validate_branch):
    """Valide les objets parcourus avant de calculer le score métier."""
    before = len(check.failures)
    if not check_type(check, label + ".body", body, dict):
        return False

    for path, question in objects_in(check, label + ".clarifications", body.get("clarifications", [])):
        check_type(check, path + ".question", question.get("question", ""), str)

    if workout:
        if body.get("entry_kind") != "workout":
            check.equal(label + ".entry_kind", body.get("entry_kind"), "workout")
        check_source_shape(check, label + ".source", body.get("source", {}))
        summary = body.get("summary")
        if check_type(check, label + ".summary", summary, dict):
            for field, row in summary.items():
                path = f"{label}.summary.{field}"
                if check_type(check, path, row, dict):
                    for source_path, source in objects_in(check, path + ".sources", row.get("sources", [])):
                        check_type(check, source_path + ".text", source.get("text", ""), str)
        for path, measure in objects_in(check, label + ".measures", body.get("measures", [])):
            check_type(check, path + ".id", measure.get("id"), str)
            check_source_shape(check, path + ".source", measure.get("source", {}))
    else:
        report = body.get("report")
        if check_type(check, label + ".report", report, dict) and not validate_branch(report, "java_nutrition_report"):
            check.equal(label + ".report_schema_valid", False, True)
    return len(check.failures) == before


def decision(exchange, contract_ok, *, workout=False):
    if not contract_ok or exchange.get("transport_error") or exchange.get("status") is None or exchange["status"] >= 500:
        return "technical_error"
    if 400 <= exchange["status"] < 500:
        return "refusal"
    if exchange["status"] != 200:
        return "technical_error"
    body = exchange["body"]
    if body.get("clarifications"):
        return "clarification"
    if workout:
        values = body["summary"].values() if body.get("activity") else ()
    else:
        values = body.get("report", {}).get("nutrients", [])
    if any(type(row.get("value")) in (int, float) for row in values):
        return "automatic"
    return "abstention"


def score(case, route, catalog, validate_branch, observed):
    check = Checks()
    oracle, exchanges, state = case["expected"], observed["exchanges"], observed["state"]
    if observed.get("runtime_error"):
        check.equal("measurement.runtime", observed["runtime_error"], None, "runtime")
    final = exchanges.get("final", {})
    body = final["body"] if isinstance(final.get("body"), dict) else {}
    status = final.get("status")
    expected_status = 409 if route == "late_meal" else 400 if route.startswith("reject_") else 200
    check.equal("final.http_status", status, expected_status)
    contract_ok = not final.get("transport_error")
    if status != 200:
        contract_ok = check_type(check, "final.body", final.get("body"), dict) and contract_ok
    workout = "workout" in route
    if route == "late_meal" and status == 409:
        contract_ok = contract_ok and validate_branch(body, "java_analysis_rejection")
    final_proposal = {}
    for label, exchange in exchanges.items():
        peer = exchange.get("peer")
        if exchange.get("status") == 200:
            response_body = exchange.get("body")
            if label in {"final", "initial", "current", "corrected", "previous_result_after"}:
                valid_shape = check_success_shape(check, label, response_body, workout=workout,
                                                  validate_branch=validate_branch)
            else:
                valid_shape = check_type(check, label + ".body", response_body, dict)
            contract_ok = contract_ok and valid_shape
        if exchange.get("transport_error") or (exchange.get("status") or 0) >= 500:
            check.equal(label + ".transport", exchange.get("transport_error") or exchange["status"], None, "runtime")
        if label in {"final", "initial", "corrected"}:
            peer_required = exchange.get("status") == 200 or route == "late_meal" and label == "final"
            if peer or peer_required:
                valid_peer = bool(peer and peer["status"] == 200 and validate_branch(peer["body"], "python_proposal"))
                check.equal(label + ".proposal_valid", valid_peer, True, "runtime")
                if valid_peer:
                    wanted_kind = "workout" if "workout" in route else "meal"
                    payload = peer["body"]
                    check.equal(label + ".proposal_binding", fields(payload, ("entry_id", "entry_revision", "entry_kind")),
                                {**fields(exchange["request"], ("entry_id", "entry_revision")), "entry_kind": wanted_kind},
                                "source_mismatch")
                    if exchange.get("status") == 200 and wanted_kind == "workout":
                        pair = exchange.get("body")
                        pair = pair if isinstance(pair, dict) else {}
                        check.equal(label + ".workout_proposal_binding",
                                    fields(pair, ("proposal_id", "proposal_schema_version")),
                                    {"proposal_id": payload.get("proposal_id"),
                                     "proposal_schema_version": payload.get("schema_version")}, "source_mismatch")
                if label == "final":
                    contract_ok = contract_ok and valid_peer
                    if valid_peer:
                        final_proposal = peer["body"]
    check.equal("final.contract_valid", bool(contract_ok), True)
    if route.startswith("reject_"):
        check.equal("final.rejection", body.get("error"), oracle["error"]["code"])
        check.equal("final.sql_created", state.get("created"), oracle.get("report_created", oracle.get("workout_created")),
                    "unsafe_write")
        check.equal("final.sql_unchanged", state.get("sql_unchanged"), True, "unsafe_write")
    elif route == "late_meal":
        check.equal("final.rejection", fields(body, ("code", "analysis_revision", "current_revision")),
                    {"code": oracle["reason"], "analysis_revision": oracle["analyzed_revision"],
                     "current_revision": oracle["current_revision"]})
        for field, expected in [
            ("write_count", oracle["write_count"]), ("sql_unchanged", True),
            ("current_food_mentions_unchanged", oracle["current_food_mentions_unchanged"]),
            ("current_report_unchanged", oracle["current_report_unchanged"]),
            ("real_proposal_held_until_r2", True),
        ]:
            check.equal("late." + field, state.get(field), expected, "unsafe_write")
        check.equal("rejection.proposal_binding", body.get("proposal_id"), final_proposal.get("proposal_id"),
                    "source_mismatch")
        check.equal("rejection.entry_id", body.get("entry_id"), final.get("request", {}).get("entry_id"), "source_mismatch")
        energy = state.get("current_energy") or {}
        check.equal("current_energy", fields(energy, ("value", "unit", "status")), oracle["current_energy"],
                    "wrong_calculation")
        quantities = [fields(item.get("quantity") or {}, ("value", "unit")) for item in final_proposal.get("food_mentions", [])]
        check.equal("late.proposal.precorrection_quantities", quantities,
                    [mention["quantity"] for mention in case["state"]["proposal_food_mentions"]], "source_mismatch")
    else:
        if status == 200 and contract_ok:
            if route.startswith("meal"):
                score_meal(check, case, catalog, final)
            else:
                score_workout(check, case, final)
        check.equal("journal.result_readback_matches", state.get("saved_matches"), True, "unsafe_write")
        if route.endswith("_correction"):
            check.equal("journal.history_preserved", state.get("history_preserved"), oracle["history_preserved"],
                        "unsafe_write")
            check.equal("journal.current_revision", state.get("current_revision"),
                        oracle.get("meal_revision", oracle.get("workout_revision")), "unsafe_write")
            if "previous_energy" in oracle:
                check.equal("journal.previous_energy", state.get("previous_energy"), oracle["previous_energy"],
                            "wrong_calculation")
    outcome = decision(final, contract_ok and not observed.get("runtime_error"), workout=workout)
    if outcome == "automatic" and oracle["action"] in {"reject_invalid_input", "reject_stale_analysis", "clarify"}:
        check.equal("decision.safe", outcome, oracle["action"],
                    "unsafe_write" if oracle["action"].startswith("reject_") else "invented_value")
    return {"outcome": outcome, "correct": not check.failures, "checks": check.count,
            "clarification_correct": outcome == "clarification" and "clarification" in oracle
            and not any(failure["category"] == "clarification" for failure in check.failures),
            "failures": check.failures, "critical_categories": sorted({
                failure["category"] for failure in check.failures if failure["category"] in CRITICAL
            })}


def fraction(n, d):
    return {"numerator": n, "denominator": d, "value": n / d if d else None}


def metrics(rows):
    executed = [row for row in rows if row["disposition"] != "excluded"]
    eligible = [row for row in executed if row["disposition"] not in {"late_meal", "reject_meal", "reject_workout"}]
    automatic = [row for row in executed if row["score"]["outcome"] == "automatic"]
    ambiguous = [row for row in eligible if row["expects_clarification"]]
    unambiguous = [row for row in eligible if not row["expects_clarification"]]
    counts = Counter(row["score"]["outcome"] for row in executed)
    categories = Counter(category for row in executed for category in row["score"]["critical_categories"])
    latencies = sorted(row["exchanges"]["final"]["duration_ms"] for row in executed
                       if row["disposition"] != "late_meal" and "final" in row["exchanges"])
    accuracy = lambda entries: fraction(sum(row["score"]["correct"] for row in entries), len(entries))
    return {
        "corpus_cases": len(rows), "executed_cases": len(executed), "excluded_cases": len(rows) - len(executed),
        "accuracy": accuracy(executed), "automatic_precision": accuracy(automatic),
        "coverage": fraction(sum(row["score"]["outcome"] == "automatic" for row in eligible), len(eligible)),
        "unambiguous_coverage": fraction(sum(row["score"]["outcome"] == "automatic" for row in unambiguous),
                                         len(unambiguous)),
        "correct_clarification_rate": fraction(sum(row["score"]["clarification_correct"]
                                                  for row in ambiguous), len(ambiguous)),
        "technical_error_rate": fraction(counts["technical_error"], len(executed)),
        "outcome_counts": {name: counts[name] for name in (
            "automatic", "clarification", "abstention", "refusal", "technical_error"
        )},
        "critical_case_count": sum(bool(row["score"]["critical_categories"]) for row in executed),
        "critical_categories": {name: categories[name] for name in sorted(CRITICAL)},
        "accuracy_by_category": {
            category: accuracy([row for row in executed if row["category"] == category])
            for category in sorted({row["category"] for row in rows})
        },
        "accuracy_by_manual_annotation": {
            label: accuracy([row for row in executed if row["manual_checks"][label]])
            for label in ("calculation", "ambiguity")
        },
        "latency_sample_count": len(latencies),
        "latency_missing_count": sum(row["disposition"] != "late_meal" for row in executed) - len(latencies),
        **{f"latency_p{p}_ms": latencies[ceil(len(latencies) * p / 100) - 1] if latencies else None for p in (50, 95)},
    }
