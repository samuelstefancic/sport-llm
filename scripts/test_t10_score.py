"""Contre-exemples fictifs du barème seul. Aucun service ni run MLflow."""

from copy import deepcopy
from pathlib import Path
from shutil import copyfile
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest import TestCase, main
from unittest.mock import patch

from evaluate_t10 import FILES, PROTOCOL, ROOT, ProtocolError, frozen, run_correction, semantic
from t10_score import Checks, MISSING, decision, fraction, score, score_workout


PROTOCOL_DATA, DESIGN, CATALOG = frozen(ROOT)
CASES = {case["id"]: case for case, _ in DESIGN}


def source(body, excerpt, kind="user_declaration"):
    return {"kind": kind, "input_id": body["entry_id"], "input_revision": body["entry_revision"], "text": excerpt}


def workout(case_id, declarations, summaries, *, question=None):
    case = CASES[case_id]
    request = {"entry_id": case_id, "entry_revision": 1, "text": case["input"]}
    measures = [{"id": field, "value": value, "unit": unit, "source": source(request, fragment)}
                for field, value, unit, fragment in declarations]
    summary = {field: {"status": "absent", "value": None, "unit": None, "sources": []}
               for field in ("duration", "distance", "sets", "repetitions", "load", "total_repetitions")}
    for field, value, unit, operation, fragments in summaries:
        summary[field] = {"status": "known" if value is not None else "unresolved", "value": value, "unit": unit,
                          "operation": operation, "sources": [source(request, part) for part in fragments]}
    body = {"entry_kind": "workout", "entry_id": case_id, "entry_revision": 1,
            "activity": case["expected"]["activity"], "energy_burned": None,
            "source": source(request, case["input"]), "summary": summary, "measures": measures,
            "clarifications": [question] if question else []}
    return {"request": request, "status": 200, "body": body, "peer": {"status": 200, "body": {"fictitious": True}}}


