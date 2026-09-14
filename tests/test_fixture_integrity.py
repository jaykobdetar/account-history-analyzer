"""FIX: original construction artifacts regenerate exactly, evaluator-only."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def test_fix01_original_fixture_index_matches_supplied_bytes():
    fixture_root = ROOT / "fixtures"
    index = json.loads((fixture_root / "fixture_index.json").read_text(encoding="utf-8"))
    assert index["fixture_version"] == "1.0.0"
    names = set()
    for entry in index["files"]:
        assert Path(entry["file"]).name == entry["file"]
        assert entry["file"] not in names
        names.add(entry["file"])
        data = (fixture_root / entry["file"]).read_bytes()
        assert len(data) == entry["bytes"]
        assert hashlib.sha256(data).hexdigest() == entry["sha256"]


def test_fix02_generator_is_byte_identical_in_separate_processes(tmp_path):
    originals = ROOT / "fixtures"
    generated_names = {path.name for path in originals.glob("*.json*")}
    for seed, timezone in (("1", "Pacific/Honolulu"), ("987654", "Europe/London")):
        destination = tmp_path / f"generation-{seed}"
        env = dict(os.environ, PYTHONHASHSEED=seed, TZ=timezone)
        completed = subprocess.run(
            [sys.executable, str(originals / "generate_fixtures.py"), "--out", str(destination)],
            cwd=tmp_path, env=env, capture_output=True, check=False,
        )
        assert completed.returncode == 0, completed.stderr.decode("utf-8")
        assert {path.name for path in destination.iterdir()} == generated_names
        for name in sorted(generated_names):
            assert (destination / name).read_bytes() == (originals / name).read_bytes(), name
