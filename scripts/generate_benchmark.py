#!/usr/bin/env python3
"""Build a fixed 1,000-record workload from the shipped synthetic-text constructor.

No truth labels are created or consulted. This tests engineering cost on formulaic
text; it is not a representative account sample or an accuracy benchmark.
"""
from datetime import timedelta
import argparse
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,default=ROOT/'benchmarks'/'input')
    args = parser.parse_args()
    spec = importlib.util.spec_from_file_location('fixture_constructor',ROOT/'fixtures/generate_fixtures.py')
    constructor = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(constructor)
    rows = [constructor.record('performance_workload',i+1,
            constructor.synthetic_text(i, garden=False, formal=False),i*300) for i in range(1000)]
    manifest = {
        'schema_version':'1.0.0','snapshot_id':'performance_workload_v1','account_id':'performance_workload',
        'source_category':'synthetic','capture_utc':'2025-03-01T00:00:00Z','text_format':'markdown',
        'default_language':'en','source_notes':'Fixed 1000-record workload from the shipped synthetic_text constructor; no real person.',
        'coverage':{'status':'complete_for_declared_scope','start_utc':rows[0]['created_utc'],
                    'end_utc':rows[-1]['created_utc'],'known_gaps':[], 'notes':'Complete for this constructed workload only.'}}
    args.out.mkdir(parents=True,exist_ok=True)
    (args.out/'records.jsonl').write_text(''.join(constructor.dumps(row)+'\n' for row in rows),encoding='utf-8')
    constructor.save_json(args.out/'snapshot.json',manifest)


if __name__=='__main__':
    main()
