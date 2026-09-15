"""Fresh final preservation check; no source editing or analyzer execution."""
from datetime import datetime,timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
PRIVATE=Path('/home/jaykob/.codex/visualizations/2026/09/14/01a0a1b3-d799-70b2-9746-932405f84cdf/pilot4_private')
PROBE_SHA='40d2aeb1ace80a79a7f8beab2daa5965ab5e8a037139df6a4ab88a3a1f1742d1'


def sha(path):
    with path.open('rb') as handle:return hashlib.file_digest(handle,'sha256').hexdigest()


def save(name,data):
    with (HERE/name).open('x') as handle:json.dump(data,handle,sort_keys=True,indent=2);handle.write('\n')


def main():
    os.environ['PYTHONDONTWRITEBYTECODE']='1';sys.dont_write_bytecode=True
    manifest=HERE/'pilot4-preservation-baseline.json';initial=HERE/'installed-package-fresh.json'
    helper=ROOT/'studies/pilot3_cross_context/environment/verify_environment.py'
    require= lambda ok,code:None if ok else (_ for _ in ()).throw(ValueError(code))
    require(sha(helper)==PROBE_SHA,'frozen_environment_probe_changed')
    start={'started_utc':datetime.now(timezone.utc).isoformat(),'checker_sha256':sha(Path(__file__)),
           'preservation_baseline_sha256':sha(manifest),'initial_installed_probe_sha256':sha(initial),
           'environment_probe_sha256':sha(helper),'analyzer_calls':0}
    save('final-preservation-start-binding.json',start)
    baseline=json.loads(manifest.read_bytes());previous=json.loads(initial.read_bytes());changed=[]
    for category,base,rows in [('pilot4_public',ROOT/'studies/pilot4_chronological_controls',baseline['prior_public_artifacts']),
                             ('pilot4_private',PRIVATE,baseline['prior_reused_private_artifacts'])]:
        for row in rows:
            p=base/row['path']
            if not p.is_file() or p.stat().st_size!=row['bytes'] or sha(p)!=row['sha256']:
                changed.append({'category':category,'path':row['path']})
    spec=importlib.util.spec_from_file_location('frozen_environment_probe',helper)
    probe=importlib.util.module_from_spec(spec);spec.loader.exec_module(probe)
    current=probe.probe(Path('/tmp/ahas-pilot3-installed'))
    fields=('package_files_sha256','module_version','distribution_version','package_file','distribution_path',
            'direct_url','implementation_fingerprint','config_sha256','expanded_default_config','resource_hashes',
            'dependency_versions','reference_environment','python','python_executable')
    identity_checks={key:current[key]==previous[key] for key in fields}
    report={'status':'passed' if not changed and all(identity_checks.values()) else 'failed',
        'finished_utc':datetime.now(timezone.utc).isoformat(),'checker_sha256':start['checker_sha256'],
        'pilot4_public_files_checked':len(baseline['prior_public_artifacts']),
        'pilot4_private_inputs_checked':len(baseline['prior_reused_private_artifacts']),
        'installed_files_checked':len(current['package_files_sha256']),'changed_prior_artifacts':changed,
        'fresh_installed_identity_checks':identity_checks,'implementation_fingerprint':current['implementation_fingerprint'],
        'analysis_config_sha256':current['config_sha256'],'preservation_baseline_sha256':start['preservation_baseline_sha256'],
        'initial_installed_probe_sha256':start['initial_installed_probe_sha256'],
        'source_content_displayed':False,'production_files_modified':False,'analyzer_calls':0,'preprocessor_calls':0,
        'scope':'All301 initial Pilot4 public files,10 named reused private inputs and54 installed files; newly appended files are not claimed as members of the old baseline.'}
    save('final-installed-package-fresh.json',current)
    report['fresh_installed_probe_sha256']=sha(HERE/'final-installed-package-fresh.json')
    save('final-preservation-verification.json',report)
    print(json.dumps(report,sort_keys=True))
    raise SystemExit(0 if report['status']=='passed' else 1)


if __name__=='__main__':main()
