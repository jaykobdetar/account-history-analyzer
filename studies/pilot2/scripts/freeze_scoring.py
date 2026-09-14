#!/usr/bin/env python3
"""Close the tested preparation gate before any new performance observation."""
import datetime,hashlib,json,os
from pathlib import Path
from account_history_analyzer.config import AnalysisConfig
from account_history_analyzer.io import digest
from account_history_analyzer.pipeline import implementation_identity

ROOT=Path(__file__).resolve().parents[1]

def sha(path):
    with path.open('rb') as source:return hashlib.file_digest(source,'sha256').hexdigest()
def read(path):return json.loads(path.read_bytes())

def main():
    assert os.environ.get('AHAS_NETWORK_ISOLATION')=='linux_seccomp_socket_denial'
    target=ROOT/'protocol/scoring-freeze.json'
    assert not target.exists()
    assert not (ROOT/'outputs/paired').exists() and not (ROOT/'outputs/streams').exists()
    registered=read(ROOT/'protocol/registration.json');plan=read(ROOT/'protocol/plan.json')
    for path,expected in registered['files'].items():assert sha(ROOT/path)==expected,path
    for relative in ('operational-addendum-001-registration.json','implementation-clarifications-registration.json'):
        entry=read(ROOT/'protocol'/relative)
        assert sha(ROOT/'protocol'/entry.get('file',entry.get('addendum')))==entry['sha256']
    fingerprint,reference,resources=implementation_identity()
    baseline=read(ROOT/'protocol/measurement-baseline.json')
    assert fingerprint==plan['implementation_fingerprint']==baseline['implementation_fingerprint']
    assert digest(AnalysisConfig.from_toml().analytical())==plan['analysis_config_sha256']==baseline['configuration_sha256']
    assert reference==baseline['reference_environment'] and dict(resources)==baseline['resources']
    paired=ROOT/'prepared/paired-registered'
    assert sha(paired/'private/candidate-pool.jsonl')==sha(ROOT/'prepared/paired/private/candidate-pool.jsonl')
    audit=read(ROOT/'prepared/paired/private/leakage-audit.json')
    assert audit['status']=='audited' and audit['candidate_pool_sha256']==sha(paired/'private/candidate-pool.jsonl')
    assert read(ROOT/'inventory/paired-prepared-check.json')['status']=='passed'
    assert read(ROOT/'review/paired-leakage-independent-check.json')['status']=='passed'
    joint=read(ROOT/'review/audit-cap-and-joint-bridges.json')
    assert joint['status']=='passed' and joint['joint_components_exposing_new_paired_cross_split_relationships']==0
    assert joint['joint_paired_cross_split_purge_same_as_initial']
    streams=ROOT/'prepared/streams'
    stream_plan=read(streams/'stream-plan.json');groups=read(streams/'group-audit.json')
    assert stream_plan['scoring_executed'] is False
    assert groups['confirmation_protection_status']=='observed_related_groups_audited'
    assert len(stream_plan['cases'])==51 and len(stream_plan['operational_availability_views'])==9
    assert read(ROOT/'logs/study-tests-combined.receipt.json')['exit_code']==0
    assert '68 passed' in (ROOT/'logs/study-tests-combined.stdout.log').read_text()
    assert read(ROOT/'logs/chronological-prepared-artifact-tests.receipt.json')['exit_code']==0
    files={}
    for directory in ['protocol','scripts','tests','prepared/paired','prepared/paired-registered','prepared/streams']:
        for path in sorted((ROOT/directory).rglob('*')):
            if path.is_file() and '__pycache__' not in path.parts and '.pytest_cache' not in path.parts:
                assert not path.is_symlink()
                files[str(path.relative_to(ROOT))]=sha(path)
    for path in sorted((ROOT/'review').glob('*.json')):
        files[str(path.relative_to(ROOT))]=sha(path)
    for name in ('paired-prepared-check.json','paired-preflight.json','paired-registered-replay.json','candidate-fidelity.json'):
        path=ROOT/'inventory'/name;files[str(path.relative_to(ROOT))]=sha(path)
    result={'status':'frozen','scoring_authorized':True,'frozen_utc':datetime.datetime.now(datetime.UTC).isoformat(),
        'protocol_id':plan['protocol_id'],'protocol_plan_sha256':sha(ROOT/'protocol/plan.json'),
        'protocol_registration_sha256':sha(ROOT/'protocol/registration.json'),
        'paired_prepared_directory':'prepared/paired-registered','stream_plan_sha256':sha(streams/'stream-plan.json'),
        'stream_group_audit_sha256':sha(streams/'group-audit.json'),
        'implementation_fingerprint':fingerprint,'analysis_config_sha256':plan['analysis_config_sha256'],
        'reference_environment':reference,'new_performance_scores_computed_before_this_gate':False,
        'confirmation_distance_computation_authorized':False,'files':dict(sorted(files.items())),
        'real_world_validation':'not_established','ground_truth_scope':'source-account ID proxies and construction facts; no verified natural-person authorship',
        'chronological_status':'exploratory; four source pairs formed, two Cornell slots unfilled',
        'historical_failures_preserved':True}
    with target.open('x') as handle:json.dump(result,handle,indent=2);handle.write('\n')
    print(json.dumps({key:result[key] for key in ('status','scoring_authorized','frozen_utc','implementation_fingerprint','paired_prepared_directory')}))
    print(json.dumps({'frozen_file_count':len(files),'scoring_freeze_sha256':sha(target)}))

if __name__=='__main__':main()
