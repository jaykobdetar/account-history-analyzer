"""Synthetic preservation tests. Fixtures stay under this new environment tree."""
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import pytest

SPEC = importlib.util.spec_from_file_location('pilot6_preservation', Path(__file__).with_name('preserve_prior_studies.py'))
p = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(p)


@pytest.fixture
def temp():
    with tempfile.TemporaryDirectory(prefix='synthetic-', dir=Path(__file__).parent) as directory:
        yield Path(directory)


def describe(path, root):
    return {'path': path.relative_to(root).as_posix(), 'bytes': path.stat().st_size, 'sha256': p.sha(path)}


def put(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value)+'\n')


def fixture(root):
    repository, private = root/'repository', root/'private'
    for key, name in p.STUDIES.items():
        public_root=repository/'studies'/name;public_root.mkdir(parents=True)
        (public_root/'README.md').write_text('synthetic public document\n')
        private_root=private/(key+'_private');private_root.mkdir(parents=True)
        (private_root/'secret-input.json').write_text('{"synthetic":true}\n')
    external=root/'external-secret-source.json'
    external.write_text('{"synthetic":true}\n')
    manifest=root/'external-secret-snapshot.json';manifest.write_text('{}\n')
    def binding(path):return {'path':str(path.resolve()),'bytes':path.stat().st_size,'sha256':p.sha(path)}
    source={**binding(external),'snapshot_manifest':binding(manifest)}
    internal=binding(private/'pilot3_private/secret-input.json')
    inventory=private/'pilot4_private/historical-inventory.json'
    put(inventory,{'complete_for_requested_known_protection_sources':True,'missing_sources':[],
                   'files':[source,internal], 'metadata_binding_documents':[binding(manifest)]})
    put(private/'pilot4_private/PREPARATION_PLAN_V1.json',{'historical_inventory':str(inventory.resolve())})
    return repository,private,external


def test_inventory_public_cache_exclusion_private_complete(temp):
    (temp/'file').write_text('kept')
    (temp/'__pycache__').mkdir();(temp/'__pycache__/module.pyc').write_bytes(b'cache')
    assert len(p.inventory(temp,True,p.Budget(),describe))==1
    assert len(p.inventory(temp,False,p.Budget(),describe))==2


def test_zero_byte_file_preserved(temp):
    (temp/'empty.log').write_bytes(b'')
    row=p.inventory(temp,False,p.Budget(),describe)[0]
    assert row['bytes']==0 and row['sha256']=='e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855'


@pytest.mark.parametrize('kind',['file','directory'])
def test_symlink_substitution_refused(temp,kind):
    target=temp/'target'
    target.mkdir() if kind=='directory' else target.write_text('data')
    (temp/'alias').symlink_to(target,target_is_directory=kind=='directory')
    with pytest.raises(ValueError,match='symlink'):p.inventory(temp,False,p.Budget(),describe)


@pytest.mark.parametrize('budget',[p.Budget(max_bytes=2),p.Budget(max_files=0)])
def test_budget_fails_before_file_read(temp,budget):
    (temp/'data').write_bytes(b'abc');called=[]
    def unexpected(*args):called.append(True);raise AssertionError('must not read')
    with pytest.raises(ValueError,match='budget'):p.inventory(temp,False,budget,unexpected)
    assert not called


def test_changed_during_read_is_refused(temp):
    (temp/'data').write_bytes(b'old')
    def changing(path,root):
        result=describe(path,root);path.write_bytes(b'changed');return result
    with pytest.raises(ValueError,match='changed_during'):p.inventory(temp,False,p.Budget(),changing)


def test_added_file_during_snapshot_refused(temp):
    (temp/'data').write_text('original')
    def adding(path,root):
        result=describe(path,root);(root/'new').write_text('added');return result
    with pytest.raises(ValueError,match='membership'):p.inventory(temp,False,p.Budget(),adding)


