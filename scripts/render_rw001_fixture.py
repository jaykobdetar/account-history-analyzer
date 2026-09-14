"""Generate public RW-001 presentation fixtures; this is a QA utility, not AHAS.

Run with the pinned development environment through scripts/offline_exec.py.
The public test helper generates source prose before reading the case sidecar.
Constructed sensitivity outcomes are explicitly not numerical validation data.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path

from account_history_analyzer.charts import render_charts
from account_history_analyzer.config import AnalysisConfig
from account_history_analyzer.io import canonical_bytes
from account_history_analyzer.registry import registry_document
from account_history_analyzer.reporting import render_html, render_markdown

ROOT = Path(__file__).resolve().parents[1]
NOTICE = ('RW-001 PUBLIC PRESENTATION FIXTURE: sensitivity outcomes were manually '
          'constructed after processing artificial source records. These are renderer '
          'regression cases, not optimizer output, numerical validation, or authorship truth.')


def main() -> None:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,required=True,help='New output directory; existing paths are refused.')
    args=parser.parse_args()
    if args.out.exists(): parser.error('Output directory already exists; choose a new destination.')
    args.out.mkdir(parents=True)
    spec=importlib.util.spec_from_file_location('rw001_public_fixture',ROOT/'tests/test_sensitivity_overview.py')
    assert spec and spec.loader
    helper=importlib.util.module_from_spec(spec);spec.loader.exec_module(helper)
    original=helper.build_exported_report(args.out/'source')
    hashes={}
    for case in ('alternative_only','matched_plus_extra'):
        results,evidence,windows=helper.constructed(original,case)
        # The notice is also visible inside the real report header, including
        # after a saved-JSON re-render; it is not an untracked HTML wrapper.
        results['snapshot']['snapshot_id']=NOTICE+' Case: '+case
        directory=args.out/case;directory.mkdir()
        files={'results.json':canonical_bytes(results),
               'evidence.jsonl':b''.join(canonical_bytes(row) for row in evidence),
               'windows.jsonl':b''.join(canonical_bytes(row) for row in windows),
               'resolved_config.json':canonical_bytes(AnalysisConfig.from_mapping().analytical()),
               'method_registry.json':canonical_bytes(registry_document()),
               **render_charts(results,windows)}
        for mode in ('included','none'):
            suffix='' if mode=='included' else '.no-excerpts'
            files['report'+suffix+'.md']=render_markdown(results,evidence,windows=windows,excerpts=mode).encode()
            files['report'+suffix+'.html']=render_html(results,evidence,windows=windows,excerpts=mode).encode()
        for name,data in files.items():
            (directory/name).write_bytes(data)
            hashes[case+'/'+name]=hashlib.sha256(data).hexdigest()
    (args.out/'README.md').write_text('# RW-001 public presentation fixtures\n\n'+NOTICE+'\n\n'
        'Source inputs contain only newly generated synthetic records. Case labels are read '
        'after source processing and never enter feature calculations. The candidate/status '
        'facts deliberately replace selected exported sensitivity observations. Therefore '
        'these documents exercise presentation and JSON reload behavior; they must not be '
        'submitted as numerical-oracle or production recomputation evidence. Actual full '
        'analysis/recompute checks are recorded separately.\n',encoding='utf-8')
    (args.out/'presentation-sha256.json').write_bytes(canonical_bytes(hashes))
    print(json.dumps({'status':'generated','cases':2,'presentation_files':len(hashes),'out':str(args.out),
                      'scope':'synthetic_renderer_regression_only'}))


if __name__=='__main__':main()
