"""M6: actual offline fixture evaluation and separation from construction truth."""
from copy import deepcopy
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

from jsonschema import Draft202012Validator
import pytest

from account_history_analyzer.config import AnalysisConfig
from account_history_analyzer.errors import InputError
from account_history_analyzer.evaluation_schemas import synthetic_evaluation_schema
from account_history_analyzer.evaluation_synthetic import boundary_context, evaluate_synthetic, numerical_checks
from account_history_analyzer.io import canonical_bytes, sha256_bytes
from account_history_analyzer.schemas import load_schema, validate

ROOT = Path(__file__).resolve().parents[1]


def fixture_subset(destination, cases, *, short=False):
    destination.mkdir()
    for case in cases:
        for suffix in (".jsonl", ".snapshot.json", ".truth.json"):
            name = case + suffix
            shutil.copyfile(ROOT / "fixtures" / name, destination / name)
        if short:
            path = destination / (case + ".jsonl")
            rows = path.read_bytes().splitlines()
            chosen = rows[:4] + rows[160:164]
            path.write_bytes(b"\n".join(chosen) + b"\n")
            path = destination / (case + ".truth.json")
            truth = json.loads(path.read_text())
            truth["record_count"] = 8
            if truth["transformation_starts_at_zero_based_record"] is not None:
                truth["transformation_starts_at_zero_based_record"] = 4
            path.write_bytes(canonical_bytes(truth))
    shutil.copyfile(ROOT / "fixtures" / "numerical_oracles.json", destination / "numerical_oracles.json")
    reindex(destination)
    return destination


def reindex(destination):
    entries = []
    for path in sorted(destination.iterdir()):
        if path.name != "fixture_index.json":
            data = path.read_bytes()
            entries.append({"file": path.name, "bytes": len(data), "sha256": sha256_bytes(data)})
    (destination / "fixture_index.json").write_bytes(canonical_bytes({"fixture_version": "1.0.0", "files": entries}))


def test_EVS01_public_numerical_helpers_match_original_oracles():
    oracles = json.loads((ROOT / "fixtures/numerical_oracles.json").read_text())
    checks = numerical_checks(oracles)
    assert len(checks) == 20
    assert all(check["status"] == "passed" for check in checks)
    changed = deepcopy(oracles)
    changed["pelt_unscaled_l2"]["optimal_objective"] = 2
    failed = [check for check in numerical_checks(changed) if check["status"] == "failed"]
    assert [check["check_id"] for check in failed] == ["pelt_objective"]


def test_EVS02_actual_arithmetic_empty_and_strict_output(tmp_path):
    directory = fixture_subset(tmp_path / "fixtures", ["arithmetic", "empty"])
    output = evaluate_synthetic(directory)
    validate(output, "evaluation_synthetic")
    assert output["status"] == "passed", [check for case in output["fixtures"] for check in case["checks"] if check["status"] == "failed"]
    assert output["check_counts"]["failed"] == 0
    assert output["check_counts"]["not_evaluated"] == 2
    assert output["dataset"]["shipped_scenarios_complete"] is False
    assert output["real_world_validation"] == "not_established"
    assert output["external_data"] == "not_evaluated"
    assert output["fixtures"][0]["summary"]["retained_words"] == 36
    assert output["fixtures"][1]["summary"]["record_count"] == 0
    assert synthetic_evaluation_schema() == load_schema("evaluation_synthetic")
    validator = Draft202012Validator(synthetic_evaluation_schema())
    for key in ("config_sha256", "real_world_validation", "fixtures"):
        bad = deepcopy(output)
        del bad[key]
        assert not validator.is_valid(bad)
    bad = deepcopy(output)
    bad["fixtures"][0]["summary"]["authorship_probability"] = 0
    assert not validator.is_valid(bad)
    assert canonical_bytes(output) == canonical_bytes(evaluate_synthetic(directory))


def test_EVS03_truth_mutation_changes_evaluation_only(tmp_path):
    directory = fixture_subset(tmp_path / "fixtures", ["arithmetic"])
    original = evaluate_synthetic(directory)
    path = directory / "arithmetic.truth.json"
    truth = json.loads(path.read_text())
    truth["gap_mean_seconds"] = 37
    path.write_bytes(canonical_bytes(truth))
    mutated = evaluate_synthetic(directory)
    assert original["fixtures"][0]["results_sha256"] == mutated["fixtures"][0]["results_sha256"]
    assert original["fixtures"][0]["canonical_snapshot_sha256"] == mutated["fixtures"][0]["canonical_snapshot_sha256"]
    assert original["dataset"]["content_sha256"] != mutated["dataset"]["content_sha256"]
    assert mutated["status"] == "failed"
    failures = [check["check_id"] for check in mutated["numerical_checks"] + mutated["fixtures"][0]["checks"] if check["status"] == "failed"]
    assert failures == ["fixture_index_integrity", "gap_mean_seconds"]