class ScoringTest(TestCase):
    def test_zero_missing_and_undefined_precision(self):
        check = Checks()
        check.value("explicit_zero", 0, 0)
        check.value("invented_zero", 0, None)
        check.value("missing", MISSING, None)
        check.value("boolean", False, 0)
        self.assertEqual([x["category"] for x in check.failures],
                         ["invented_value", "wrong_calculation", "wrong_calculation"])
        self.assertIsNone(fraction(0, 0)["value"])
        response = {"status": 200, "body": {"report": {"nutrients": [{"value": 0}]}}}
        self.assertEqual(decision(response, True), "automatic")
        response["body"]["report"]["nutrients"][0]["value"] = None
        self.assertEqual(decision(response, True), "abstention")

    def test_s01_rejects_reversed_source_texts_and_activity_only(self):
        sample = workout("S01", [
            ("duration", 20, "min", "20 minutes"), ("duration", 10, "min", "10 minutes"),
        ], [("duration", 30, "min", "sum", ["20 minutes", "10 minutes"])])
        check = Checks()
        score_workout(check, CASES["S01"], sample)
        self.assertFalse(check.failures)
        row = sample["body"]["summary"]["duration"]
        row["sources"].reverse()
        check = Checks()
        score_workout(check, CASES["S01"], sample)
        self.assertIn("duration.cited_fragments", [f["field"] for f in check.failures])
        row["sources"] = [source(sample["request"], "Course")]
        check = Checks()
        score_workout(check, CASES["S01"], sample)
        self.assertIn("duration.cited_fragments", [f["field"] for f in check.failures])

    def test_s07_safe_product_and_unresolved_load(self):
        sample = workout("S07", [
            ("sets", 3, "count", "3 séries"), ("repetitions", 10, "count", "10 répétitions"), ("load", 40, None, "40"),
        ], [
            ("sets", 3, "count", "declared", ["3 séries"]), ("repetitions", 10, "count", "declared", ["10 répétitions"]),
            ("load", None, None, None, ["40"]), ("total_repetitions", 30, "count", "product", ["3 séries", "10 répétitions"]),
        ], question={**CASES["S07"]["expected"]["clarification"], "reason": "unit_absent"})
        check = Checks()
        score_workout(check, CASES["S07"], sample)
        self.assertFalse(check.failures)
        sample["body"]["measures"][2]["value"] = 400
        check = Checks()
        score_workout(check, CASES["S07"], sample)
        self.assertIn("load.declared_values", [f["field"] for f in check.failures])
        sample["body"]["summary"]["load"].update(value=40, unit="kg", status="known")
        check = Checks()
        score_workout(check, CASES["S07"], sample)
        self.assertIn("invented_value", [f["category"] for f in check.failures])

    def test_workout_null_summary_row_remains_a_case_error(self):
        sample = workout("S01", [], [])
        sample["body"]["summary"]["duration"] = None
        observed = {"exchanges": {"final": sample}, "state": {"saved_matches": True}}
        graded = score(CASES["S01"], "workout", CATALOG, lambda *_: True, observed)
        self.assertFalse(graded["correct"])
        self.assertEqual(graded["outcome"], "technical_error")
        self.assertIn("final.summary.duration", [failure["field"] for failure in graded["failures"]])

    def test_workout_malformed_nested_values_produce_contract_diagnostics(self):
        for patches, field in [
            ({"measures": {}}, "measures"), ({"measures": [0]}, "measures[0]"),
            ({"measures": [{}]}, "measures[0].id"),
            ({"measures": [{"id": "duration", "source": []}]}, "measures[0].source"),
            ({"summary": {"duration": {"sources": None}}}, "summary.duration.sources"),
            ({"summary": {"duration": {"sources": [None]}}}, "summary.duration.sources[0]"),
            ({"source": []}, "source"),
            ({"clarifications": {}}, "clarifications"), ({"clarifications": [None]}, "clarifications[0]"),
            ({"clarifications": [{"question": None}]}, "clarifications[0].question"),
        ]:
            with self.subTest(field=field):
                sample = workout("S01", [], [])
                sample["body"].update(patches)
                observed = {"exchanges": {"final": sample}, "state": {"saved_matches": True}}
                result = score(CASES["S01"], "workout", CATALOG, lambda *_: True, observed)
                self.assertEqual(result["outcome"], "technical_error")
                self.assertTrue(any(failure["field"] == f"final.{field}" and failure["category"] == "contract"
                                    for failure in result["failures"]))

    def test_malformed_initial_workout_does_not_interrupt_correction(self):
        initial = {"status": 200, "body": {"entry_kind": "workout", "summary": {"duration": None}}}
        final = workout("S09", [], [])
        exchanges = {}

        def post(label, body):
            exchanges[label] = {**(initial if label == "initial" else final), "request": body}
            return exchanges[label]

        def fetch(label, _):
            if label == "previous_result_after":
                return initial
            return {"status": 200, "body": {"text": "Vélo : 60 min."}}

        trace = SimpleNamespace(entry="S09", state={}, post=post, fetch=fetch)
        with patch("evaluate_t10.side_effects"):
            run_correction(None, trace, CASES["S09"], "workout_correction", {})
        self.assertEqual(exchanges["final"]["request"]["text"], CASES["S09"]["input"])
        self.assertFalse(trace.state["history_preserved"])
        observed = {"exchanges": exchanges, "state": trace.state}
        result = score(CASES["S09"], "workout_correction", CATALOG, lambda *_: True, observed)
        self.assertEqual(result["outcome"], "technical_error")
        self.assertIn("initial.summary.duration", [failure["field"] for failure in result["failures"]])

    def test_f10_malformed_initial_report_does_not_interrupt_correction(self):
        for body in ([], "invalid", {"report": None}):
            with self.subTest(body=body):
                initial = {"status": 200, "body": body}
                final = {"status": 200, "body": {"report": {}}}
                exchanges = {}

                def post(label, request):
                    exchanges[label] = {**(initial if label == "initial" else final), "request": request}
                    return exchanges[label]

                def fetch(label, _):
                    if label == "previous_result_after":
                        return initial
                    return {"status": 200, "body": {"text": "150 g de riz cuit, 100 g de poulet cuit"}}

                trace = SimpleNamespace(entry="F10", state={}, post=post, fetch=fetch)
                with patch("evaluate_t10.side_effects"):
                    run_correction(None, trace, CASES["F10"], "meal_correction", {})
                self.assertEqual(exchanges["final"]["request"]["text"], CASES["F10"]["input"])
                observed = {"exchanges": exchanges, "state": trace.state}
                result = score(CASES["F10"], "meal_correction", CATALOG, lambda *_: True, observed)
                self.assertEqual(result["outcome"], "technical_error")
                path = "initial.report" if isinstance(body, dict) else "initial.body"
                self.assertIn(path, [failure["field"] for failure in result["failures"]])

    def test_non_object_rejection_is_a_case_error(self):
        for case_id, route, status in (("F11", "late_meal", 409), ("F15", "reject_meal", 400)):
            for body in (["error"], "error"):
                with self.subTest(case=case_id, body=body):
                    final = {"status": status, "body": body, "request": {"entry_id": case_id}}
                    observed = {"exchanges": {"final": final}, "state": {}}
                    result = score(CASES[case_id], route, CATALOG, lambda *_: False, observed)
                    self.assertEqual(result["outcome"], "technical_error")
                    self.assertIn("final.body", [failure["field"] for failure in result["failures"]])

    def test_positive_final_with_missing_peer_is_technical_error(self):
        sample = workout("S01", [], [])
        sample["peer"] = None
        observed = {"exchanges": {"final": sample}, "state": {"saved_matches": True}}
        graded = score(CASES["S01"], "workout", CATALOG, lambda *_: True, observed)
        self.assertFalse(graded["correct"])
        self.assertEqual(graded["outcome"], "technical_error")

    def test_f06_omitted_candidates_are_not_a_critical_source_attribution(self):
        case = CASES["F06"]
        request = {"entry_id": "F06", "entry_revision": 1, "text": case["input"]}
        binding = source(request, "100 g de riz")
        proposal = {"entry_id": "F06", "entry_revision": 1, "entry_kind": "meal", "food_mentions": [{"mention_id": "m1", "text": binding["text"], "source": binding,
                                       "food_state": "unknown", "catalog_candidates": []}]}
        body = {"report": {"kind": "java_nutrition_report", "meal_id": "F06", "meal_revision": 1,
                           "selected_nutrients": ["energy"], "nutrients": [
                               {"id": "energy", "value": None, "unit": "kcal", "status": "indéterminé",
                                "provenance": [], "missing": [
                                    {"item_id": "m1", "reason": "raw_cooked_unknown", "source": binding},
                                ]},
                           ]},
                "clarifications": [{"mention_id": "m1", "field": "food_state", "reason": "raw_cooked_unknown",
                                    "question": "Le riz a-t-il été pesé cru ou cuit ?"}]}
        observed = {"exchanges": {"final": {"status": 200, "body": body, "request": request,
                                            "peer": {"status": 200, "body": proposal}}},
                    "state": {"saved_matches": True}}
        actual = score(case, "meal", CATALOG, lambda *_: True, observed)
        self.assertTrue(actual["clarification_correct"])
        self.assertFalse(actual["correct"])
        self.assertEqual(actual["critical_categories"], [])
        proposal["food_mentions"][0]["catalog_candidates"].append(
            {"record_id": "D04", "catalog_id": "DEMO-FOOD", "catalog_version": "0.2.0"})
        altered = score(case, "meal", CATALOG, lambda *_: True, observed)
        self.assertEqual(altered["critical_categories"], ["source_mismatch"])

    def test_f10_quantity_source_attaches_correction_to_rice_only(self):
        case = CASES["F10"]
        request = {"entry_id": "F10", "entry_revision": 2, "text": case["input"]}
        fragments = ["riz cuit, 100 g", "le poulet cuit reste à 100 g"]
        mentions = [{"text": part, "mention_id": f"m{i}", "source": source(request, part)}
                    for i, part in enumerate(fragments, 1)]
        contributions = [
            {"item_id": f"m{i}", "value": value,
             "quantity": {"value": 100, "unit": "g", "source": source(request, part, kind)},
             "reference": {"value": value, "unit": "kcal", "basis_mass_g": 100,
                           "source": {"kind": "catalog", "catalog_id": "DEMO-FOOD", "catalog_version": "0.2.0",
                                      "record_id": food, "field": "nutrients.energy"}}}
            for i, (part, kind, value, food) in enumerate(zip(
                fragments, ("user_correction", "user_declaration"), (130, 165), ("D01", "D02")), 1)
        ]
        proposal = {"entry_id": "F10", "entry_revision": 2, "entry_kind": "meal", "food_mentions": mentions}
        exchange = {"request": request, "status": 200, "peer": {"status": 200, "body": proposal},
                    "body": {"report": {"kind": "java_nutrition_report", "meal_id": "F10", "meal_revision": 2,
                                        "selected_nutrients": ["energy", "protein"], "nutrients": [
                                            {"id": "energy", "value": 295, "unit": "kcal", "status": "complet",
                                             "provenance": contributions, "missing": []},
                                        ]}, "clarifications": []}}
        observed = {"exchanges": {"final": exchange}, "state": {"saved_matches": True, "history_preserved": True,
                                                               "current_revision": 2,
                                                               "previous_energy": case["expected"]["previous_energy"]}}
        original = score(case, "meal_correction", CATALOG, lambda *_: True, observed)
        self.assertFalse(any(f["field"].startswith("energy.provenance") for f in original["failures"]))
        contributions[0]["quantity"]["source"]["kind"] = "user_declaration"
        contributions[1]["quantity"]["source"]["kind"] = "user_correction"
        changed = score(case, "meal_correction", CATALOG, lambda *_: True, observed)
        self.assertIn("energy.provenance.m1.quantity_source.binding", [f["field"] for f in changed["failures"]])
        self.assertIn("energy.provenance.m2.quantity_source.binding", [f["field"] for f in changed["failures"]])
        swapped = deepcopy(observed)
        swapped["exchanges"]["final"]["peer"]["body"]["food_mentions"][0].update(
            text=fragments[1], source=source(request, fragments[1]))
        mutated = score(case, "meal_correction", CATALOG, lambda *_: True, swapped)
        self.assertIn("proposal.m1.source.text_matches_expected_mention", [f["field"] for f in mutated["failures"]])

    def test_semantic_comparison_observes_values_but_not_timing_or_identifiers(self):
        original = {"duration_ms": 123, "correlation_id": "old", "body": {"proposal_id": "old", "value": 0}}
        copy = {"duration_ms": 321, "correlation_id": "new", "body": {"proposal_id": "new", "value": 0}}
        self.assertEqual(semantic(original), semantic(copy))
        copy["body"]["value"] = None
        self.assertNotEqual(semantic(original), semantic(copy))

    def test_changed_catalog_bytes_refused_before_service(self):
        with TemporaryDirectory(prefix="t10-score-") as temp:
            root = Path(temp)
            for relative in FILES | {PROTOCOL}:
                target = root / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                copyfile(ROOT / relative, target)
            with (root / "data/dev/catalog.json").open("ab") as stream:
                stream.write(b" ")
            with self.assertRaisesRegex(ProtocolError, "Empreinte différente : data/dev/catalog.json"):
                frozen(root)


if __name__ == "__main__":
    main()
