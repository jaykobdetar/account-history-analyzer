"""Export payload schema definitions into source and installed contracts.

Run from a development checkout with the package installed: python
scripts/sync_schemas.py. Paths are resolved relative to this script, never cwd.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from account_history_analyzer.payload_schemas import evidence_schema, records_features_schema, tighten_config, tighten_results, windows_schema
from account_history_analyzer.evaluation_schemas import synthetic_evaluation_schema


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Fail if generated contracts differ")
    args = parser.parse_args()
    root = Path(__file__).resolve().parent.parent
    schemas = root / "schemas"
    result = tighten_results(
        json.loads((schemas / "results.schema.json").read_text(encoding="utf-8")),
        json.loads((schemas / "snapshot.schema.json").read_text(encoding="utf-8")),
    )
    changed = False
    config = tighten_config(json.loads((schemas / "config.schema.json").read_text(encoding="utf-8")))
    for name, schema in {"results": result, "records_features": records_features_schema(), "evidence": evidence_schema(), "config": config, "windows": windows_schema(), "evaluation_synthetic": synthetic_evaluation_schema()}.items():
        data = (json.dumps(schema, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
        destinations = (
            schemas / f"{name}.schema.json",
            root / "src" / "account_history_analyzer" / "contracts" / f"{name}.schema.json",
        )
        for path in destinations:
            if args.check:
                changed |= not path.exists() or path.read_bytes() != data
            else:
                path.write_bytes(data)
    return int(changed)


if __name__ == "__main__":
    raise SystemExit(main())
