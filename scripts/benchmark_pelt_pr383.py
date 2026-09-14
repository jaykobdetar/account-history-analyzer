"""Bounded, offline comparison of released AHAS PELT and the PR #383 wrapper.

The original implementation and an already-standardized real fixture matrix
come directly from the hash-pinned 1.0.0 release archive. No fixture records,
metadata, truth labels, or source IDs are passed through feature calculations.
Numerical comparisons/inputs are separate from nondeterministic timing receipts.

Example (run after other tests/benchmarks finish):
  .venv/bin/python scripts/offline_exec.py .venv/bin/python \
    scripts/benchmark_pelt_pr383.py --out qa/pr383/benchmark

--describe reads and validates inputs/provenance without running an optimizer.
Existing output files are refused; use a fresh directory for additional runs.
"""
from __future__ import annotations

import argparse
import gc
import hashlib
import inspect
import json
import math
from pathlib import Path
import platform
import resource
import statistics
import subprocess
import sys
import tarfile
import tempfile
import time
import tracemalloc
import types
import os
from importlib import metadata

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / "release/account-history-analyzer-1.0.0-source-and-reports.tar.gz"
ARCHIVE_SHA256 = "4cc1b959445d3dc1a12a75c80bf2505bab017883f737ddb9a986f6d1e6335325"
PREFIX = "account_history_analyzer_v1/"
OLD_MEMBER = PREFIX + "src/account_history_analyzer/changepoints.py"
FIXTURE_MEMBER = PREFIX + "output/constructed_style_shift/results.json"
VARIANTS = ("released_ahas_1_0_0", "ruptures_pr383_wrapper")
ABSOLUTE_TOLERANCE = 1e-9
RELATIVE_TOLERANCE = 1e-12


def encode(value):
    return (json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False) + "\n").encode()


def sha(data):
    return hashlib.sha256(data).hexdigest()


def archive_sources(archive):
    data = archive.read_bytes()
    if sha(data) != ARCHIVE_SHA256:
        raise ValueError("Original release archive does not match the frozen 1.0.0 SHA256")
    with tarfile.open(archive, "r:gz") as source:
        old = source.extractfile(OLD_MEMBER).read()
        fixture = source.extractfile(FIXTURE_MEMBER).read()
    return old, fixture


def original_function(source):
    # Execute the exact released module in an isolated namespace. Its relative
    # imports resolve the same pinned numerical dependencies as the new wrapper;
    # no package module or installed ruptures class is monkeypatched.
    module = types.ModuleType("account_history_analyzer._released_pelt_benchmark")
    module.__package__ = "account_history_analyzer"
    exec(compile(source, OLD_MEMBER, "exec"), module.__dict__)
    from ruptures.costs import CostL2
    if module.CostL2 is not CostL2:
        raise ValueError("Original optimizer does not use the pinned CostL2 class")
    return module.pelt_l2


def provenance(old_source, fixture_bytes):
    import numpy
    from ruptures.costs import CostL2
    from account_history_analyzer import changepoints
    from account_history_analyzer._vendor import ruptures_pr383
    if metadata.version("ruptures") != "1.1.10":
        raise ValueError("Benchmark requires the locked ruptures 1.1.10 dependency")
    vendor = Path(ruptures_pr383.__file__).with_suffix(".json")
    details = json.loads(vendor.read_text())
    return {"archive_sha256": ARCHIVE_SHA256, "original_source_member": OLD_MEMBER,
            "original_source_sha256": sha(old_source), "fixture_result_member": FIXTURE_MEMBER,
            "fixture_result_sha256": sha(fixture_bytes),
            "current_wrapper_sha256": sha(Path(changepoints.__file__).read_bytes()),
            "vendor_module_sha256": sha(Path(ruptures_pr383.__file__).read_bytes()),
            "vendor_method_sha256": sha(inspect.getsource(ruptures_pr383.PeltMinSize._seg).encode()),
            "vendor_commit": details["commit"], "vendor_metadata_sha256": sha(vendor.read_bytes()),
            "cost": "ruptures.costs.CostL2", "cost_source_sha256": sha(inspect.getsource(CostL2).encode()),
            "ruptures_version": metadata.version("ruptures"), "numpy_version": numpy.__version__,
            "current_optimizer": changepoints.OPTIMIZER,
            "original_optimizer": "pelt_l2_min_size_safe_pruning_v1"}


