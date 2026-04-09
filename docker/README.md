## Running with Docker Compose

The project ships a multi‑stage Dockerfile that can build five distinct images that create four services:

* `api` – the py_dss FastAPI server
* `worker` – the py_dss job handler
* `dev` – an image with dev packages
* `test` – runs test cases
* `lint` – runs ruff check and format

The **docker‑compose.yml** file orchestrates the four services.  To start the API and worker containers, simply run:

```bash
docker compose up

# use "docker compose up --build" to force docker to rebuild the containers.
```

If you want to run the automated test suite with the normal services use the `test` profile:

```bash
COMPOSE_PROFILES=test docker compose up --build
```

The `data` directory is exported as a volume and is shared between the api and worker. This allows files to persist between runs.
