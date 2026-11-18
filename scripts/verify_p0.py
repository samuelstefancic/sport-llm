"""Verify P0 schemas and fictional artifacts. No application, DB, server or model."""
import argparse
from collections import Counter
from decimal import Decimal
import hashlib
import importlib.metadata
import json
from pathlib import Path
import sys
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'build' / 'verification' / 'p0'


def reject_constant(value):
    raise ValueError('Non-JSON numeric constant: ' + value)


def unique_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate JSON key: ' + key)
        result[key] = value
    return result


def read(path):
    return json.loads(path.read_text(), parse_constant=reject_constant,
                      object_pairs_hook=unique_keys)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def number(value):
    return Decimal(str(value))


def error_tree(errors):
    for error in errors:
        yield error
        yield from error_tree(error.context)


def fixture_report_problems(doc):
    """Inspect arithmetic already present in a fixture, not an application calculator."""
    issues = []
    ids = [row['id'] for row in doc['nutrients']]
    if len(ids) != len(set(ids)):
        issues.append('duplicate_nutrient')
    if set(ids) != set(doc['selected_nutrients']):
        issues.append('selection_mismatch')
    for row in doc['nutrients']:
        contributions = row['provenance']
        known_ids = [x['item_id'] for x in contributions]
        missing_ids = [x['item_id'] for x in row['missing']]
        if len(known_ids) != len(set(known_ids)) or set(known_ids) & set(missing_ids):
            issues.append('duplicate_contribution')
        for part in contributions:
            expected = (number(part['quantity']['value']) * number(part['reference']['value'])
                        / number(part['reference']['basis_mass_g']))
            if number(part['value']) != expected:
                issues.append('wrong_contribution')
        total = sum((number(x['value']) for x in contributions), Decimal(0)) if contributions else None
        if total != (None if row['value'] is None else number(row['value'])):
            issues.append('wrong_arithmetic')
    return sorted(set(issues))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--environment', type=Path,
                        help='Observed local package cache paths; installs nothing')
    args = parser.parse_args()
    if args.environment:
        env = read(args.environment)
        if Path(sys.executable).resolve() != Path(env['python']).resolve():
            raise RuntimeError('Use the Python interpreter recorded in environment.json')
        sys.path[:0] = env['package_paths']
    from jsonschema import Draft202012Validator
    from referencing import Registry, Resource

    schema_path = ROOT / 'contracts/analysis.schema.json'
    schema = read(schema_path)
    Draft202012Validator.check_schema(schema)
    registry = Registry().with_resource(schema['$id'], Resource.from_contents(schema))
    validator = Draft202012Validator(schema, registry=registry)
    manifest = read(ROOT / 'contracts/examples/manifest.json')
    example_results = []
    for item in manifest['examples']:
        path = ROOT / 'contracts/examples' / item['file']
        doc = read(path)
        errors = list(validator.iter_errors(doc))
        actual = not errors
        assert actual == item['expected_schema_valid'], (item['id'], errors)
        all_errors = list(error_tree(errors))
        if 'expected_failure_path' in item:
            assert any(list(e.absolute_path) == item['expected_failure_path'] for e in all_errors), item['id']
        issues = fixture_report_problems(doc) if actual and doc['kind'] == 'java_nutrition_report' else []
        outcome = item['expected_business_outcome']
        if outcome == 'reject_wrong_arithmetic':
            assert 'wrong_arithmetic' in issues
        elif outcome == 'reject_duplicate_nutrient':
            assert 'duplicate_nutrient' in issues
        elif actual and doc['kind'] == 'java_nutrition_report':
            assert not issues, (item['id'], issues)
        receiver_accepted = None
        if item.get('expected_receiver_branch'):
            receiver = Draft202012Validator(
                {'$ref': schema['$id'] + '#/$defs/' + item['expected_receiver_branch']},
                registry=registry)
            receiver_accepted = receiver.is_valid(doc)
            assert receiver_accepted is False, item['id']
        example_results.append({'id': item['id'], 'status': 'PASS',
                                'schema_valid': actual, 'expected_schema_valid': item['expected_schema_valid'],
                                'schema_error_count': len(errors),
                                'expected_failure_path': item.get('expected_failure_path'),
                                'fixture_consistency_issues': issues,
                                'receiver_branch_accepted': receiver_accepted,
                                'business_outcome_prepared': outcome, 'sha256': digest(path)})

    corpus_path = ROOT / 'data/dev/cases.json'
    catalog_path = ROOT / 'data/dev/catalog.json'
    corpus, catalog = read(corpus_path), read(catalog_path)
    cases = corpus['cases']
    counts = dict(Counter(c['category'] for c in cases))
    assert counts == {'food': 15, 'sport': 10, 'mixed_or_ambiguous': 5}
    assert len(cases) == len({c['id'] for c in cases}) == 30
    assert corpus['purpose'] == 'development_only' and corpus['not_independent_final_test'] is True
    ids = {c['id'] for c in cases}
    assert ids == {f'F{i:02}' for i in range(1, 16)} | {f'S{i:02}' for i in range(1, 11)} | {f'M{i:02}' for i in range(1, 6)}
    manual_ids = {kind: [c['id'] for c in cases if c['manual_checks'][kind]]
                  for kind in ('calculation', 'ambiguity')}
    assert all(len(v) == 10 for v in manual_ids.values())
    assert catalog['fictitious'] is True and catalog['version'] == corpus['catalog_version']
    foods = {x['food_id']: x for x in catalog['items']}
    assert len(foods) == len(catalog['items'])
    units = {x['id']: x['unit'] for x in catalog['nutrient_definitions']}
    for food in foods.values():
        assert food['basis'] == {'value': 100, 'unit': 'g'}
        for nutrient_id, nutrient in food['nutrients'].items():
            assert nutrient['unit'] == units[nutrient_id]
            assert (nutrient['value'] is None) == (nutrient['availability'] == 'absent')
    for case in cases:
        assert case['input'] and case['expected_behavior'] and case['expected'] and case['group_id']
        assert case['split'] == 'development' and case['fictitious'] is True
        source = case['fixture_refs']['catalog']
        if source:
            assert source['version'] == catalog['version'] and source['catalog_id'] == catalog['catalog_id']
            assert (corpus_path.parent / source['file']).is_file()
        for mention in case.get('food_mentions', []):
            assert mention['food_id'] is None or mention['food_id'] in foods
        nutrients = case['expected'].get('nutrients', case['expected'].get('meal', {}).get('nutrients', []))
        if nutrients:
            assert {x['id'] for x in nutrients} == set(case['selected_nutrients'])
        for row in nutrients:
            assert row['unit'] == units[row['id']]
            assert (row['value'] is None) == (row['status'] == 'indéterminé')
            assert bool(row['provenance']) == (row['status'] != 'indéterminé')
            assert bool(row['missing']) == (row['status'] != 'complet')
            for provenance in row['provenance']:
                assert provenance['catalog_version'] == catalog['version']
                assert provenance['food_id'] in foods and provenance['field'] == row['id']
                assert foods[provenance['food_id']]['nutrients'][row['id']]['value'] is not None

    scenario = read(ROOT / 'contracts/examples/revision-scenario.json')
    stale = read(ROOT / 'contracts/examples/python-stale-revision.json')
    rejection = read(ROOT / 'contracts/examples/java-stale-rejection.json')
    assert validator.is_valid(stale) and validator.is_valid(rejection)
    assert stale['entry_revision'] == rejection['analysis_revision'] == 1
    assert scenario['current_state']['meal_revision'] == rejection['current_revision'] == 2
    assert scenario['expected']['writes'] == 0 and rejection['code'] == 'stale_revision'
    assert scenario['expected']['meal_revision_after'] == scenario['current_state']['meal_revision']
    assert scenario['expected']['rice_g_after'] == scenario['current_state']['rice_g']
    assert scenario['expected']['report_after'] == scenario['current_state']['report_file']
    f11 = next(c for c in cases if c['id'] == 'F11')
    assert f11['expected']['reason'] == rejection['code'] and f11['expected']['write_count'] == 0

    result = {'observed_at': datetime.now(timezone.utc).isoformat(), 'status': 'PASS',
              'command': [sys.executable, '-B', 'scripts/verify_p0.py', *sys.argv[1:]],
              'validator': {'library': 'jsonschema', 'version': importlib.metadata.version('jsonschema'),
                            'draft': '2020-12', 'meta_schema': 'PASS', 'installed_for_this_task': False},
              'schema_sha256': digest(schema_path), 'examples': example_results,
              'corpus': {'count': len(cases), 'distribution': counts,
                         'group_count': len({c['group_id'] for c in cases}), 'manual_oracle_ids': manual_ids,
                         'structural_and_reference_checks': 'PASS',
                         'cases_sha256': digest(corpus_path), 'catalog_sha256': digest(catalog_path),
                         'oracles_sha256': digest(ROOT / 'data/dev/oracles.md')},
              'revision_fixture_coherence': 'PASS; static expected outcome, not a transactional execution',
              'scope': 'P0 fixture/schema checks only; no Java, DB transaction, model or deployment executed'}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'validation.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'status': result['status'], 'schema_examples': len(example_results),
                      'schema_accepted': sum(x['schema_valid'] for x in example_results),
                      'schema_rejected_as_expected': sum(not x['schema_valid'] for x in example_results),
                      'corpus': len(cases), 'distribution': counts}, ensure_ascii=False))


if __name__ == '__main__':
    if not __debug__:
        sys.exit('Assertions must be enabled (remove -O or PYTHONOPTIMIZE).')
    main()