def test_compare_tracks_changed_missing_and_added_without_imputation():
    old=[{'path':'a','bytes':1,'sha256':'old'},{'path':'b','bytes':0,'sha256':'empty'}]
    new=[{'path':'a','bytes':1,'sha256':'new'},{'path':'c','bytes':0,'sha256':'empty'}]
    assert p.compare_rows(old,new)=={'missing':['b'],'added':['c'],'changed':['a']}
    with pytest.raises(ValueError,match='duplicate'):p.compare_rows(old,old+old)


def test_historical_original_bindings_deduplicate_roots_and_snapshots(temp):
    repository,private,external=fixture(temp)
    roots={key:(private/(key+'_private')).resolve() for key in p.STUDIES}
    value=p.protected_source_bindings(private,roots,p.Budget(),describe)
    assert value['declared_historical_source_files']==2
    assert len(value['external_files'])==2 and len(value['already_covered_by_private_trees'])==1
    assert sorted(map(len,[r['categories'] for r in value['external_files']]))==[1,2]


def test_historical_expected_source_hash_refuses_changed_input(temp):
    repository,private,external=fixture(temp);external.write_text('changed')
    roots={key:(private/(key+'_private')).resolve() for key in p.STUDIES}
    with pytest.raises(ValueError,match='source_hash_mismatch'):
        p.protected_source_bindings(private,roots,p.Budget(),describe)


def test_public_projection_never_exports_private_file_names():
    result=p.public_projection({'pilot5':{'relative_root':'studies/pilot5_shared_anchor','files':[]}},
        {'pilot5':{'root':'/secret/root','files':[{'path':'secret-identity-map.json','bytes':19,'sha256':'abc'}]}},
        {'declared_historical_source_files':1,'external_files':[{'path':'/secret/source','bytes':7}],
         'already_covered_by_private_trees':[]}, 'private-hash', {'checks':{'fixed':True}})
    text=json.dumps(result)
    assert 'secret' not in text and 'identity-map' not in text
    assert result['private_tree_aggregates']['pilot5']=={'files':1,'bytes':19}


def mock_runtime(monkeypatch,repository):
    monkeypatch.setattr(p,'ROOT',repository)
    monkeypatch.setattr(p,'prior_helpers',lambda:(SimpleNamespace(describe=describe),SimpleNamespace(sha=p.sha),None))
    monkeypatch.setattr(p,'fresh_engine',lambda probe:({'checks':{'synthetic':True}}, {'private_probe':True},{'private_probe':True}))
    monkeypatch.setattr(p.resource,'setrlimit',lambda *args:None)
    monkeypatch.setattr(p.signal,'alarm',lambda *args:None)
    monkeypatch.setenv('AHAS_NETWORK_ISOLATION','linux_seccomp_socket_denial')


def test_freeze_and_final_recheck_integration_with_private_only_difference_paths(temp,monkeypatch):
    repository,private,_=fixture(temp);mock_runtime(monkeypatch,repository)
    baseline=temp/'baseline.json';private_baseline=temp/'freeze/private-manifest.json'
    assert p.execute('freeze',private,temp/'freeze',baseline)==0
    assert p.execute('verify',private,temp/'verify01',temp/'verify01.json',baseline,private_baseline)==0
    (private/'pilot5_private/secret-input.json').write_text('altered original\n')
    assert p.execute('verify',private,temp/'verify02',temp/'verify02.json',baseline,private_baseline)==1
    report=p.read(temp/'verify02.json')
    assert report['difference_counts']=={'private_pilot5':{'missing':0,'added':0,'changed':1}}
    assert 'secret-input' not in json.dumps(report)
    assert p.read(temp/'verify02/differences.json')['private_pilot5']['changed']==['secret-input.json']


def test_initial_baseline_cannot_be_overwritten(temp,monkeypatch):
    repository,private,_=fixture(temp);mock_runtime(monkeypatch,repository)
    baseline=temp/'baseline.json';p.execute('freeze',private,temp/'freeze',baseline)
    with pytest.raises(FileExistsError):p.execute('freeze',private,temp/'freeze',baseline)
