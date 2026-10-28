# Inventory Agent Loop

## Goal and scope
Implement the 4Geeks AI Engineering assignment with a single inventory, a CSV-backed FastAPI API, and a manual Python CLI tool-calling agent. No agent frameworks, frontend, database, branch-specific stock, demand forecasts, or additional direct dependencies beyond fastapi, uvicorn, openai, and python-dotenv. Use Python standard-library unittest and HTTP utilities.

## Authorization and constraints
User authorized implementation after approving the single-inventory scope. Keep code educational and minimal. Ask before unresolved product choices. Run focused checks per task; one short integrated verification at the end if useful. Do not read or expose secrets. Session standing permission now authorizes ordinary local work-unit commits; do not push or create a PR for this task. Branch: feat/inventory-agent-loop. Record local work-unit commits below.

## Tasks
- [x] T1 (done): Build the CSV-backed inventory API and dependency setup, with focused endpoint/persistence tests and API usage documentation.
- [x] T2 (done): Build the CLI agent, typed tools, manual loop, session history, and append-only event log, with focused mocked tests.
- [x] T3 (done): Finish concise English/Spanish setup documentation and run a bounded integration/persistence check; report credential-dependent checks honestly.

- [ ] T4 (in_progress; awaiting user configuration): Perform one bounded real-Groq smoke test after the user configures project-local GROQ_API_KEY; never print or commit credentials.

## Acceptance and checks
T1: GET/POST /inventory, PATCH /inventory/{product_id} with signed delta, GET /inventory/alerts with configurable threshold default 10 and strict less-than; descriptive errors, stable IDs, nonnegative finite quantities, CSV survives app restart. Use unittest with temporary storage and HTTP against a disposable local server; no external services.
T2: Four typed tools invoke HTTP API, all requested calls and results enter history before next LLM request, final reply ends a turn not the CLI, session history persists in memory, all user/agent/tool events append to actor,message,tool_call,timestamp CSV. Mock LLM for deterministic checks; include multi-step interaction and API/LLM failures.
T3: Setup uses uv and documented environment activation (python command is absent globally but python3 3.14.4 and uv 0.13.6 exist). Two terminal startup, shutdown/relaunch, .env safety, examples, and scoped test commands. One small integrated scenario demonstrates real local HTTP + mocked tool-selecting LLM, persistence after restart and append across agent sessions. Real Groq run requires user key and is pending unless safely configured by user.

## Evidence and progress
- Read entire upstream assignment README. Local baseline is the python-hello starter; server.py is a Flask example and will not be used.
- Initial git worktree was clean; feature branch created before implementation.
- Native review switch is on; use provider inspect/consent before reporting source implementation complete. Review does not authorize commits.
- T1 writer observed RED (missing api), then GREEN 5/5 tests. Independent verifier reran `uv run python -m unittest discover -s tests -p 'test_api.py' -v`: 5/5 PASS (2.547s). `uv sync` and `git diff --check` passed.
- T1 native review review-a685e608a1b5ddaa approved and acknowledgement burned successfully. Non-blocking advisories: CSV field-size limit and extreme decimal exponents; no correction required.
- T1 commit: 881a626567429d7243a4affd53b64cf66a5eb7f2 (feat(api): add CSV-backed inventory endpoints). Generated uv.lock accounts for 504 lines.
- T1 API serializes Decimal quantities as JSON strings; test isolation uses INVENTORY_CSV_PATH. Single-process/non-crash-atomic storage is documented.
- Groq official docs confirm OpenAI SDK base URL https://api.groq.com/openai/v1 and llama-3.3-70b-versatile tool support. Do not include name on tool-result messages (compatibility restriction).
- T2 initial writer run: RED missing agent, then GREEN 7/7 mocked tests; intermediate test-only import issue corrected. Parent readback found tool_call CSV values used call IDs instead of required tool names. Regression correction observed RED (IDs instead of names), then GREEN 7/7 tests (0.030s). Model-history IDs preserved; CSV now uses tool names.
- T2 native review review-8aa9191b7c6873c7 approved and acknowledged; one informational advisory at agent.py:81-82. Initial consent expired without lineage creation, fresh consent succeeded. ASSESS failed to assess untracked files and requested independent verification; independent verifier confirmed 7/7 tests PASS (0.019s), no rubric blockers. Parent `git diff --check` and staged whitespace check passed. No real LLM call performed.
- T2 commit: 53afeb6a276299008eaddd01e6c47f0e50dc6af8 (feat(agent): add manual tool loop and conversation logging).

- T3 writer: bilingual docs and isolated real-HTTP/mocked-SDK integration test completed. Focused integration PASS 1/1 (0.863s); no meaningful RED for documentation/coverage of existing behavior. Parent corrected assignment source URL in both READMEs.
- Final verifier mvrjz1qb-8-ceg5 ran `uv run python -m unittest discover -s tests -v` exactly once: 13/13 PASS in 3.605s (5 API, 7 agent, 1 integration); `git diff --check` passed. No concrete rubric gaps. No real model capability was tested.
- T3 initial consent expired without creating lineage or mutating source. On user resumption, fresh review review-17b7c7959f84ae69 approved and acknowledgement burned successfully with no findings.
- T3 commit: 4bbeee008d31e82beb52351a44efd4d01ffca40f (test(inventory): cover integrated workflow and document setup).
- User requested locating an existing provider key and instructions, not copying it. Bounded redacted scan found a nonempty GROQ_API_KEY candidate in /srv/workspaces/4geeks/eduDev-voice-command-api/.env. Current project .env is absent. Key validity unverified; no values shown, saved, copied, or used. Groq is not xAI/Grok.

## Next step
User should create project-root .env from .env.example and set GROQ_API_KEY locally, then notify the parent. Run one isolated real-provider integration smoke test using synthetic inventory and a temporary log; no full-suite rerun unless behavior changes. Report real model/provider outcome honestly. No push or PR performed.
