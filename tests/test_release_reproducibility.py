"""Release-audit helper checks; these never execute an analyzer before freeze."""
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('release_reproduction',ROOT/'scripts/check_release_reproducibility.py')
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


def test_recursive_object_reordering_preserves_values_and_list_order():
    original = {'a':[{'x':1,'y':2},'literal'], 'b':{'first':True,'last':None}}
    reordered = audit.reverse_keys(original)
    assert reordered == original
    assert list(reordered) == ['b','a']
    assert list(reordered['a'][0]) == ['y','x']
    assert list(reordered['b']) == ['last','first']
    assert original['a'][1] == 'literal'


def _artifacts(directory):
    manifest = {}
    for name in audit.REQUIRED:
        data = ('actual artifact '+name).encode()
        (directory/name).write_bytes(data)
        manifest[name] = audit.sha256(data)
    (directory/'checksums.json').write_bytes(audit.canonical(manifest))
    (directory/'ingest_receipt.json').write_text('{}')
    (directory/'run_receipt.json').write_text(json.dumps({'network_isolation':'linux_seccomp_socket_denial'}))


def test_all_checksums_and_checksum_manifest_are_compared_but_receipts_are_separate(tmp_path):
    _artifacts(tmp_path)
    actual, receipts = audit.inspect_artifacts(tmp_path)
    assert set(actual) == audit.REQUIRED | {'checksums.json'}
    assert set(receipts) == audit.RECEIPTS
    assert not set(actual) & audit.RECEIPTS


@pytest.mark.parametrize('corruption', ['changed','extra','missing','no_network_receipt'])
def test_release_inspection_refuses_corruption_or_unaccounted_output(tmp_path,corruption):
    _artifacts(tmp_path)
    if corruption == 'changed':
        (tmp_path/'report.html').write_text('changed')
    elif corruption == 'extra':
        (tmp_path/'unknown-output.json').write_text('{}')
    elif corruption == 'missing':
        (tmp_path/'surface_features.svg').unlink()
    else:
        (tmp_path/'run_receipt.json').write_text('{}')
    with pytest.raises(ValueError):
        audit.inspect_artifacts(tmp_path)