def prepare(archive):
    old_source, fixture_bytes = archive_sources(archive)
    recorded = json.loads(fixture_bytes)["modules"]["style"]["payload"]
    stream = next(item for item in recorded["streams"] if item["scope_type"] == "pooled" and item["kind"] == "comment")
    change = next(item for item in recorded["changes"] if item["stream_id"] == stream["stream_id"])
    matrices = [{"case": "archived_standardized_style_matrix", "rows": change["scaling"]["standardized_rows"],
                 "penalty": change["penalty_beta"],
                 "construction": "Unmodified standardized_rows of archived pooled comment primary stream; archived primary beta."}]
    for count in (128, 256):
        # Counter-based fixed input generation, not a feature extractor or a
        # stochastic experiment. Eight coordinates use SHA256-derived fractions.
        stationary = [[int.from_bytes(hashlib.sha256(f"ahas-pelt-benchmark-v1:{row}:{column}".encode()).digest()[:8], "big") / 2**64 - 0.5
                       for column in range(8)] for row in range(count)]
        stepped = [[value + (-1.0 if row < count // 3 else 1.0 if row < 2 * count // 3 else 0.0)
                    for value in values] for row, values in enumerate(stationary)]
        matrices.extend([
            {"case": f"constructed_stationary_n{count}", "rows": stationary, "penalty": math.log(count),
             "construction": "Eight coordinates: uint64(first8(SHA256('ahas-pelt-benchmark-v1:row:column')))/2^64 - 0.5; beta=ln(N)."},
            {"case": f"constructed_steps_n{count}", "rows": stepped, "penalty": math.log(count),
             "construction": "Same stationary coordinates plus common offsets -1, +1, 0 in intervals [0,N//3), [N//3,2*N//3), [2*N//3,N); beta=ln(N)."},
        ])
    workloads = []
    for matrix in matrices:
        for minimum in (3, 20):
            rows = matrix["rows"]
            if len(rows) < minimum or not rows or not rows[0] or any(len(row) != len(rows[0]) for row in rows):
                raise ValueError("Invalid fixed benchmark matrix")
            workloads.append({"workload_id": matrix["case"] + f"_min{minimum}", "case": matrix["case"],
                "rows": rows, "rows_sha256": sha(encode(rows)), "n": len(rows), "dimensions": len(rows[0]),
                "penalty": matrix["penalty"], "min_size": minimum, "jump": 1,
                "construction": matrix["construction"]})
    return workloads, provenance(old_source, fixture_bytes)


def worker(args):
    import numpy as np
    from account_history_analyzer.changepoints import pelt_l2
    if os.environ.get("AHAS_NETWORK_ISOLATION") != "linux_seccomp_socket_denial":
        raise ValueError("Run under scripts/offline_exec.py to deny networking in every worker")
    job = json.loads(args.job.read_text())
    function = pelt_l2 if args.worker == VARIANTS[1] else original_function(archive_sources(args.archive)[0])
    signal = np.asarray(job["rows"], dtype=np.float64)
    signal.flags.writeable = False
    keywords = {"min_size": job["min_size"], "jump": job["jump"]}
    baseline_rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    expected = function(signal, job["penalty"], **keywords)  # Untimed warmup.
    times = []
    for _ in range(args.repeats):
        gc.collect()
        start = time.perf_counter_ns()
        actual = function(signal, job["penalty"], **keywords)
        times.append((time.perf_counter_ns() - start) / 1e9)
        if actual != expected:
            raise ValueError("Optimizer output changed between identical timing repetitions")
    allocation_peaks = []
    for _ in range(args.repeats):
        gc.collect()
        tracemalloc.start()
        actual = function(signal, job["penalty"], **keywords)
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        allocation_peaks.append(peak)
        if actual != expected:
            raise ValueError("Optimizer output changed during allocation measurement")
    final_rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    sys.stdout.buffer.write(encode({"variant": args.worker, "result": expected,
        "receipt": {"timing_seconds": times, "median_timing_seconds": statistics.median(times),
            "tracemalloc_peak_bytes": allocation_peaks, "median_tracemalloc_peak_bytes": statistics.median(allocation_peaks),
            "baseline_process_peak_rss_kib": baseline_rss, "final_process_peak_rss_kib": final_rss,
            "increase_in_process_peak_rss_kib": max(0, final_rss - baseline_rss),
            "network_isolation": os.environ["AHAS_NETWORK_ISOLATION"]}}))


def markdown(comparison, receipts):
    lines = ["# PELT PR #383 comparison", "", "Numerical results use identical input arrays and pinned CostL2. Runtime and allocation observations below are benchmark receipts, separate from `comparison.json`.", "",
        "| Workload | N × D | Minimum | Same boundaries | Objective difference | Old median ms | New median ms | New/old time | Old/new traced peak KiB |",
        "|---|---:|---:|---|---:|---:|---:|---:|---:|"]
    for case, timings in zip(comparison["workloads"], receipts["workloads"], strict=True):
        old, new = (timings["variants"][variant] for variant in VARIANTS)
        lines.append(f"| {case['workload_id']} | {case['n']} × {case['dimensions']} | {case['min_size']} | {case['boundaries_equal']} | {case['objective_absolute_difference']:.3g} | {old['median_timing_seconds']*1000:.3f} | {new['median_timing_seconds']*1000:.3f} | {new['median_timing_seconds']/old['median_timing_seconds']:.3f} | {old['median_tracemalloc_peak_bytes']/1024:.1f} / {new['median_tracemalloc_peak_bytes']/1024:.1f} |")
    lines.extend(["", f"Five untraced timing repetitions and five separately traced allocation repetitions follow one untimed warmup in a fresh worker for each optimizer/workload (configured repetitions: {receipts['repetitions']}).",
        "", "Tracemalloc peaks describe allocations it tracks during a single call, excluding the already-created input. RSS is process-wide high-water memory including imports and warmup; its increase can be zero when imports set the peak. Tracing is disabled during timing.",
        "", "Boundaries and objectives are exposed independently: equal objective within the explicit tolerance need not imply identical boundaries under ties. These bounded workloads are engineering observations, not asymptotic, cross-platform, or real-world detection-accuracy claims.", ""])
    return "\n".join(lines).encode()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, default=ARCHIVE)
    parser.add_argument("--out", type=Path, default=ROOT / "qa/pr383/benchmark")
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--describe", action="store_true")
    parser.add_argument("--worker", choices=VARIANTS, help=argparse.SUPPRESS)
    parser.add_argument("--job", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if not 1 <= args.repeats <= 10:
        parser.error("--repeats must be between 1 and 10")
    if args.worker:
        worker(args)
        return 0
    workloads, source = prepare(args.archive)
    if args.describe:
        sys.stdout.buffer.write(encode({"provenance": source, "workloads": [{k: v for k, v in job.items() if k != "rows"} for job in workloads]}))
        return 0
    if platform.system() != "Linux" or os.environ.get("AHAS_NETWORK_ISOLATION") != "linux_seccomp_socket_denial":
        parser.error("Benchmark requires Linux and scripts/offline_exec.py (RSS units and network isolation)")
    targets = [args.out / name for name in ("inputs.json", "comparison.json", "receipts.json", "report.md")]
    if any(path.exists() for path in targets):
        parser.error("Output files already exist; choose a fresh --out directory to preserve receipts")
    comparisons, receipts = [], []
    began = time.perf_counter()
    with tempfile.TemporaryDirectory(prefix="ahas-pr383-benchmark-") as temporary:
        for index, job in enumerate(workloads):
            path = Path(temporary) / "job.json"
            path.write_bytes(encode(job))
            actual = {}
            # Alternate which variant runs first across jobs to expose rather
            # than systematically favor one side of an environmental time trend.
            order = VARIANTS if index % 2 == 0 else tuple(reversed(VARIANTS))
            for variant in order:
                command = [sys.executable, str(Path(__file__).resolve()), "--worker", variant,
                    "--job", str(path), "--archive", str(args.archive.resolve()), "--repeats", str(args.repeats)]
                finished = subprocess.run(command, check=False, capture_output=True, timeout=120)
                if finished.returncode:
                    raise RuntimeError(f"Benchmark worker failed ({job['workload_id']}, {variant}): {finished.stderr.decode()}")
                actual[variant] = json.loads(finished.stdout)
            old, new = (actual[variant]["result"] for variant in VARIANTS)
            comparisons.append({**{k: v for k, v in job.items() if k != "rows"},
                "results": {variant: actual[variant]["result"] for variant in VARIANTS},
                "boundaries_equal": old["internal_boundaries"] == new["internal_boundaries"],
                "objective_absolute_difference": abs(old["objective"] - new["objective"]),
                "objectives_close": math.isclose(old["objective"], new["objective"], abs_tol=ABSOLUTE_TOLERANCE, rel_tol=RELATIVE_TOLERANCE)})
            receipts.append({"workload_id": job["workload_id"], "execution_order": list(order),
                "variants": {variant: actual[variant]["receipt"] for variant in VARIANTS}})
            print(f"Completed {index + 1}/{len(workloads)} optimizer comparisons", file=sys.stderr, flush=True)
    comparison = {"schema_version": "1.0.0", "scope": "bounded_optimizer_engineering_comparison",
        "provenance": source, "objective_absolute_tolerance": ABSOLUTE_TOLERANCE,
        "objective_relative_tolerance": RELATIVE_TOLERANCE, "workloads": comparisons,
        "all_boundaries_equal": all(item["boundaries_equal"] for item in comparisons),
        "all_objectives_close": all(item["objectives_close"] for item in comparisons)}
    operational = {"schema_version": "1.0.0", "command": [sys.executable, *sys.argv], "cwd": str(Path.cwd()),
        "python": platform.python_version(), "platform": platform.platform(), "processor": platform.processor(),
        "repetitions": args.repeats, "untimed_warmups": 1, "timing_tracemalloc_enabled": False,
        "worker_isolation": "fresh_subprocess_per_optimizer_and_workload",
        "blas_thread_environment": {key: os.environ.get(key) for key in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS")},
        "elapsed_seconds": time.perf_counter() - began, "workloads": receipts,
        "memory_scope": "Separate per-call tracemalloc peaks; process ru_maxrss in Linux KiB includes imports, input, warmup and previous repetitions."}
    args.out.mkdir(parents=True, exist_ok=True)
    documents = (encode({"schema_version": "1.0.0", "workloads": workloads}), encode(comparison), encode(operational), markdown(comparison, operational))
    for path, data in zip(targets, documents, strict=True):
        path.write_bytes(data)
    print(json.dumps({"workloads": len(comparisons), "all_boundaries_equal": comparison["all_boundaries_equal"],
                      "all_objectives_close": comparison["all_objectives_close"], "output": str(args.out)}))
    return 0 if comparison["all_objectives_close"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
