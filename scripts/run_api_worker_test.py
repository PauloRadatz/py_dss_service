#!/usr/bin/env python
"""
API + Worker end-to-end test script.

Submits a job via the REST API and polls until it completes, then prints results.
Requires both the API server and worker to be running in separate terminals:

    Terminal 1:  python -m py_dss_service.api.main
    Terminal 2:  python -m py_dss_service.worker.main

Usage:
    python scripts/run_api_worker_test.py [base_url]

    base_url defaults to http://127.0.0.1:8000
"""

import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

BASE_URL = sys.argv[1].rstrip("/") if len(sys.argv) > 1 else "http://127.0.0.1:8000"

POLL_INTERVAL = 1.0   # seconds between status checks
POLL_TIMEOUT  = 60.0  # total seconds to wait for completion

DEFAULT_SCRIPT = """Clear
New Circuit.TestCkt basekv=12.47 pu=1.0 phases=3
New Line.Line1 Bus1=SourceBus Bus2=LoadBus Length=1 Units=km r1=0.01 x1=0.02
New Load.Load1 Bus1=LoadBus kW=100 kvar=50 kV=12.47
Set VoltageBases=[12.47]
CalcVoltageBases"""


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

def _request(method: str, path: str, body: dict | None = None) -> dict:
    """Make an HTTP request and return parsed JSON response."""
    url = f"{BASE_URL}{path}"
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Content-Type": "application/json", "Accept": "application/json"}

    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        body_text = e.read().decode()
        raise RuntimeError(f"HTTP {e.code} {e.reason} — {body_text}") from e


def get(path: str) -> dict:
    return _request("GET", path)


def post(path: str, body: dict) -> dict:
    return _request("POST", path, body)


# ---------------------------------------------------------------------------
# Main test flow
# ---------------------------------------------------------------------------

def main() -> None:
    print(f"\n{'='*60}")
    print("API + Worker End-to-End Test")
    print(f"Base URL: {BASE_URL}")
    print(f"{'='*60}\n")

    # ------------------------------------------------------------------ 1
    print("1. Checking API health...")
    try:
        health = get("/health")
        assert health.get("status") == "ok", f"Unexpected health response: {health}"
        print(f"   OK — {health}")
    except Exception as e:
        print(f"   FAILED: {e}")
        print("   Is the API server running?  python -m py_dss_service.api.main")
        sys.exit(1)

    # ------------------------------------------------------------------ 2
    print("\n2. Submitting job...")
    try:
        submit_resp = post("/jobs", {"dss_script": DEFAULT_SCRIPT})
        job_id = submit_resp["job_id"]
        print(f"   Job ID : {job_id}")
        print(f"   Status : {submit_resp.get('status')}")
    except Exception as e:
        print(f"   FAILED: {e}")
        sys.exit(1)

    # ------------------------------------------------------------------ 3
    print(f"\n3. Polling for completion (timeout={POLL_TIMEOUT}s)...")
    deadline = time.time() + POLL_TIMEOUT
    final_status = None

    while time.time() < deadline:
        try:
            status_resp = get(f"/jobs/{job_id}")
            current_status = status_resp.get("status")

            if current_status in ("done", "failed"):
                final_status = current_status
                print(f"   Status: {current_status}")
                break

            print(f"   Status: {current_status} — waiting {POLL_INTERVAL}s...")
            time.sleep(POLL_INTERVAL)

        except Exception as e:
            print(f"   Poll error: {e}")
            time.sleep(POLL_INTERVAL)

    if final_status is None:
        print(f"   TIMEOUT — job did not complete within {POLL_TIMEOUT}s")
        print("   Is the worker running?  python -m py_dss_service.worker.main")
        sys.exit(1)

    # ------------------------------------------------------------------ 4
    print("\n4. Fetching job result...")
    try:
        result_resp = get(f"/jobs/{job_id}/result")
        result = result_resp.get("result", {})

        print(f"   Converged          : {result.get('converged')}")
        print(f"   Simulation type    : {result.get('simulation_type')}")
        print(f"   Execution time (s) : {result.get('execution_time_seconds')}")

        circuit_summary = result.get("circuit_summary")
        if circuit_summary and isinstance(circuit_summary, dict):
            print(f"\n   Circuit summary ({len(circuit_summary)} quantities):")
            for i, (key, value) in enumerate(list(circuit_summary.items())[:5]):
                print(f"     {key}: {value}")
            if len(circuit_summary) > 5:
                print(f"     ... ({len(circuit_summary) - 5} more)")

        voltages_ln = result.get("voltages_ln")
        if voltages_ln:
            mag = voltages_ln.get("magnitude", {})
            print(f"\n   Voltages LN — buses with data: {len(mag)}")

        if final_status == "failed":
            print(f"\n   Error: {result_resp.get('error')}")

    except Exception as e:
        print(f"   FAILED: {e}")
        sys.exit(1)

    # ------------------------------------------------------------------ done
    print(f"\n{'='*60}")
    status_label = "PASSED" if final_status == "done" else "FAILED (job failed)"
    print(f"Test {status_label}")
    print(f"{'='*60}\n")

    sys.exit(0 if final_status == "done" else 1)


if __name__ == "__main__":
    main()
