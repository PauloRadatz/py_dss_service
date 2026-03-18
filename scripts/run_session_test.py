#!/usr/bin/env python
"""
Sessions API end-to-end test script.

Creates a session, loads a circuit, solves, fetches results, then closes the session.
Requires the API server to be running:

    python -m py_dss_service.api.main

Usage:
    python scripts/run_session_test.py [base_url]

    base_url defaults to http://127.0.0.1:8000
"""

import json
import sys
import urllib.error
import urllib.request

BASE_URL = sys.argv[1].rstrip("/") if len(sys.argv) > 1 else "http://127.0.0.1:8000"

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
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        body_text = e.read().decode()
        raise RuntimeError(f"HTTP {e.code} {e.reason} — {body_text}") from e


def get(path: str) -> dict:
    return _request("GET", path)


def post(path: str, body: dict | None = None) -> dict:
    return _request("POST", path, body or {})


def delete(path: str) -> dict:
    return _request("DELETE", path)


# ---------------------------------------------------------------------------
# Main test flow
# ---------------------------------------------------------------------------

def main() -> None:
    print(f"\n{'='*60}")
    print("Sessions API End-to-End Test")
    print(f"Base URL: {BASE_URL}")
    print(f"{'='*60}\n")

    session_id = None

    try:
        # -------------------------------------------------------------- 1
        print("1. Checking API health...")
        try:
            health = get("/health")
            assert health.get("status") == "ok", f"Unexpected health response: {health}"
            print(f"   OK — {health}")
        except Exception as e:
            print(f"   FAILED: {e}")
            print("   Is the API server running?  python -m py_dss_service.api.main")
            sys.exit(1)

        # -------------------------------------------------------------- 2
        print("\n2. Creating session...")
        create_resp = post("/sessions")
        session_id = create_resp["session_id"]
        print(f"   Session ID : {session_id}")
        print(f"   Status     : {create_resp.get('status')}")

        # -------------------------------------------------------------- 3
        print("\n3. Loading circuit...")
        load_resp = post(f"/sessions/{session_id}/load", {"dss_script": DEFAULT_SCRIPT})
        print(f"   Status       : {load_resp.get('status')}")
        print(f"   Circuit name : {load_resp.get('circuit_name')}")

        # -------------------------------------------------------------- 4
        print("\n4. Solving (snapshot power flow)...")
        solve_resp = post(f"/sessions/{session_id}/solve", {"simulation_type": "snapshot"})
        print(f"   Status     : {solve_resp.get('status')}")
        print(f"   Converged  : {solve_resp.get('converged')}")

        # -------------------------------------------------------------- 5
        print("\n5. Fetching results...")
        results_resp = get(f"/sessions/{session_id}/results")
        result = results_resp.get("result", {})

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

        # -------------------------------------------------------------- 5b
        print("\n6. Fetching circuit_summary sub-endpoint...")
        cs_resp = get(f"/sessions/{session_id}/results/circuit_summary")
        cs_data = cs_resp.get("data") or {}
        print(f"   Field      : {cs_resp.get('field')}")
        print(f"   Quantities : {len(cs_data)}")

        # -------------------------------------------------------------- 5c
        print("\n7. Fetching voltages_ln sub-endpoint...")
        vln_resp = get(f"/sessions/{session_id}/results/voltages_ln")
        vln_data = vln_resp.get("data") or {}
        mag = vln_data.get("magnitude", {})
        print(f"   Field      : {vln_resp.get('field')}")
        print(f"   Buses      : {len(mag)}")

        # -------------------------------------------------------------- 6
        print("\n8. Verifying session is listed...")
        list_resp = get("/sessions")
        count = list_resp.get("count", 0)
        ids = [s["session_id"] for s in list_resp.get("sessions", [])]
        print(f"   Active sessions : {count}")
        assert session_id in ids, f"Session {session_id} not found in list: {ids}"
        print(f"   Session found   : yes")

    except Exception as e:
        print(f"\n   ERROR: {e}")
        _cleanup(session_id)
        sys.exit(1)

    # -------------------------------------------------------------- 7
    _cleanup(session_id)
    session_id = None

    print(f"\n{'='*60}")
    print("Test PASSED")
    print(f"{'='*60}\n")


def _cleanup(session_id: str | None) -> None:
    """Delete the session if one was created."""
    if session_id is None:
        return
    print(f"\n9. Closing session {session_id}...")
    try:
        close_resp = delete(f"/sessions/{session_id}")
        print(f"   Status : {close_resp.get('status')}")
    except Exception as e:
        print(f"   Warning: Could not close session: {e}")


if __name__ == "__main__":
    main()
