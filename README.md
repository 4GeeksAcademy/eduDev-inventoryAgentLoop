# Inventory API

A minimal single-inventory FastAPI API backed by CSV. The CLI agent is not yet
implemented. The original `main.py` and Flask example `server.py` are preserved
starter files, not the API entry point.

## Quick start

Install [uv](https://docs.astral.sh/uv/) and Python 3.11 or newer, then run from
the project root:

```bash
uv sync
uv run uvicorn api.app:app --host 127.0.0.1 --port 8000
```

Alternatively, activate with `source .venv/bin/activate`, then use `python` and
`uvicorn` directly. A global `python` command is not required with `uv run`.
Open http://127.0.0.1:8000/docs for interactive API documentation.
Stop with Ctrl+C; restarting the same command retains stock.
Run only one API process/worker against the file.

## API

| Request | Input | Result |
| --- | --- | --- |
| `GET /inventory` | None | Product list (initially empty) |
| `POST /inventory` | `name`, `quantity`, `unit` | Created product, HTTP 201 |
| `PATCH /inventory/{product_id}` | Signed `delta` | Updated product |
| `GET /inventory/alerts?threshold=10` | Optional threshold, default 10 | Products strictly below threshold |

```bash
curl -X POST http://127.0.0.1:8000/inventory \
  -H 'Content-Type: application/json' \
  -d '{"name":"Rice","quantity":"12.5","unit":"kg"}'
curl -X PATCH http://127.0.0.1:8000/inventory/1 \
  -H 'Content-Type: application/json' -d '{"delta":"-3"}'
curl http://127.0.0.1:8000/inventory/alerts
```

Products contain integer `id`, trimmed `name` and `unit`, and decimal `quantity`.
Send quantities/deltas as JSON numbers or decimal strings; responses use decimal
strings to preserve precision. IDs are stable and new IDs increase from the
largest existing ID. Names need not be unique. Blank names/units, non-finite or
negative stock, invalid input, and changes below zero return HTTP 422. Unknown
product IDs return HTTP 404. Thresholds must be finite and nonnegative.

## Storage and tests

The API creates `products.csv` on the first successful write, with header
`id,name,quantity,unit`. Paths are anchored to the project root, not the shell's
working directory. Set `INVENTORY_CSV_PATH` before starting the process to use
another file (absolute paths are supported; relative paths use the project root).
Its parent directory must already exist. Malformed existing CSV returns HTTP 500
without overwriting it; repair the file manually. Writes use an in-process lock,
not cross-process locking or crash-safe transactions. Keep backups for valuable data.

```bash
uv run python -m unittest discover -s tests -p 'test_api.py' -v
```

Tests start disposable local HTTP servers and set absolute temporary CSV paths;
they never use your inventory or an LLM service. `.env`, `.venv`, bytecode,
`products.csv`, and `conversation_log.csv` are ignored by Git. No API credentials
are needed, and this API does not load `.env`. Never commit secrets.

### Contributors

This template was built as part of the [4Geeks Python Resources](https://4geeks.com/technology/python) for learning at [4Geeks.com](https://4geeks.com) by [Alejandro Sanchez](https://twitter.com/alesanchezr) and [many other contributors](https://github.com/4GeeksAcademy/python-hello/graphs/contributors).
