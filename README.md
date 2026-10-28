# Inventory API and CLI agent

A minimal single-inventory FastAPI API backed by CSV, with a manual Groq tool-calling CLI. The original `main.py` and Flask example `server.py` are preserved
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

## CLI agent (second terminal)

Keep the API running. Create a project-root `.env` using `.env.example` as a
reference and set your own `GROQ_API_KEY` locally; never commit it. Then run:

```bash
uv run python agent.py
```

Configuration: `GROQ_MODEL` defaults to `llama-3.3-70b-versatile` and
`API_BASE_URL` to `http://127.0.0.1:8000`. Existing environment variables take
precedence over `.env`. Only the CLI entry point loads `.env`.

Try “List my inventory”, “Create Rice with 12.5 kg”, “Remove 2 kg of Rice”,
and “Show products below 10”. The assistant should ask about ambiguous names
or missing units; it does not convert units or forecast demand. Type `exit` or
`quit`, or use Ctrl+C/EOF to leave. A final answer ends a turn, not the session.

Session context stays in memory until exit. Public user/agent messages, tool
requests and tool results append immediately to project-root
`conversation_log.csv` (`actor,message,tool_call,timestamp`); no private reasoning
is requested or logged. Logs can contain your inventory and conversation data;
keep them private. The agent never reads the inventory CSV directly.

API writes and provider requests are not automatically retried. If a request
times out, a write may already have applied: inspect inventory before retrying.
Provider failures let you continue or quit without replaying completed tools.
This is a single-user educational loop, not production infrastructure.

Focused agent tests use mocked SDK/HTTP calls and temporary logs, without keys,
`.env` reads or network requests:

```bash
uv run python -m unittest discover -s tests -p 'test_agent.py' -v
```

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