def test_EVS04_controlled_style_and_topic_operations_on_small_subsets(tmp_path):
    directory = fixture_subset(tmp_path / "fixtures", ["stable_constructed_style", "constructed_style_shift", "constructed_topic_shift"], short=True)
    output = evaluate_synthetic(directory)
    assert output["status"] == "passed", [check for case in output["fixtures"] for check in case["checks"] if check["status"] == "failed"]
    assert all(check["status"] == "passed" for check in output["cross_fixture_checks"])
    assert all(case["summary"]["record_count"] == 8 for case in output["fixtures"])
    style = next(case for case in output["fixtures"] if case["case"] == "constructed_style_shift")
    assert style["construction_boundary"]["record_interval"] == [3, 4]
    assert all(stream["status"] == "insufficient_data" for stream in style["construction_boundary"]["streams"])


def test_EVS05_parameter_dependent_checks_explicitly_skip(tmp_path):
    directory = fixture_subset(tmp_path / "fixtures", ["arithmetic"])
    config = AnalysisConfig.from_mapping({"activity": {"sliding_window_seconds": [5], "burst_duration_seconds": 5},
        "style": {"minimum_record_words": 1, "contraction_minimum_opportunities": 3}})
    output = evaluate_synthetic(directory, config)
    checks = {check["check_id"]: check for check in output["fixtures"][0]["checks"]}
    for name in ("sliding_30_seconds", "greedy_burst_membership", "contraction_qualification", "default_style_eligibility"):
        assert checks[name]["status"] == "not_evaluated"
        assert checks[name]["reason"]
    assert output["status"] == "passed"


def test_EVS06_missing_or_unsafe_fixture_inputs_fail_explicitly(tmp_path):
    with pytest.raises(InputError):
        evaluate_synthetic(tmp_path / "absent")
    directory = fixture_subset(tmp_path / "fixtures", ["empty"])
    path = directory / "empty.truth.json"
    path.unlink()
    with pytest.raises(InputError, match="missing_fixture_file"):
        evaluate_synthetic(directory)
    index_path = directory / "fixture_index.json"
    index = json.loads(index_path.read_text())
    index["files"][0]["file"] = "../outside.jsonl"
    index_path.write_bytes(canonical_bytes(index))
    with pytest.raises(InputError, match="invalid_fixture_index"):
        evaluate_synthetic(directory)


def test_EVS07_nonconstruction_ground_truth_rejected(tmp_path):
    directory = fixture_subset(tmp_path / "fixtures", ["empty"])
    path = directory / "empty.truth.json"
    truth = json.loads(path.read_text())
    truth["human_bot_or_ai_ground_truth"] = "human"
    path.write_bytes(canonical_bytes(truth))
    with pytest.raises(InputError, match="invalid_synthetic_truth"):
        evaluate_synthetic(directory)


def test_EVS08_boundary_geometry_without_detection_cutoff():
    windows = [{"window_id": "a", "first_record_position": 0, "last_record_position": 3},
               {"window_id": "b", "first_record_position": 4, "last_record_position": 7}]
    boundary = {"boundary_id": "boundary", "record_interval": [3, 4], "left_window_id": "a", "right_window_id": "b",
                "left_record_id": "source3", "right_record_id": "source4"}
    style = {"changes": [{"stream_id": "stream", "status": "ok", "boundaries": [boundary]}]}
    for position, relation, gap, neighbor in ((4, "overlap", 0, True), (5, "touching", 0, True),
                                              (7, "separated", 2, True), (12, "separated", 7, False)):
        output = boundary_context(position, style, windows)
        candidate = output["streams"][0]["candidates"][0]
        assert (candidate["relation"], candidate["record_position_gap"], candidate["neighboring_window"]) == (relation, gap, neighbor)
    assert boundary_context(None, style, windows) is None
    assert boundary_context(4, {"changes": []}, windows)["streams"] == []


def test_EVS09_evaluator_separate_process_identity(tmp_path):
    directory = fixture_subset(tmp_path / "fixtures", ["arithmetic", "empty"])
    command = [sys.executable, "-c", "import sys; from account_history_analyzer.evaluation_synthetic import evaluate_synthetic; "
        "from account_history_analyzer.io import canonical_bytes; sys.stdout.buffer.write(canonical_bytes(evaluate_synthetic(sys.argv[1])))", str(directory)]
    outputs = []
    for seed, timezone, cwd in (("1", "Pacific/Honolulu", ROOT), ("9959", "Europe/London", tmp_path)):
        process = subprocess.run(command, cwd=cwd, env=dict(os.environ, PYTHONHASHSEED=seed, TZ=timezone),
                                 check=False, capture_output=True)
        assert process.returncode == 0, process.stderr.decode()
        outputs.append(process.stdout)
    assert outputs[0] == outputs[1]


def test_EVS10_symlink_fixture_index_is_rejected(tmp_path):
    directory = fixture_subset(tmp_path / "fixtures", ["empty"])
    index = directory / "fixture_index.json"
    target = tmp_path / "outside_index.json"
    index.rename(target)
    index.symlink_to(target)
    with pytest.raises(InputError, match="invalid_fixture_index"):
        evaluate_synthetic(directory)
