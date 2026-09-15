"""Fresh terminal identity check; reads no corpus and executes no analyzer."""
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root/'scripts'))
from run_full_chronology import sha, write, baseline_identity

prior = json.loads((root/'environment/installed-package-fresh.json').read_bytes())
package = Path(prior['package_file']).parent
current = {p.relative_to(package).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
           for p in package.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix != '.pyc'}
assert current == prior['package_files_sha256'], 'Installed package bytes changed'
identity = baseline_identity({'PYTHONPATH': '/tmp/ahas-pilot3-installed', 'PYTHONDONTWRITEBYTECODE': '1'})
report = {'status': 'passed', 'finished_utc': datetime.now(timezone.utc).isoformat(),
          'installed_files_byte_identical': len(current), 'actual_fresh_identity': identity,
          'initial_probe_sha256': sha(root/'environment/installed-package-fresh.json'),
          'checker_sha256': sha(__file__), 'corpus_records_read': 0,
          'preprocessor_calls': 0, 'real_chronological_analyzer_calls': 0}
write(root/'environment/terminal-identity-verification.json', report)
print(json.dumps({'status': 'passed', 'unchanged_installed_files': len(current),
                  'implementation_fingerprint': identity['implementation_fingerprint'],
                  'config_sha256': identity['config_sha256']}))
