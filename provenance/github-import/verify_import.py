from pathlib import Path
import hashlib,json,zipfile,sys,re
work=Path(__file__).resolve().parent
stage=work/'account-history-analyzer'
assembly=json.loads((work/'assembly-receipt.json').read_text())
exceptions={'README.md','.gitignore'}
for name,expected in assembly['copied_release_files'].items():
 if name not in exceptions: assert hashlib.sha256((stage/name).read_bytes()).hexdigest()==expected,name
pilot=work.parent/'ahas-pilot2-20260914/deliverables/AHAS_1.0.4_RW001_and_Pilot2_Review_20260914.zip'
with zipfile.ZipFile(pilot) as archive:
 for name in archive.namelist(): assert (stage/'studies/pilot2'/name).read_bytes()==archive.read(name),name
 assert len(archive.namelist())==317
sys.path.insert(0,str(stage/'src'))
import account_history_analyzer
from account_history_analyzer.pipeline import implementation_identity
from account_history_analyzer.config import AnalysisConfig
from account_history_analyzer.io import digest
fp,env,resources=implementation_identity()
assert Path(account_history_analyzer.__file__).is_relative_to(stage)
assert account_history_analyzer.__version__=='1.0.4'
assert fp=='bfc989028bf2b47c506d1ba501287d4e362aadc25ca5c731c41e4b27a336e179'
assert digest(AnalysisConfig.from_toml().analytical())=='8fd0239fe2f87c9f1506786ac36099fe996e00cc6e021b3ecc67fbb65cd2d925'
patterns=[rb'gh[pousr]_[A-Za-z0-9]{30,}',rb'github_pat_[A-Za-z0-9_]{30,}',rb'AKIA[0-9A-Z]{16}',rb'-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----']
paths=[]
for p in stage.rglob('*'):
 if not p.is_file() or '.git' in p.parts or '__pycache__' in p.parts:continue
 assert not p.is_symlink()
 assert p.stat().st_size<50*1024*1024
 content=p.read_bytes()
 for pattern in patterns: assert not re.search(pattern,content),'Credential-like material in '+str(p.relative_to(stage))
 paths.append(p)
result={'status':'passed','source_version':account_history_analyzer.__version__,'implementation_fingerprint':fp,'analysis_config_sha256':digest(AnalysisConfig.from_toml().analytical()),'reference_environment':env,'resource_sha256':resources,'frozen_release_files_compared':len(assembly['copied_release_files'])-len(exceptions),'preserved_pilot_handoff_files':317,'file_count_at_check':len(paths),'bytes_at_check':sum(p.stat().st_size for p in paths),'credential_pattern_matches':0,'scope':'Byte-preserving source/documentation import plus navigation only; no scientific recomputation or new regression-suite claim.'}
(work/'import-verification.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result))
