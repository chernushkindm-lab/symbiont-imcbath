"""Run fresh MEMOTE, save machine-readable evidence, and preserve its exit code."""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import platform
import subprocess
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", type=Path, default=root / "ModelFiles/xml/iMcBath.xml")
    parser.add_argument("--output", type=Path, default=root / "reports/generated")
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    model_path = args.model.resolve()
    metadata = {
        "started_utc": datetime.now(timezone.utc).isoformat(),
        "model_file": model_path.name,
        "model_sha256": hashlib.sha256(model_path.read_bytes()).hexdigest(),
        "upstream_commit": "f3ab4c6bf5d78d8c2f0daeaf40e843fe458c8160",
        "python": platform.python_version(),
        "platform": platform.platform(),
        "solver": "glpk",
        "solver_timeout_seconds": 10,
        "suite": "MEMOTE built-in tests; no custom experimental phenotype dataset",
        "packages": {name: importlib.metadata.version(name) for name in
                     ["memote", "cobra", "swiglpk", "numpy", "pandas", "pytest", "pandera"]},
    }
    code = 2
    try:
        # Separate exact-chemistry ledger for the pinned JSON companion only.
        # Custom --model files must never be mislabeled as this baseline audit.
        if model_path == (root / "ModelFiles/xml/iMcBath.xml").resolve():
            subprocess.run([
                sys.executable, str(root / "scripts/audit_reactions.py"),
                "--model", str(root / "ModelFiles/json/iMcBath.json"),
                "--output", str(output / "reaction-audit"), "--include-source",
            ], check=True)
            metadata["exact_reaction_audit"] = "reaction-audit/summary.json (JSON companion; independent source hash)"
        else:
            metadata["exact_reaction_audit"] = "not run: custom SBML has no verified JSON companion"
        import cobra
        from memote.suite import api
        cobra.Configuration().solver = "glpk"
        model, sbml_version, notifications = api.validate_model(str(model_path))
        metadata["sbml_version"] = sbml_version
        metadata["sbml_notifications"] = notifications
        if model is None:
            metadata["status"] = "sbml_load_failed"
            api.validation_report(str(model_path), notifications, str(output / "memote.html"))
        else:
            code, results = api.test_model(
                model, sbml_version=sbml_version, results=True,
                pytest_args=["--tb=short", "-q", "--junitxml=" + str(output / "junit.xml")],
                solver_timeout=10,
            )
            code = int(code)
            (output / "memote-results.json").write_text(
                json.dumps(results, indent=2, default=str), encoding="utf-8")
            (output / "memote-scored.json").write_text(
                api.snapshot_report(results, html=False), encoding="utf-8")
            (output / "memote.html").write_text(api.snapshot_report(results), encoding="utf-8")
            metadata["status"] = "passed" if code == 0 else "completed_with_findings" if code == 1 else "suite_error"
    except Exception as error:
        metadata["status"] = "execution_error"
        metadata["error"] = str(error)
        (output / "error.txt").write_text(traceback.format_exc(), encoding="utf-8")
        traceback.print_exc()
        code = 2
    metadata["pytest_exit_code"] = code
    metadata["finished_utc"] = datetime.now(timezone.utc).isoformat()
    (output / "run-metadata.json").write_text(json.dumps(metadata, indent=2, default=str), encoding="utf-8")
    print(json.dumps({"status": metadata["status"], "exit_code": code, "output": str(output)}))
    return code


if __name__ == "__main__":
    sys.exit(main())
