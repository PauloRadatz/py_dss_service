#!/usr/bin/env python
"""
Standalone worker test script.

Creates a job directly in the filesystem and runs the worker to process it.
Useful for testing worker functionality without needing the API server.

Usage:
    python scripts/run_worker_test.py [dss_script_file] [actions_json]

If no script file is provided, uses a default test script.
"""

import json
import sys
import time
from pathlib import Path

# Add src to path so we can import py_dss_service
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from py_dss_service.common.ids import generate_job_id
from py_dss_service.common.time import utc_now_iso
from py_dss_service.logging import get_logger, setup_logging
from py_dss_service.schemas.job_spec import (
    Action,
    AddLineInVsourceAction,
    DSSCommandAction,
    JobSpec,
)
from py_dss_service.settings import get_settings
from py_dss_service.worker.tasks import claim_job, process_job

DEFAULT_SCRIPT = """Clear
New Circuit.TestCkt basekv=12.47 pu=1.0 phases=3
New Line.Line1 Bus1=SourceBus Bus2=LoadBus Length=1 Units=km r1=0.01 x1=0.02
New Load.Load1 Bus1=LoadBus kW=100 kvar=50 kV=12.47
Set VoltageBases=[12.47]
CalcVoltageBases"""


def parse_actions(actions_input: str | list[dict] | None = None) -> list[Action]:
    """
    Parse actions from JSON string, list of dicts, or None.

    Args:
        actions_input: JSON string, list of dicts, or None.

    Returns:
        List of Action objects.
    """
    if actions_input is None:
        return []

    if isinstance(actions_input, list):
        actions_data = actions_input
    elif isinstance(actions_input, str):
        try:
            actions_data = json.loads(actions_input)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid actions JSON: {e}")
    else:
        raise TypeError(f"actions_input must be str, list, or None, got {type(actions_input)}")

    actions: list[Action] = []
    for action_dict in actions_data:
        action_type = action_dict.get("type")
        if action_type == "dss_command":
            actions.append(DSSCommandAction(**action_dict))
        elif action_type == "add_line_in_vsource":
            actions.append(AddLineInVsourceAction(**action_dict))
        else:
            print(f"Warning: Unknown action type '{action_type}', skipping")

    return actions


def create_test_job(dss_script: str, actions: list | None = None) -> tuple[str, Path]:
    """
    Create a test job file in the pending directory.

    Returns:
        Tuple of (job_id, job_file_path).
    """
    settings = get_settings()
    settings.ensure_directories()

    if actions is None:
        actions = []

    job_id = generate_job_id()
    job_spec = JobSpec(
        job_id=job_id,
        dss_script=dss_script,
        created_at=utc_now_iso(),
        actions=actions,
    )

    job_file = settings.jobs_pending_dir / f"{job_id}.json"
    job_file.write_text(job_spec.model_dump_json(indent=2), encoding="utf-8")

    return job_id, job_file


def main(actions: str | list[dict] | None = None, dss_script: str | None = None) -> None:
    """
    Main test function.

    Args:
        actions: Optional actions (JSON string or list of dicts).
        dss_script: Optional DSS script. If None, uses DEFAULT_SCRIPT or reads from sys.argv.
    """
    setup_logging(level="INFO")
    logger = get_logger("run_worker_test")

    if dss_script is None:
        if len(sys.argv) > 1 and sys.argv[1] and sys.argv[1].strip():
            script_file = Path(sys.argv[1])
            if not script_file.exists():
                print(f"Error: Script file not found: {script_file}")
                sys.exit(1)
            dss_script = script_file.read_text(encoding="utf-8")
            print(f"Using script from: {script_file}")
        else:
            dss_script = DEFAULT_SCRIPT
            print("Using default test script")
    else:
        print("Using provided DSS script")

    if actions is None:
        if len(sys.argv) > 2:
            try:
                actions = parse_actions(sys.argv[2])
                print(f"Using {len(actions)} action(s) from command line")
            except (json.JSONDecodeError, ValueError) as e:
                print(f"Warning: Invalid actions JSON '{sys.argv[2]}': {e}")
                actions = []
        else:
            actions = []
    else:
        try:
            actions = parse_actions(actions)
            print(f"Using {len(actions)} action(s)")
        except (ValueError, TypeError) as e:
            print(f"Error parsing actions: {e}")
            sys.exit(1)

    print(f"\n{'='*60}")
    print("Worker Test Script")
    print(f"{'='*60}\n")

    # Create test job
    print("1. Creating test job...")
    job_id, job_file = create_test_job(dss_script, actions=actions)
    print(f"   Job created: {job_id}")
    print(f"   Location: {job_file}")

    settings = get_settings()

    # Claim and process job
    print("\n2. Claiming job...")
    claimed = claim_job(settings, logger)

    if claimed is None:
        print("   Failed to claim job")
        sys.exit(1)

    running_file, job_spec = claimed
    print(f"   Job claimed: {job_spec.job_id}")

    # Process job
    print("\n3. Processing job...")
    start_time = time.time()

    try:
        process_job(settings, running_file, job_spec, logger)
        elapsed = time.time() - start_time
        print(f"   Job processed successfully ({elapsed:.2f}s)")
    except Exception as e:
        print(f"   Job processing failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    # Check results
    print("\n4. Checking results...")
    possible_paths = [
        settings.results_dir.resolve() / f"{job_id}.json",
        settings.results_dir / f"{job_id}.json",
    ]

    result_file = None
    for path in possible_paths:
        if path.exists():
            result_file = path
            break

    if result_file and result_file.exists():
        result_data = json.loads(result_file.read_text(encoding="utf-8"))
        print(f"   Result file: {result_file}")
        print(f"   Converged: {result_data.get('converged')}")

        circuit_summary = result_data.get("circuit_summary")
        if circuit_summary and isinstance(circuit_summary, dict):
            print(f"   Circuit summary quantities: {len(circuit_summary)}")
            print(f"\n   First few quantities:")
            for i, (key, value) in enumerate(list(circuit_summary.items())[:3]):
                print(f"     {key}: {value}")
            if len(circuit_summary) > 3:
                print(f"     ... ({len(circuit_summary) - 3} more quantities)")

        if result_data.get("error"):
            print(f"   Error: {result_data.get('error')}")
    else:
        print(f"   Result file not found")
        print(f"   Searched in: {settings.results_dir.resolve()}")

    # Check log file
    log_file = settings.logs_dir / f"{job_id}.log"
    if log_file.exists():
        print(f"\n5. Log file: {log_file}")

    print(f"\n{'='*60}")
    print("Test completed!")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
