"""Hash Pilot4 artifacts and the source inputs reused by Pilot5, without edits."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
PRIOR=ROOT/'studies/pilot4_chronological_controls'
PRIVATE=Path('/home/jaykob/.codex/visualizations/2026/09/14/01a0a1b3-d799-70b2-9746-932405f84cdf/pilot4_private')


def sha(path):
    with path.open('rb') as handle:return hashlib.file_digest(handle,'sha256').hexdigest()


def describe(path,base):
    if path.is_symlink() or not path.is_file():raise ValueError('invalid_prior_artifact_path')
    return {'path':path.relative_to(base).as_posix(),'bytes':path.stat().st_size,'sha256':sha(path)}


def main():
    started=datetime.now(timezone.utc).isoformat()
    prior=[describe(p,PRIOR) for p in sorted(PRIOR.rglob('*'))
           if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc']
    names=['PREPARATION_PLAN_V1.json','candidate-allocation-01.json','exposure-flags.json',
           'candidates-01/candidate-pool.jsonl','candidates-01/selection.json',
           'candidates-01/preparation.json','candidates-01/original-source-lines.jsonl',
           'candidates-01/original-source-index.json','audit-01/audit.json',
           'history-01/historical-audit-source-inventory.json']
    private=[describe(PRIVATE/name,PRIVATE) for name in names]
    value={'status':'frozen_before_pilot5_source_selection','started_utc':started,
           'finished_utc':datetime.now(timezone.utc).isoformat(),'checker_sha256':sha(Path(__file__)),
           'prior_public_artifacts':prior,'prior_public_artifact_count':len(prior),
           'prior_reused_private_artifacts':private,
           'prior_public_relative_root':'studies/pilot4_chronological_controls',
           'private_root_logical_name':'pilot4_private','prior_artifacts_modified':False,
           'private_source_content_displayed':False,'preprocessor_calls':0,
           'real_chronological_analyzer_calls':0,
           'scope':'Hash-only preservation baseline. Private list covers named source inputs, not every private Pilot4 artifact.'}
    with (HERE/'pilot4-preservation-baseline.json').open('x') as handle:
        json.dump(value,handle,sort_keys=True,indent=2);handle.write('\n')
    print(json.dumps({'status':value['status'],'prior_public_artifact_count':len(prior),
                      'prior_private_source_bindings':len(private),'real_chronological_analyzer_calls':0}))


if __name__=='__main__':main()
