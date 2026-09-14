"""Exercise actual publication on a saved result; DOES NOT recompute analysis."""
from pathlib import Path
import json,sys,hashlib,time,platform,resource
from account_history_analyzer.artifact_io import load_artifact_json,file_digest
from account_history_analyzer.artifacts import AnalysisResult,write_artifacts,verify_artifacts
from account_history_analyzer.io import freeze
src=Path(sys.argv[1]);out=Path(sys.argv[2]);receipt=Path(sys.argv[3]);started=time.perf_counter()
results=load_artifact_json(src/'results.json')
files={name:(src/meta['relative_path']).read_bytes() for name,meta in results['artifacts'].items()}
result=AnalysisResult(freeze(results),freeze(files),{'review_scope':'republishing supplied values, not fresh ingestion'},{'review_scope':'republishing supplied values, not new numerical analysis','python':platform.python_version()})
del results,files
write_artifacts(result,out)
del result
checks=json.loads((src/'checksums.json').read_bytes()); names=[*checks,'checksums.json']
equal={name:file_digest(out/name)==file_digest(src/name) for name in names}
summary=verify_artifacts(out)
receipt.write_text(json.dumps({'scope':'Republish saved analytical values through actual write_artifacts, then compare and verify. No numerical recomputation.','canonical_matches':equal,'integrity':summary,'wall_seconds':time.perf_counter()-started,'peak_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss},indent=2)+'\n')
print(receipt.read_text(),flush=True)
