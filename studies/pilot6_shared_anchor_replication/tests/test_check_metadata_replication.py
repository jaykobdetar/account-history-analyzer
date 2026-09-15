"""Fabricated metadata only; no real records or analyzer execution."""
from fractions import Fraction
import importlib.util
import json
from pathlib import Path
import pytest

from test_metadata_replication_independent import registered_fixture, exact_small, m, put

SPEC = importlib.util.spec_from_file_location('independent_pilot6_saved_check',
    Path(__file__).parents[1] / 'scripts/check_metadata_replication.py')
c = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(c)


def fixture(tmp_path, monkeypatch):
    plan, source, rows, calls = registered_fixture(tmp_path, monkeypatch)
    public, private = tmp_path / 'public', tmp_path / 'private'
    m.run(plan, public, private)
    return plan, public, private


def check(plan, public, private):
    return c.verify(plan, public, private, matching_factory=lambda config, callback: exact_small)


def test_independent_whole_prefix_endpoints_ties_and_median():
    cut = 180 * 86400
    rows = [(0, 'outer-included', 125)] + [(cut - i, f'r{i:02d}', 125) for i in range(1, 40)]
    rows += [(-1, 'before-band', 500), (cut, 'on-cut-late', 500)]
    selected = c.prefix(rows, cut, True)
    assert selected['records'] == 40 and selected['words'] == 5000
    assert selected['median'] == Fraction(2 * cut - 41, 2)
    assert selected['rows'][0][1] == 'outer-included'
    late = [(cut + i, f'r{i:02d}', 125) for i in range(40)] + [(2 * cut, 'outside', 500)]
    assert c.prefix(late, cut, False)['rows'][0][0] == cut
    assert c.prefix(late[:39] + [late[-1]], cut, False) is None


def test_prefix_must_fail_instead_of_skipping_large_closing_comment():
    rows = [(100 + i, str(i), 130) for i in range(39)] + [(139, 'last', 500), (140, 'shorter', 20)]
    assert c.prefix(rows, 100, False) is None  # 5,570 at the required fortieth record
    rows[39] = (139, 'last', 430)
    assert c.prefix(rows, 100, False)['words'] == 5500


def test_primary_windows_need_both_thresholds_and_residual_is_not_qualified():
    assert c.qualified_windows([(i, str(i), 125) for i in range(80)]) == 10
    assert c.qualified_windows([(i, str(i), 500) for i in range(7)]) == 0
    assert c.qualified_windows([(i, str(i), 125) for i in range(79)]) == 9


def test_late_median_gate_excludes_anchor_date_and_is_inclusive():
    def cell(median):
        return {'rows': [(i, str(i), 125) for i in range(40)], 'records': 40,
                'words': 5000, 'median': Fraction(median)}
    cells = [cell(-1000 * 86400), cell(0), cell(30 * 86400), cell(0), cell(0)]
    result = c.metrics(cells)
    assert result['valid'] and result['cost'] == Fraction(1, 2)
    cells[-1]['median'] = Fraction(30 * 86400 + 1)
    assert 'four_late_median_span_above_30_days' in c.metrics(cells)['reason_codes']


def test_independent_all_505_cuts_global_matching_round_trip(tmp_path, monkeypatch):
    plan, public, private = fixture(tmp_path, monkeypatch)
    result = check(plan, public, private)
    assert result['status'] == 'passed' and result['calendar_pair_cuts_verified'] == 505
    assert result['global_maximum_matching_pairs'] == result['provisional_pairs_verified'] == 2
    assert result['unique_valid_edges_verified'] == 3 and result['protected_accounts_excluded'] == 119
    assert result['style_calls'] == result['preprocessor_calls'] == 0
    assert not any(name in json.dumps(result) for name in ('account_a', 'account_b', 'record_id'))


@pytest.mark.parametrize('mutation', ['cost', 'windows', 'missing', 'duplicate', 'stratum'])
def test_direction_mutations_are_detected_independently(tmp_path, monkeypatch, mutation):
    plan, public, private = fixture(tmp_path, monkeypatch)
    path = private / 'directional-evaluations.jsonl'
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    if mutation == 'cost':
        rows[0]['cost']['numerator'] += 1
    elif mutation == 'windows':
        rows[0]['qualified_window_counts'][0] += 1
    elif mutation == 'missing':
        rows.pop(0)
    elif mutation == 'duplicate':
        rows.insert(0, rows[0])
    else:
        rows[0]['stratum_id'] = 'stratum-99'
    path.write_text(''.join(json.dumps(r) + '\n' for r in rows))
    with pytest.raises(ValueError):
        check(plan, public, private)


@pytest.mark.parametrize('target', ['cut', 'best', 'matching', 'pool', 'summary', 'source'])
def test_output_and_source_mutations_are_refused(tmp_path, monkeypatch, target):
    plan, public, private = fixture(tmp_path, monkeypatch)
    if target == 'cut':
        path = public / 'all-calendar-cuts.json'; doc = c.read(path)
        doc[0]['directions_without_anchor'] += 1
    elif target == 'best':
        path = private / 'best-edge-directions.json'; doc = c.read(path)
        doc[0]['cut'] = '2010-01-01T00:00:00Z'
    elif target == 'matching':
        path = private / 'provisional-pairs.json'; doc = c.read(path)
        doc['matching']['cardinality'] = 1
    elif target == 'pool':
        path = private / 'provisional-pairs.json'; doc = c.read(path)
        doc['pairs'].reverse()
    elif target == 'summary':
        path = public / 'feasibility-summary.json'; doc = c.read(path)
        doc['counts']['eligible_rows'] += 1
    else:
        path = Path(c.read(plan)['source_metadata'][0]['path'])
        before = path.read_bytes()
        path.write_bytes(before.replace(b'"retained_words": 125', b'"retained_words": 124', 1))
        with pytest.raises(ValueError):
            check(plan, public, private)
        return
    put(path, doc)
    with pytest.raises(ValueError):
        check(plan, public, private)


def test_checker_accepts_legacy_unavailable_null_and_refuses_eligible_null(tmp_path, monkeypatch):
    extra = {'record_id': 'legacy-null', 'account_key': 'legacy-account', 'community': 'AskAcademia',
             'reason': 'unavailable', 'retained_words': None, 'created_utc': None}
    plan, source, rows, calls = registered_fixture(tmp_path, monkeypatch, [extra])
    public, private = tmp_path/'public', tmp_path/'private'
    m.run(plan, public, private)
    result = check(plan, public, private)
    assert result['counts']['ineligible_rows'] == 1
    doc = c.read(plan)
    source.write_text(source.read_text().replace('"reason": "unavailable"', '"reason": null'))
    with pytest.raises(ValueError):
        c.checked_sources(doc, set(), lambda: None)
