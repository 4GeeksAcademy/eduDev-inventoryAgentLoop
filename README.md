# Inventory API and CLI agent

[Español](README.es.md) · [Assignment source](https://github.com/4GeeksAcademy/ai-engineering-syllabus/blob/main/content/projects/ai-basic-inventory-agent-loop/README.md)

A minimal single-inventory FastAPI API backed by CSV, with a manual Groq tool-calling CLI. The original `main.py` and Flask example `server.py` are preserved
starter files, not the API entry point.

## Quick start

Install [uv](https://docs.astral.sh/uv/) and Python 3.11 or newer, then run from
the project root:

```bash
uv sync
# Create only if absent; never overwrite an existing .env:
if [ ! -e .env ]; then cp -n .env.example .env; fi
# Terminal 1: API first
uv run uvicorn api.app:app --reload
```

The four direct dependencies are `fastapi`, `uvicorn`, `openai`, and
`python-dotenv`. The agent uses the OpenAI SDK with Groq's compatible endpoint
`https://api.groq.com/openai/v1`, not an agent framework.

Optionally activate with `source .venv/bin/activate` in each terminal, then run
the assignment commands `uvicorn api.app:app --reload` and `python agent.py`.
A global `python` command is not required with `uv run`.
Open http://127.0.0.1:8000/docs for interactive API documentation.
Stop the agent first (`exit`, `quit`, Ctrl+C or EOF), then stop the API with
Ctrl+C. Relaunch API first and agent second; neither resets inventory or the log.
Run only one API process/worker against the file.

## CLI agent (second terminal)

Keep the API running. Edit the local `.env` created above and set your own
`GROQ_API_KEY`; never commit or share it. In terminal 2, from the project root:

```bash
uv run python agent.py
```

Configuration: `GROQ_MODEL` defaults to `llama-3.3-70b-versatile` and
`API_BASE_URL` to `http://127.0.0.1:8000`. Existing environment variables take
precedence over `.env`. Only the CLI entry point loads `.env`.

Try “Add Rice with 8 kg”, then immediately “Show alerts below 10”. Follow with
“A delivery added 5 kg of Rice”, then “Sell 4 kg of Rice”. Expected stock is
8 → 13 → 9 kg; alerts use strict `< 10`, so exactly 10 is not an alert.
All requests use one shared inventory, not separate branch inventories. The assistant should ask about ambiguous names
or missing units; it does not convert units or forecast demand. Type `exit` or
`quit`, or use Ctrl+C/EOF to leave. A final answer ends a turn, not the session.

The four tools are `get_inventory`, `add_product`, `change_stock`, and
`get_alerts`. Session context stays in memory until exit; a new session does not
reload previous conversation history from the audit log. Public user/agent messages, tool
requests and tool results append immediately to project-root
`conversation_log.csv` (`actor,message,tool_call,timestamp`); no private reasoning
is requested or logged. Logs are plaintext and can contain your inventory, conversation data, or secrets
you type; keep them private and do not paste credentials into the chat. The agent never reads the inventory CSV directly.

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

The bounded integration uses real local HTTP and mocked SDK responses, checks
history, CSV persistence after API restart, and log append across agent sessions:

```bash
uv run python -m unittest discover -s tests -p 'test_integration.py' -v
# Final local suite (no provider calls):
uv run python -m unittest discover -s tests -v
```

A separate real-Groq smoke test passed with `GROQ_MODEL=openai/gpt-oss-20b`
using 10 requests and isolated temporary data: creation, alerts, stock changes,
restart persistence, and log append. Set that model in your local `.env` if the
fallback `llama-3.3-70b-versatile` is unavailable; source defaults are unchanged.
This records one successful run, not a guarantee of model behavior.
Before submission, follow the assignment's repository/link and
demo requirements, and check that no credentials or private runtime CSVs are
included. Publishing is a separate manual step.

### Contributors

This template was built as part of the [4Geeks Python Resources](https://4geeks.com/technology/python) for learning at [4Geeks.com](https://4geeks.com) by [Alejandro Sanchez](https://twitter.com/alesanchezr) and [many other contributors](https://github.com/4GeeksAcademy/python-hello/graphs/contributors).
