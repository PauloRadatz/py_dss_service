# Scripts

Standalone test and utility scripts for `py-dss-service`.

Run all scripts from the **project root** (the directory containing `pyproject.toml`).

---

## `run_worker_test.py` — Worker direct test (no API needed)

Tests the worker end-to-end without starting any server.
Creates a job spec on the filesystem, claims it, processes it, and prints the result.

```
python scripts/run_worker_test.py
```

Optional: pass a custom DSS script file and/or actions JSON:

```
python scripts/run_worker_test.py path/to/script.dss '[{"type":"dss_command","command":"Set Maxiter=100"}]'
```

**Requires:** OpenDSS / `py-dss-interface` installed in the environment.

---

## `run_api_worker_test.py` — API + Worker end-to-end test

Submits a job through the REST API, polls until the job completes, then prints the result.

**Step 1** — Start the API server (Terminal 1):

```
python -m py_dss_service.api.main
```

**Step 2** — Start the worker (Terminal 2):

```
python -m py_dss_service.worker.main
```

**Step 3** — Run the script (Terminal 3):

```
python scripts/run_api_worker_test.py
```

Optional: pass a custom base URL:

```
python scripts/run_api_worker_test.py http://127.0.0.1:8000
```

The script exits with code `0` on success, `1` if the job fails or times out (default 60 s).

---

## `run_session_test.py` — Sessions API end-to-end test

Exercises the full session lifecycle: create → load circuit → solve → fetch results → close.

**Step 1** — Start the API server (Terminal 1):

```
python -m py_dss_service.api.main
```

**Step 2** — Run the script (Terminal 2, no worker needed):

```
python scripts/run_session_test.py
```

Optional: pass a custom base URL:

```
python scripts/run_session_test.py http://127.0.0.1:8000
```

The script cleans up the session automatically, even on failure.

---

## Quick reference

| Script | Needs API? | Needs Worker? | What it tests |
|---|---|---|---|
| `run_worker_test.py` | No | No | Worker task functions directly |
| `run_api_worker_test.py` | Yes | Yes | Full job submission → result flow |
| `run_session_test.py` | Yes | No | Session create / load / solve / results |
