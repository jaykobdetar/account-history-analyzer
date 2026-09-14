import json
from pathlib import Path
import pytest
from account_history_analyzer.io import load_snapshot
from account_history_analyzer.errors import InputError


def test_M0_gate(tmp_path):
    rows = Path('fixtures/arithmetic.jsonl').read_text().splitlines()
    a = load_snapshot('fixtures/arithmetic.jsonl', 'fixtures/arithmetic.snapshot.json')
    p = tmp_path/'records.jsonl'
    p.write_text('\n'.join(json.dumps(json.loads(x),sort_keys=False) for x in reversed(rows)))
    b = load_snapshot(p, 'fixtures/arithmetic.snapshot.json')
    assert a.canonical_sha256 == b.canonical_sha256
    assert a.receipt['duplicate_rows'] == 1
    assert len(a.records) == 6
    for bad in ('{', '{"id":"x","id":"y"}', '{"value":NaN}', json.dumps(dict(json.loads(rows[0]),created_utc='2025-02-30T00:00:00Z'))):
        p.write_text(bad+'\n')
        with pytest.raises(InputError):
            load_snapshot(p, 'fixtures/arithmetic.snapshot.json')
