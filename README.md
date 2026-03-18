# py-dss-service

**Stage 1 Prototype**: FastAPI + filesystem-based job queue for OpenDSS simulations.

A lightweight service for running OpenDSS power flow simulations via HTTP API. Submit DSS scripts, poll for status, and retrieve voltage results.

## Features (Stage 1)

- ✅ FastAPI REST API
- ✅ Filesystem-based job queue (no external dependencies)
- ✅ Separate worker process for DSS execution
- ✅ Script validation (blocks file I/O commands)
- ✅ Per-job logging
- ✅ Job timeout protection
- ✅ Cross-platform (Windows & Linux)

## Quick Start

### 1. Install Dependencies

```bash
# Create virtual environment (recommended)
python -m venv venv

# Activate (Windows)
venv\Scripts\activate

# Activate (Linux/macOS)
source venv/bin/activate

# Install package in development mode
pip install -e .
```

### 2. Start the API Server

Open a terminal and run:

```bash
python -m py_dss_service.api.main
```

You should see:
```
Starting py-dss-service API on 127.0.0.1:8000
Data directory: C:\path\to\py_dss_service\data
API docs: http://127.0.0.1:8000/docs
```

### 3. Start the Worker

Open a **second terminal**, activate the venv, and run:

```bash
python -m py_dss_service.worker.main
```

You should see:
```
Starting py-dss-service worker
Data directory: C:\path\to\py_dss_service\data
Poll interval: 1.0s
Job timeout: 300s
Press Ctrl+C to stop...
```

### 4. Submit a Job

Use curl, PowerShell, or any HTTP client:

**PowerShell (Windows):**
```powershell
$body = @{
    dss_script = @"
Clear
New Circuit.TestCkt basekv=12.47 pu=1.0 phases=3
New Line.Line1 Bus1=SourceBus Bus2=LoadBus Length=1 Units=km
New Load.Load1 Bus1=LoadBus kW=100 kvar=50
Set VoltageBases=[12.47]
CalcVoltageBases
"@
} | ConvertTo-Json

Invoke-RestMethod -Uri "http://127.0.0.1:8000/jobs" -Method Post -Body $body -ContentType "application/json"
```

**curl (Linux/macOS/Windows with curl):**
```bash
curl -X POST http://127.0.0.1:8000/jobs \
  -H "Content-Type: application/json" \
  -d '{
    "dss_script": "Clear\nNew Circuit.TestCkt basekv=12.47 pu=1.0 phases=3\nNew Line.Line1 Bus1=SourceBus Bus2=LoadBus Length=1 Units=km\nNew Load.Load1 Bus1=LoadBus kW=100 kvar=50\nSet VoltageBases=[12.47]\nCalcVoltageBases"
  }'
```

Response:
```json
{"job_id": "20260116-103045-a1b2c3d4", "status": "queued"}
```

### 5. Check Job Status

```bash
curl http://127.0.0.1:8000/jobs/{job_id}
```

Response:
```json
{"job_id": "20260116-103045-a1b2c3d4", "status": "done", "created_at": "2026-01-16T10:30:45+00:00"}
```

### 6. Get Results

```bash
curl http://127.0.0.1:8000/jobs/{job_id}/result
```

Response:
```json
{
  "job_id": "20260116-103045-a1b2c3d4",
  "status": "done",
  "result": {
    "job_id": "20260116-103045-a1b2c3d4",
    "converged": true,
    "bus_names": ["sourcebus", "loadbus"],
    "voltages_by_bus": {
      "sourcebus": [7199.558, 7199.558, 7199.558],
      "loadbus": [7185.123, 7185.456, 7185.789]
    },
    "raw_buses_vmag": [7199.558, 7199.558, 7199.558, 7185.123, 7185.456, 7185.789],
    "completed_at": "2026-01-16T10:30:46+00:00",
    "execution_time_seconds": 0.234,
    "log_file": "logs/20260116-103045-a1b2c3d4.log"
  }
}
```

## Sample DSS Script

Here's a minimal, self-contained DSS script (no file references):

```
Clear
New Circuit.IEEE13Node basekv=4.16 pu=1.0 phases=3

! Define a simple line
New Line.L1 Bus1=sourcebus Bus2=bus1 Length=0.5 Units=km r1=0.01 x1=0.02

! Add a load
New Load.Load1 Bus1=bus1 kW=500 kvar=200 kV=4.16

! Set voltage bases and calculate
Set VoltageBases=[4.16]
CalcVoltageBases
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/jobs` | POST | Submit a new job |
| `/jobs/{job_id}` | GET | Get job status |
| `/jobs/{job_id}/result` | GET | Get job results |
| `/docs` | GET | OpenAPI documentation |

## Configuration

Configure via environment variables (prefix: `PYDSS_`):

| Variable | Default | Description |
|----------|---------|-------------|
| `PYDSS_DATA_DIR` | `./data` | Root directory for job files |
| `PYDSS_API_HOST` | `127.0.0.1` | API bind address |
| `PYDSS_API_PORT` | `8000` | API port |
| `PYDSS_WORKER_POLL_INTERVAL` | `1.0` | Seconds between job polling |
| `PYDSS_WORKER_JOB_TIMEOUT` | `300` | Max seconds per job |
| `PYDSS_MAX_SCRIPT_LENGTH` | `204800` | Max script size (bytes) |
| `PYDSS_LOG_LEVEL` | `INFO` | Logging level |

Example:
```bash
set PYDSS_DATA_DIR=C:\pydss\data
set PYDSS_LOG_LEVEL=DEBUG
python -m py_dss_service.api.main
```

## Data Directory Structure

```
data/
├── jobs/
│   ├── pending/      # Jobs waiting to be processed
│   ├── running/      # Jobs currently being processed
│   ├── done/         # Completed jobs
│   └── failed/       # Failed jobs
├── results/          # Result JSON files
└── logs/             # Per-job log files
```

## Security

Scripts are validated to block potentially dangerous commands:
- `compile` - file loading
- `redirect` - file redirection
- `buscoords` - coordinate files
- `export` - data export
- `save` - file saving
- `open` - file opening

Scripts exceeding 200KB are rejected.

## Project Structure

```
src/py_dss_service/
├── __init__.py
├── settings.py          # Configuration
├── logging.py           # Logging setup
├── common/              # Shared utilities
│   ├── errors.py        # Custom exceptions
│   ├── ids.py           # Job ID generation
│   └── time.py          # Time utilities
├── schemas/             # Pydantic models
│   ├── job_spec.py      # Job submission
│   ├── results.py       # Result format
│   └── status.py        # Status types
├── engine/              # DSS execution
│   ├── runner.py        # DSS runner
│   └── validation.py    # Script validation
├── api/                 # FastAPI app
│   ├── main.py          # Entry point
│   └── routers/
│       ├── health.py    # Health endpoint
│       └── jobs.py      # Job endpoints
├── worker/              # Worker process
│   ├── main.py          # Entry point
│   └── tasks.py         # Job processing
├── queue/               # [Placeholder] Redis queue
├── db/                  # [Placeholder] PostgreSQL
└── storage/             # [Placeholder] S3/MinIO
```

## Future Stages

- **Stage 2**: Redis job queue + PostgreSQL job tracking
- **Stage 3**: S3/MinIO result storage + authentication
- **Stage 4**: Docker deployment + Kubernetes scaling

See placeholder module READMEs for migration plans.

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Lint
ruff check src/
```

## License

MIT

