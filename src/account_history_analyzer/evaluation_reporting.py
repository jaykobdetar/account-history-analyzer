"""Deterministic evaluator summaries, kept separate from production measurements."""
from __future__ import annotations
from pathlib import Path
from typing import Any, Mapping
import os
import platform
import resource

from .artifacts import publish_files
from .io import canonical_bytes, sha256_bytes
from .reporting import json_text, md_text


def render_evaluation(evaluation: Mapping[str, Any]) -> str:
    """Render facts with sorted mapping keys and unchanged ordered arrays."""
    lines = ['# Local evaluation of account-history measurements', '',
             f"Suite: **{md_text(evaluation.get('suite', evaluation.get('format', 'unknown')))}**. Status: **{md_text(evaluation['status'])}**.", '',
             'Engineering checks and constructed signals do not establish real-world authorship, automation or AI-detection accuracy.',
             'No confidence intervals are inferred from correlated observations. All source data and labels are supplied locally.', '',
             'The complete observations, denominators, hashes, protocols and missingness reasons are in evaluation.json.', '']
    if evaluation.get('suite') == 'synthetic':
        lines += ['Real-world validation: **not_established**. External data: **not_evaluated**.',
                  'Truth sidecars describe construction operations only; the analyzer does not consume them.', '',
                  f"Indexed cases: {len(evaluation['fixtures'])}. Shipped-scenario coverage complete: {str(evaluation['dataset']['shipped_scenarios_complete']).lower()}. Missing scenarios: {md_text(', '.join(evaluation['dataset']['missing_shipped_scenarios']) or 'none')}.",
                  f"Check outcomes: {md_text(json_text(evaluation['check_counts']))}. A not-evaluated check is not a pass.", '',
                  '| Constructed case | Check outcomes | Analysis exit code |', '| --- | --- | --- |']
        for case in evaluation.get('fixtures', []):
            counts = {status:sum(c['status']==status for c in case['checks']) for status in ('passed','failed','not_evaluated')}
            lines.append(f"| {md_text(case['case'])} | {md_text(json_text(counts))} | {case['analysis_exit_code']} |")
        lines += ['', '| Numerical check | Outcome | Expected | Observed |', '| --- | --- | --- | --- |']
        for check in evaluation.get('numerical_checks', []):
            lines.append('| '+' | '.join(md_text(check.get(key)) for key in ('check_id','status','expected','observed'))+' |')
        for case in evaluation.get('fixtures', []):
            if case.get('construction_boundary') is not None:
                lines += ['', f"Construction boundary observations for {md_text(case['case'])}: {md_text(json_text(case['construction_boundary']))}."]
    else:
        lines += ['Reported metrics describe only the supplied evaluation protocol and labels. They are not an authorship probability for an analyzed account.', '',
                  '## Supplied-data evaluation details', '']
        details = {key:value for key,value in evaluation.items() if key not in {'dataset','identities'}}
        # Backticks and HTML characters are escaped even inside fenced JSON so
        # hostile provenance cannot terminate the fence or introduce markup.
        encoded = json_text(details, indent=2)
        for char in ('`','<','>','&'):
            encoded = encoded.replace(char, '\\u'+format(ord(char),'04x'))
        lines += ['```json',encoded,'```']
    return '\n'.join(lines).rstrip()+'\n'


def write_evaluation(evaluation: Mapping[str, Any], directory: str | Path, *,
                     runtime_seconds: float, overwrite: bool = False) -> None:
    """Atomically publish complete evaluator outputs with separate actual receipts."""
    artifacts = {'evaluation.json':canonical_bytes(evaluation),
                 'report.md':render_evaluation(evaluation).encode('utf-8')}
    artifacts['checksums.json'] = canonical_bytes({name:sha256_bytes(data) for name,data in sorted(artifacts.items())})
    artifacts['run_receipt.json'] = canonical_bytes({'runtime_seconds':runtime_seconds,
        'peak_process_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        'python':platform.python_version(),'platform':platform.platform(),
        'network_isolation':os.environ.get('AHAS_NETWORK_ISOLATION','not_asserted')})
    publish_files(artifacts,directory,overwrite=overwrite)
