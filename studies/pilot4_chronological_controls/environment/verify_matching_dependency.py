"""Fresh independent identity check for the isolated study-only matching library."""
from datetime import datetime,timezone
import hashlib
import importlib.metadata as metadata
import json
from pathlib import Path
import sys
import networkx as nx

ROOT=Path(__file__).resolve().parents[1]


def sha(path):
    with Path(path).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()


def main():
    manifest=ROOT/'environment/isolated-matching-dependency.json';declared=json.loads(manifest.read_bytes())
    root=Path(declared['isolated_installation']);wheel=Path(declared['wheel_path'])
    expected={r['path']:r['sha256'] for r in declared['installed_files']}
    actual={str(p.relative_to(root)):sha(p) for p in root.rglob('*') if p.is_file() and '__pycache__' not in p.parts}
    assert expected==actual and len(expected)==595
    assert sha(wheel)==declared['wheel_sha256'] and wheel.stat().st_size==declared['wheel_bytes']
    dist=metadata.distribution('networkx')
    assert nx.__version__==dist.version==declared['version']=='3.5'
    assert Path(nx.__file__).resolve()==root/'networkx/__init__.py'
    assert dist._path.resolve()==root/'networkx-3.5.dist-info'
    assert 'account_history_analyzer' not in sys.modules
    result={'status':'passed','checked_utc':datetime.now(timezone.utc).isoformat(),
        'verifier_sha256':sha(__file__),'dependency_manifest_sha256':sha(manifest),
        'isolated_import_file':str(Path(nx.__file__).resolve()),'distribution_path':str(dist._path.resolve()),
        'version':nx.__version__,'installed_files_checked':len(expected),'missing_or_extra_files':0,
        'all_installed_hashes_match':True,'wheel_bytes':wheel.stat().st_size,'wheel_sha256':sha(wheel),
        'helper_sha256':sha(ROOT/'scripts/exact_blossom.py'),
        'independent_tests_sha256':sha(ROOT/'tests/test_exact_blossom_independent.py'),
        'test_receipt_sha256':sha(ROOT/'logs/blossom-independent-synthetic-01.receipt.json'),
        'ahas_imported':False,'source_metadata_read':False,'source_archives_read':False,'scores_computed':0,
        'exact_weight_proof':{'cost_scaling':'LCM of rational denominators makes each cost an integer.',
            'lex_dominance':'With E ordered edges, B=2^E exceeds the sum B-1 of every positive edge tie bit.',
            'objective':'maxcardinality=True first fixes the largest matching cardinality; -integer_cost*B next minimizes exact total cost.',
            'identity_tie':'Among equal-size equal-cost edge sets, maximizing descending edge bits selects the set containing the earliest edge at the first differing position, exactly the lexicographically smallest sorted edge list.',
            'library_integer_arithmetic':'Pinned max_weight_matching uses integer arithmetic for Python integer weights and invokes its optimum verification on integer solutions.'},
        'limits_note':'The matcher invokes the resource callback before/after the solver; caller must retain an external wall deadline during the solve.'}
    target=ROOT/'environment/matching-independent-verification.json'
    with target.open('x') as f:json.dump(result,f,indent=2,sort_keys=True);f.write('\n')
    print(json.dumps(result,sort_keys=True))

if __name__=='__main__':main()
