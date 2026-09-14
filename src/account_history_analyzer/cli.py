"""CLI boundaries, stable exit codes, and clean machine-readable standard output."""
from __future__ import annotations
import argparse
from pathlib import Path
import sys

from .config import AnalysisConfig
from .errors import AHASError, InputError
from .io import canonical_bytes, canonical_digest, load_json, load_snapshot, parse_json, sha256_bytes


def _input_options(parser: argparse.ArgumentParser, *, output: bool = False) -> None:
    parser.add_argument('--input', required=True)
    parser.add_argument('--manifest', required=True)
    parser.add_argument('--config')
    if output:
        parser.add_argument('--out', required=True)
        parser.add_argument('--overwrite', action='store_true')
        parser.add_argument('--allow-toy-reference', action='store_true')


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog='ahas', description='Offline descriptive account-history measurements')
    sub = parser.add_subparsers(dest='command', required=True)
    _input_options(sub.add_parser('validate'))
    _input_options(sub.add_parser('analyze'), output=True)
    compare = sub.add_parser('compare', help='Compare explicit supplied local slices')
    _input_options(compare, output=True)
    compare.add_argument('--selection', required=True)
    render = sub.add_parser('render', help='Render verified stored measurements without analysis')
    render.add_argument('--results', required=True)
    render.add_argument('--artifacts', required=True)
    render.add_argument('--format', choices=['html','markdown','both'], default='html')
    render.add_argument('--excerpts', choices=['included','none'], default='included')
    render.add_argument('--out', required=True)
    render.add_argument('--overwrite', action='store_true')
    verify_parser = sub.add_parser('verify')
    _input_options(verify_parser)
    verify_parser.add_argument('--analysis-dir', required=True)
    verify_parser.add_argument('--recompute', action='store_true', help='Regenerate and compare all canonical artifacts, including reports and charts; exclude operational receipts')
    evaluate = sub.add_parser('evaluate', help='Evaluate explicit local synthetic or labeled data')
    evaluate.add_argument('--suite', required=True, choices=['synthetic','paired_text','account_stream'])
    evaluate.add_argument('--fixtures')
    evaluate.add_argument('--dataset')
    evaluate.add_argument('--config')
    evaluate.add_argument('--allow-toy-reference', action='store_true')
    evaluate.add_argument('--out', required=True)
    evaluate.add_argument('--overwrite', action='store_true')
    args = parser.parse_args(argv)
    try:
        if args.command == 'evaluate':
            from .evaluation_reporting import write_evaluation
            import time
            started = time.perf_counter()
            config = AnalysisConfig.from_toml(args.config, allow_toy_reference=args.allow_toy_reference)
            if config.reference and config.reference['reference_kind']=='toy' and not args.allow_toy_reference:
                raise InputError('Toy reference requires --allow-toy-reference', code='toy_reference_forbidden')
            if args.suite == 'synthetic':
                if not args.fixtures or args.dataset:
                    raise InputError('Synthetic evaluation requires --fixtures and no --dataset', code='invalid_evaluation_arguments')
                from .evaluation_synthetic import evaluate_synthetic
                evaluation = evaluate_synthetic(args.fixtures, config)
            else:
                if not args.dataset or args.fixtures:
                    raise InputError('External evaluation requires --dataset and no --fixtures', code='invalid_evaluation_arguments')
                from .evaluation_external import evaluate_external
                evaluation = evaluate_external(args.dataset, args.suite, config)
            write_evaluation(evaluation, args.out, runtime_seconds=time.perf_counter()-started, overwrite=args.overwrite)
            summary = {'status':evaluation['status'], 'evaluation_sha256':sha256_bytes(canonical_bytes(evaluation))}
            sys.stdout.buffer.write(canonical_bytes(summary))
            return evaluation.get('exit_code', 3 if evaluation['status']=='failed' else 0)
        elif args.command == 'verify':
            from .verification import verify
            summary = verify(args.input, args.manifest, args.analysis_dir, recompute=args.recompute, config_path=args.config)
        elif args.command == 'render':
            from .artifacts import publish_files, safe_artifact, inspect_artifacts
            from .artifact_io import iter_artifact_jsonl, read_artifact_bytes
            from .reporting import render_markdown, render_html
            from .charts import render_charts
            root = Path(args.artifacts)
            _, result, _, limits = inspect_artifacts(root)
            stored = safe_artifact(root, 'results.json')
            if Path(args.results).resolve() != stored.resolve():
                raise InputError('--results must be the verified results.json in --artifacts', code='results_artifact_mismatch')
            evidence = list(iter_artifact_jsonl(safe_artifact(root, 'evidence.jsonl'), max_bytes=limits.max_file_bytes))
            windows = list(iter_artifact_jsonl(safe_artifact(root, 'windows.jsonl'), max_bytes=limits.max_file_bytes))
            rendered = dict(render_charts(result, windows))
            for name in ('resolved_config.json', 'method_registry.json'):
                rendered[name] = read_artifact_bytes(safe_artifact(root, name), max_bytes=limits.max_file_bytes)
            if args.format in {'html','both'}:
                rendered['report.html'] = render_html(result, evidence, excerpts=args.excerpts, windows=windows).encode('utf-8')
            if args.format in {'markdown','both'}:
                rendered['report.md'] = render_markdown(result, evidence, excerpts=args.excerpts, windows=windows).encode('utf-8')
            publish_files(rendered, args.out, overwrite=args.overwrite, limits=limits)
            summary = {'status': 'rendered', 'excerpts': args.excerpts, 'analytical_results_unchanged': True}
        else:
            config = AnalysisConfig.from_toml(args.config, allow_toy_reference=getattr(args, 'allow_toy_reference', False))
            if config.reference and config.reference['reference_kind']=='toy' and not getattr(args,'allow_toy_reference',False):
                raise InputError('Toy reference requires --allow-toy-reference', code='toy_reference_forbidden')
            snapshot = load_snapshot(args.input, args.manifest, config)
            if args.command in {'analyze','compare'}:
                from .pipeline import analyze
                from .artifacts import write_artifacts
                selection = load_json(args.selection) if args.command == 'compare' else None
                result = analyze(snapshot, config, selection=selection)
                write_artifacts(result, args.out, overwrite=args.overwrite)
                summary = {'status': 'partial' if result.exit_code else 'complete',
                           'results_sha256': canonical_digest(result.results)}
                sys.stdout.buffer.write(canonical_bytes(summary))
                return result.exit_code
            summary = {'status': 'valid', 'unique_records': len(snapshot.records),
                       'canonical_sha256': snapshot.canonical_sha256, 'warnings': snapshot.warnings}
        sys.stdout.buffer.write(canonical_bytes(summary))
        return 0
    except AHASError as exc:
        print(str(exc), file=sys.stderr)
        return exc.exit_code
    except Exception as exc:
        print(f'computation_failure: {type(exc).__name__}: {exc}', file=sys.stderr)
        return 3
