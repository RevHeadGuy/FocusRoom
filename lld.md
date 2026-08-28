# Low Level Design (LLD) — Productivity Agent

---



## Table of Contents

1. [System Architecture](#1-system-architecture)
2. [Module Breakdown](#2-module-breakdown)
3. [Streamlit Frontend](#3-streamlit-frontend)
4. [Database Schema](#4-database-schema)
5. [MCP Server and Transport Layer](#5-mcp-server-and-transport-layer)
6. [Supervisor Orchestration](#6-supervisor-orchestration)
7. [Telemetry System](#7-telemetry-system)
8. [Reminder and Email Architecture](#8-reminder-and-email-architecture)
9. [Key Data Flows](#9-key-data-flows)
10. [Configuration and Environment Variables](#10-configuration-and-environment-variables)
11. [Known Edge Cases](#11-known-edge-cases)

---

## 1. System Architecture

The system is composed of four independently runnable processes sharing a single SQLite database (`productivity.db`).

```
┌────────────────────────────────────────────────────────────────┐
│  Streamlit Frontend  (streamlit_app.py)                        │
│  Direct Python import — no HTTP between frontend and agents    │
└─────────────────────────────┬──────────────────────────────────┘
                              │ Python function calls
┌─────────────────────────────▼──────────────────────────────────┐
│  ProductivityOrchestrator (agent.py)                           │
│  ProductivitySupervisor   (orchestrator.py)                    │
│  TaskAgent / MemoryAgent / PlanningAgent                       │
└─────────────────────────────┬──────────────────────────────────┘
                              │
               ┌──────────────▼──────────────┐
               │  Database (database.py)      │
               │  SQLite — WAL mode           │
               └─────────────────────────────┘

┌────────────────────────────────────────────────────────────────┐
│  MCP Server  (orchestrator/mcp_server.py)                      │
│  Starlette ASGI — Streamable HTTP at /mcp                      │
│  10 tools; used by Kiro, Claude Desktop, or any MCP client     │
└────────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────┐
│  Reminder Worker  (reminder_worker.py)                         │
│  Independent process; polls DB every 60 s                      │
│  ReminderAgent → EmailService → SMTP                           │
└────────────────────────────────────────────────────────────────┘
```

### Key architectural decisions

| Decision | Rationale |
|---|---|
| Frontend imports agents directly (no HTTP) | Eliminates latency and serialisation overhead for the Streamlit path |
| MCP server as optional external interface | Allows IDE plugins and AI clients to call the same agent code |
| Single SQLite file, WAL mode | One writer + many concurrent readers without blocking; zero infrastructure |
| Two-tier deterministic + LLM router | Frequent, well-known requests never spend tokens on routing |
| `contextvars` for execution ID | Each thread in the parallel worker pool gets an isolated copy of execution context |

---

## 2. Module Breakdown

### `agent.py` — `ProductivityOrchestrator`

Central domain object. All CRUD operations and LLM calls live here.

**Constructor:** Connects to `Database`, initialises the Groq client from `GROQ_API_KEY`, reads model name from `GROQ_MODEL` (default `openai/gpt-oss-120b`).

| Method | Responsibility |
|---|---|
| `call_llm(messages, operation, max_tokens)` | Calls Groq chat completions, records token usage + LLM execution event, returns message content string |
| `clean_json(text)` | Strips markdown code fences, extracts first `{…}` JSON block |
| `create_task(title, …)` | Validates priority enum, computes `next_id = max(existing)+1`, persists, returns DB record |
| `list_tasks(status)` | Delegates to `db.get_tasks(status)` |
| `get_task(task_id)` | Single-record lookup |
| `update_task(task_id, **updates)` | Allow-list fields; validate priority/status enums; delegates to `db.update_task` |
| `complete_task(task_id)` | Sets `status="completed"`, writes `completed_at`, re-saves |
| `delete_task(task_id)` | Guard-checks existence, calls `db.delete_task` |
| `save_memory(key, value, category)` | Builds memory dict with `updated_at`; upserts via `db.save_memory` |
| `search_memory(query)` | Delegates to `db.search_memory` |
| `get_memories()` | Returns all memories newest-first |
| `find_overdue_tasks()` | Non-completed tasks where `due_date < today`; parses ISO then `%Y-%m-%d` fallback |
| `find_high_priority_tasks()` | Active tasks where `priority in {high, critical}` |
| `create_daily_plan()` | Returns `{date, tasks (active), memories}` — zero LLM tokens |
| `productivity_report()` | Aggregates all telemetry: task counts, token usage, MCP transport, agent execution status, execution traces |

**Singleton pattern:** `get_agent()` returns a module-level `_agent` instance. One object is shared across all callers in the same process.

---

### `database.py` — `Database`

Thin SQLite wrapper. Every method opens a short-lived `sqlite3.connect(timeout=10)` connection with WAL mode and `synchronous=NORMAL`.

Responsibilities:
- Schema creation (`CREATE TABLE IF NOT EXISTS`)
- Safe field allow-listing in `update_task`
- Schema migrations via `ALTER TABLE` for added columns
- LIKE-based fuzzy memory search across `key`, `value`, `category`
- All telemetry reads and writes

Full schema — see [Section 4](#4-database-schema).

---

### `orchestrator.py` — `ProductivitySupervisor`

Multi-agent coordinator. Owns instances of `TaskAgent`, `MemoryAgent`, and `PlanningAgent`.

See [Section 6](#6-supervisor-orchestration) for the full execution model.

---

### `task_agent.py` — `TaskAgent`

Thin action dispatcher. All logic delegates to `get_agent()`.

| Action | Delegates to |
|---|---|
| `create` | `agent.create_task(…)` |
| `list` | `agent.list_tasks(status)` |
| `complete` | `agent.complete_task(task_id)` |
| `update` | `agent.update_task(task_id, **updates)` |
| `delete` | `agent.delete_task(task_id)` |
| `overdue` | `agent.find_overdue_tasks()` |
| `high_priority` | `agent.find_high_priority_tasks()` |

An `aliases` dict normalises LLM-generated action names (e.g. `"add task" → "create"`). Telemetry event recording is skipped when a supervisor-provided `execution_id` is already active, to avoid duplicate events.

---

### `memory_agent.py` — `MemoryAgent`

Same dispatch pattern as `TaskAgent`. Two actions:
- `save` → `agent.save_memory(key, value, category)`
- `search` → `agent.search_memory(query)`

An alias dict covers natural-language variants (`"remember"`, `"recall"`, `"store"`, etc.). Same telemetry dedup guard.

---

### `planning_agent.py` — `PlanningAgent`

The most complex sub-agent. Entry point: `handle(action, arguments)`.

#### `collaborative_daily_plan(arguments)` execution steps

1. Accepts pre-fetched `task_context` and `memory_context` compact JSON strings from the supervisor, **or** fetches them directly when running standalone.
2. `_filter_tasks()`: keeps active tasks due within 14 days, sorted by priority then due date, capped at 15.
3. `_filter_memories()`: takes top 5 entries (DB returns newest-first).
4. `_encode_tasks()`: compact `!! Title (mm-dd)` format. `_encode_memories()`: values only, capped at 80 chars each.
5. Builds a minimal single-turn prompt. Calls LLM with `max_tokens=400`.
6. Derives `source_agents` from `execution_events` in DB (falls back to inferring from which context keys were present).
7. Returns `{"plan": <LLM text>, "source_agents": […]}`.

**Token optimisation constants:**

| Constant | Value |
|---|---|
| `_MAX_TASKS` | 15 |
| `_MAX_MEMORIES` | 5 |
| `_TASK_DUE_WINDOW` | 14 days |
| `_PLAN_MAX_TOKENS` | 400 |

---

### `telemetry.py`

Context-variable-based execution tracking using `contextvars.ContextVar`.

Each thread in the parallel worker pool gets its own copy of `_current_execution_id` via `contextvars.copy_context().run(…)`, preventing `"cannot enter context: already entered"` errors.

| Function | Behaviour |
|---|---|
| `start_execution()` | Generates `uuid4`, sets ContextVar, returns the ID |
| `get_execution_id()` | Reads ContextVar (returns `None` if not set) |
| `set_execution_id(id)` | Used by supervisor to propagate an externally-created ID |
| `record_event(db, type, name, details)` | Reads current ID; inserts into `execution_events`; no-ops if no ID |
| `finish_execution()` | Resets ContextVar to `None` |

---

### `mcp_transport.py`

In-process MCP transport recorder. Fills the gap where `TransportMetricsMiddleware` (HTTP-level middleware in `mcp_server.py`) does not fire during direct supervisor calls.

```
record_mcp_call(db, tool, arguments, result, execution_id)
  → request_bytes  = len(JSON({tool, arguments}).encode("utf-8"))
  → response_bytes = len(JSON(result).encode("utf-8"))
  → db.save_mcp_transport({execution_id, method="TOOL", path="/mcp/tools/<tool>", …})
```

Never raises — exceptions are printed to stderr so the calling worker always returns its result.

---

### `email_service.py` — `EmailService`

Active email sender used by the reminder pipeline. Uses `EMAIL_SENDER`, `EMAIL_PASSWORD`, `EMAIL_RECIPIENT`, `EMAIL_SMTP_SERVER`, `EMAIL_SMTP_PORT`. Raises `ValueError` on misconfiguration. Returns `True` on successful send.

### `email_agent.py` — `EmailAgent`

Legacy email sender with different env var names (`EMAIL_ADDRESS`, `REMINDER_EMAIL`, `SMTP_HOST`). Not used by the active reminder pipeline. Kept for backwards compatibility.

---

### `reminder_agent.py` — `ReminderAgent`

Pure business logic; no email, no LLM.

- `get_upcoming_tasks(hours=24)`: fetches all tasks, filters to non-completed with `due_date` in `[now, now+hours]`.
- `get_reminder_type(hours_left)`: returns `"15"` / `"1"` / `"24"` / `None` based on thresholds.
- `generate_reminders(hours=24)`: for each upcoming task, determines reminder type, checks `db.reminder_was_sent(task_id, type)`, builds reminder dict with `task_id`, `title`, `priority`, `due_date`, `hours_left`, `reminder_type`, `message`.

---

## 3. Streamlit Frontend

### Application structure

Single `main()` function drives everything. Sidebar radio button (`view`) controls which panel renders.

**Cached services** (`@st.cache_resource`): `get_agent()` and `ProductivitySupervisor()` are created once per Streamlit server process and shared across all sessions and reruns.

### Views

| View | What it does |
|---|---|
| **Overview** | `render_metrics(report)` — 4-column stat cards; `render_telemetry(report)` — 4-panel telemetry dashboard; `render_telemetry_detail(report)` — collapsible raw event data; active task list (first 5); "Today at a glance" plan card + completion progress bar |
| **Tasks** | Expander form: title, description, priority selectbox, date + time pickers, project field. Filter selectbox + full paginated task list. |
| **Plan** | Calls `agent.create_daily_plan()` (zero LLM tokens). Renders task list + full `report` JSON. |
| **Memory** | Form to `agent.save_memory(…)`. Search input toggles between `agent.search_memory(query)` and `agent.get_memories()`. |
| **Assistant** | Free-text prompt → `supervisor.run(prompt)`. Extracts `result["plan"]` if present, else `st.write(result)`. Re-fetches report and re-renders telemetry panels inline. |

### Key rendering functions

**`render_task(task, agent)`** — HTML card with priority colour class (`.priority-critical/high/medium/low`), status pill, due date label. "Complete" button calls `agent.complete_task(task_id)` then `st.rerun()`.

**`render_metrics(report)`** — 4-column layout: Active tasks, Completed, High priority, Completion rate.

**`render_telemetry(report)`** — 2-column layout:

| Left column | Right column |
|---|---|
| AI USAGE: token table by operation, totals row, avg/exec row | MCP: tool call counts, lifetime transport bytes, current-execution bytes |
| AGENT EXECUTION: tick/cross for supervisor, TASK_AGENT, MEMORY_AGENT, PLANNING_AGENT | EXECUTION TRACE: ordered steps from `recent_executions[0]` |

**`render_telemetry_detail(report)`** — `st.expander` containing `st.dataframe` of per-execution token breakdown and nested `st.expander` per event with `st.json(details)`.

### Data flow

```
main()
  → agent.productivity_report()          # on every load/rerun
  → sidebar radio selection
  → view-specific agent.* or supervisor.run() calls
  → st.rerun() on any mutation
```

---

## 4. Database Schema

File: `productivity.db` (SQLite, WAL mode, `synchronous=NORMAL`)

No foreign-key constraints. Relationships are enforced via `execution_id` string matching in application code.

### `tasks`

| Column | Type | Notes |
|---|---|---|
| `id` | INTEGER PRIMARY KEY | Manual: `max(existing)+1` in `agent.create_task` |
| `title` | TEXT NOT NULL | |
| `description` | TEXT | nullable |
| `priority` | TEXT NOT NULL | `low / medium / high / critical` |
| `status` | TEXT NOT NULL | `todo / in_progress / completed` |
| `due_date` | TEXT | ISO 8601 datetime string |
| `project` | TEXT | nullable |
| `created_at` | TEXT NOT NULL | ISO 8601 |
| `completed_at` | TEXT | nullable |
| `reminder_24_sent` | INTEGER DEFAULT 0 | boolean flag |
| `reminder_1_sent` | INTEGER DEFAULT 0 | boolean flag |
| `reminder_15_sent` | INTEGER DEFAULT 0 | boolean flag |

Persisted via `INSERT OR REPLACE`. The three `reminder_*_sent` columns are added via `ALTER TABLE` migration if absent.

### `memories`

| Column | Type | Notes |
|---|---|---|
| `key` | TEXT PRIMARY KEY | Upsert key |
| `value` | TEXT NOT NULL | |
| `category` | TEXT NOT NULL | e.g. `general` |
| `updated_at` | TEXT NOT NULL | ISO 8601 |

Persisted via `INSERT OR REPLACE`. Searched with `LOWER(col) LIKE ?` across all three columns.

### `token_usage`

| Column | Type | Notes |
|---|---|---|
| `id` | INTEGER PRIMARY KEY AUTOINCREMENT | |
| `operation` | TEXT NOT NULL | e.g. `supervisor_decision`, `planning_request` |
| `model` | TEXT NOT NULL | |
| `prompt_tokens` | INTEGER | |
| `completion_tokens` | INTEGER | |
| `total_tokens` | INTEGER | |
| `created_at` | TEXT NOT NULL | ISO 8601 — join key to `execution_events` |

### `mcp_transport`

| Column | Type | Notes |
|---|---|---|
| `id` | INTEGER PRIMARY KEY AUTOINCREMENT | |
| `execution_id` | TEXT | nullable; added via migration |
| `method` | TEXT NOT NULL | `GET/POST` (HTTP) or `TOOL` (in-process) |
| `path` | TEXT NOT NULL | URL path or `/mcp/tools/<name>` |
| `request_bytes` | INTEGER DEFAULT 0 | |
| `response_bytes` | INTEGER DEFAULT 0 | |
| `status_code` | INTEGER NOT NULL | |
| `created_at` | TEXT NOT NULL | ISO 8601 |

HTTP path writes in two steps (start → update with response bytes). In-process path writes in one step via `record_mcp_call`.

### `execution_events`

| Column | Type | Notes |
|---|---|---|
| `id` | INTEGER PRIMARY KEY AUTOINCREMENT | |
| `execution_id` | TEXT NOT NULL | UUID from `telemetry.start_execution()` |
| `event_type` | TEXT NOT NULL | `MCP Tool / MCP / Agent / LLM / Result` |
| `name` | TEXT NOT NULL | e.g. `TASK_AGENT`, `list_tasks`, `supervisor` |
| `details` | TEXT NOT NULL DEFAULT `'{}'` | JSON blob |
| `created_at` | TEXT NOT NULL | ISO 8601 |

This table is the **authoritative source** for MCP call counts. `get_mcp_tool_call_counts()` reads tool counts from here, not from `mcp_transport` row counts.

---

## 5. MCP Server and Transport Layer

### `mcp_server.py`

Built on `mcp==2.0.0` Python SDK. Server object: `MCPServer("Productivity Orchestrator")`. Tools registered with `@mcp.tool()`.

**App factory `create_app(api_key)`:**

1. `mcp.streamable_http_app(host="127.0.0.1")` — Starlette ASGI app at `/mcp`
2. Wraps with `TransportMetricsMiddleware` (outermost)
3. Wraps with `APIKeyMiddleware` if `MCP_API_KEY` is set

**`APIKeyMiddleware`** — `BaseHTTPMiddleware`. Reads `Authorization: Bearer <key>`. Uses `hmac.compare_digest` for timing-safe comparison. Returns `401 + WWW-Authenticate: Bearer` on failure.

**`TransportMetricsMiddleware`** — Raw ASGI middleware (not `BaseHTTPMiddleware`; implements `__call__(scope, receive, send)` directly):

```
http.request      → accumulate request_bytes
http.response.start → record status_code; db.start_mcp_transport(…) → transport_id
http.response.body  → accumulate response_bytes; db.update_mcp_transport(transport_id, …)
```

Skips non-HTTP scopes.

**`trace_mcp_tool` decorator** — wraps each tool (except `productivity_assistant`):
```
start_execution() → execution_id
record_event("MCP Tool", tool_name, {arguments})
  → call tool
record_event("Result", "mcp_result", {result})
finish_execution()  ← always in finally
```

### The 10 MCP tools

| Tool | Validation | Delegates to |
|---|---|---|
| `productivity_assistant(request)` | Non-empty | `supervisor.run(request, execution_id=…)` |
| `create_task(title, priority, …)` | Priority enum, title non-empty | `agent.create_task(…)` |
| `list_tasks(status)` | — | `agent.list_tasks(status)` |
| `update_task(task_id, …)` | At least one field, priority re-checked | `agent.update_task(…)` |
| `complete_task(task_id)` | — | `agent.complete_task(…)` |
| `delete_task(task_id)` | — | `agent.delete_task(…)` |
| `save_memory(key, value, category)` | key/value non-empty | `agent.save_memory(…)` |
| `search_memory(query)` | Non-empty | `agent.search_memory(…)` |
| `daily_plan()` | — | `agent.create_daily_plan()` |
| `productivity_report()` | — | `agent.productivity_report()` |

**Result serialisation helpers:**
- `success_result(data)` → `{"success": True, "data": …, "error": None}`
- `error_result(msg)` → `{"success": False, "data": None, "error": …}`
- `operation_result(result, data_key)` — inspects raw agent result for existing error signals before wrapping

**Startup guard:** `__main__` raises `RuntimeError` if `MCP_HOST` is non-localhost and `MCP_API_KEY` is unset.

---

## 6. Supervisor Orchestration

### Two-tier routing

**Tier 1 — Deterministic router (`_route_deterministically`)** — runs first, zero LLM tokens:

| Phrase list | Produces |
|---|---|
| `_DAILY_PLAN_PHRASES` | `[TASK_AGENT:list, MEMORY_AGENT:search, PLANNING_AGENT:daily]` |
| `_TASK_ONLY_PHRASES` | `[TASK_AGENT:list]` (with optional `status` argument) |
| `_OVERDUE_PHRASES` | `[TASK_AGENT:overdue]` |
| `_HIGH_PRIORITY_PHRASES` | `[TASK_AGENT:high_priority]` |
| `_REPORT_PHRASES` | `[PLANNING_AGENT:report]` |

Returns `None` if no phrase matches → falls through to Tier 2.

**Tier 2 — LLM router (`decide_agent`)** — constrained system prompt requesting JSON schema `{"actions": [{agent, action, arguments}]}`. Output passes through:
1. `clean_json` — strip markdown fences
2. `parse_decisions` — validate structure
3. `normalize_decision` — apply action aliases; validate agent/action against allowed sets

### Execution flow in `run(user_message, execution_id)`

```
1. Route (deterministic → LLM fallback)
2. record_event("Agent", "supervisor", {request, resolved_actions})

3. Partition decisions into task_decisions and memory_decisions

4. ThreadPoolExecutor(max_workers=2):
     task_ctx.run(_run_task, decision)     ─┐ parallel
     memory_ctx.run(_run_memory, decision) ─┘

5. For each PLANNING_AGENT decision (sequential, waits for 4):
     Build task_context_str  = compact JSON | error string
     Build memory_context_str = compact JSON | error string
     planning_agent.handle("daily" | "weekly" | "report", arguments)

6. Final result priority: planning_result > memory_result > task_result
```

**Context propagation:** `contextvars.copy_context()` is called per parallel worker. Each thread gets its own isolated `_current_execution_id` copy — avoids "cannot enter context: already entered" when the thread pool reuses threads.

**Events inside parallel workers (`_run_task` / `_run_memory`):**

```
record_event("Agent", "TASK_AGENT" | "MEMORY_AGENT", …)
record_event("MCP", <canonical_tool_name>, {arguments})
agent.handle(action, arguments)
record_mcp_call(db, tool, args, result, execution_id)
record_event("Result", "<agent>_result", {result})
```

**Execution ID lifetime:** Created by `mcp_server.productivity_assistant` and passed into `supervisor.run()`. If called without an ID (e.g. from Streamlit), `run()` creates one itself (`owns_execution=True`) and calls `finish_execution()` in its own `finally`.

---

## 7. Telemetry System

Three subsystems all writing to the same SQLite database.

### Token usage

`agent.call_llm` always writes to `token_usage` via `db.save_token_usage`. When an `execution_id` is active, it also fires `record_event("LLM", operation, usage_details)` into `execution_events`.

`db.get_token_usage_for_execution(execution_id)` joins the two tables using a ±2-second `created_at` timestamp window, matched by `operation` name. This is the join strategy — not a foreign key.

### MCP transport

Two write paths:

| Path | Trigger | How bytes are measured | Write strategy |
|---|---|---|---|
| HTTP | `TransportMetricsMiddleware` | Raw ASGI body bytes | Two-step: `start_mcp_transport` → `update_mcp_transport` |
| In-process | `record_mcp_call` | `len(JSON(payload).encode("utf-8"))` | Single-step: `save_mcp_transport` |

**Authoritative call count** comes from `execution_events WHERE event_type='MCP'`, not from `mcp_transport` row count. This is because transport rows may be missing for historical executions or if a concurrent write fails. The count reported on the dashboard is `total_calls` (from events), while bytes come from `mcp_transport`.

### Execution events

All significant steps write to `execution_events` via `record_event`.

| `event_type` | `name` examples | Who writes it |
|---|---|---|
| `MCP Tool` | `create_task`, `list_tasks` | `trace_mcp_tool` decorator in `mcp_server.py` |
| `Agent` | `supervisor`, `TASK_AGENT`, `MEMORY_AGENT` | `supervisor.run`, `_run_task`, `_run_memory` |
| `MCP` | `list_tasks`, `search_memory` | `_run_task`, `_run_memory`, planning loop |
| `LLM` | `supervisor_decision`, `planning_request` | `agent.call_llm` |
| `Result` | `mcp_result`, `task_agent_result` | Various layers |

**Dedup guard in agents:** `TaskAgent.handle` and `MemoryAgent.handle` skip their own `"Agent"` event when `get_execution_id()` is already set (supervisor already wrote it).

---

## 8. Reminder and Email Architecture

### Pipeline

```
ReminderAgent.generate_reminders(hours=24)
  ↓  list of reminder dicts
reminder_worker.run_reminder_check()
  ↓  for each reminder
EmailService.send_email(subject, body)
  ↓  SMTP STARTTLS
db.mark_reminder_sent(task_id, reminder_type)
```

### Deduplication — two layers

| Layer | Mechanism | Scope |
|---|---|---|
| Database (authoritative) | `reminder_was_sent(task_id, type)` checks `reminder_*_sent` column; `mark_reminder_sent` sets it to 1 | Persists across restarts |
| In-memory (cache) | `self.sent_reminders: set` in `orchestrator/reminder_service.py` | Resets on process restart; only a fast-path guard |

### Reminder stages

| Stage | Threshold | DB column |
|---|---|---|
| 24-hour | `0.25 h < hours_left ≤ 24 h` | `reminder_24_sent` |
| 1-hour | `0.25 h < hours_left ≤ 1 h` | `reminder_1_sent` |
| 15-minute | `hours_left ≤ 0.25 h` | `reminder_15_sent` |

### Polling intervals

| Process | Interval | Look-ahead window |
|---|---|---|
| `reminder_worker.py` | 60 seconds | 24 hours |
| `orchestrator/reminder_service.py` | 5 minutes (configurable) | 24 hours |
| `reminder_service.py` (root-level, legacy) | 30 minutes | 24 hours |

---

## 9. Key Data Flows

### A. User request via Assistant view (Streamlit)

```
streamlit_app.py
  → supervisor.run(prompt)

  supervisor:
    _route_deterministically(prompt)
      → [TASK_AGENT:list, MEMORY_AGENT:search, PLANNING_AGENT:daily]  # deterministic match
      # OR
    decide_agent(prompt)
      → call_llm([system, user])  →  db.save_token_usage
      →                           →  record_event("LLM", "supervisor_decision")

    record_event("Agent", "supervisor", {actions})

    ThreadPoolExecutor(max_workers=2):
      ┌─ copy_context().run(_run_task, decision)
      │     record_event("Agent", "TASK_AGENT")
      │     record_event("MCP", "list_tasks")
      │     task_agent.handle("list", {})
      │       → agent.list_tasks() → db.get_tasks()
      │     record_mcp_call(db, "list_tasks", {}, result, execution_id)
      │     record_event("Result", "task_agent_result", result)
      │
      └─ copy_context().run(_run_memory, decision)  ← parallel
            record_event("Agent", "MEMORY_AGENT")
            record_event("MCP", "search_memory")
            memory_agent.handle("search", {"query": …})
              → agent.search_memory(…) → db.search_memory(…)
            record_mcp_call(db, "search_memory", …)
            record_event("Result", "memory_agent_result", result)

    planning_agent.handle("daily", {task_context, memory_context})
      → _filter_tasks / _encode_tasks  (compact format)
      → _filter_memories / _encode_memories  (top 5, 80 chars)
      → call_llm([user: compact_prompt], max_tokens=400)
          → db.save_token_usage
      → return {"plan": "…", "source_agents": […]}

    record_event("Result", "agent_result", {result})

  ← {"plan": "MORNING FOCUS …", "source_agents": ["TASK_AGENT", "MEMORY_AGENT", "PLANNING_AGENT"]}

streamlit_app.py:
  → st.markdown(result["plan"])
  → agent.productivity_report()   # reload telemetry
  → render_telemetry(updated_report)
```

### B. MCP tool call via HTTP client

```
HTTP POST /mcp  (Authorization: Bearer <key>)
  → APIKeyMiddleware: hmac.compare_digest  →  401 on failure
  → TransportMetricsMiddleware:
      http.request body          → request_bytes
      http.response.start        → db.start_mcp_transport(…) → transport_id
  → mcp_server.create_task(…)
      trace_mcp_tool:
        start_execution()        → execution_id
        record_event("MCP Tool", "create_task", {arguments})
        agent.create_task(…)
          → db.get_tasks()       → next_id
          → db.save_task(task)
          → db.get_task(next_id)
        record_event("Result", "mcp_result", {result})
        finish_execution()
  → TransportMetricsMiddleware:
      http.response.body         → db.update_mcp_transport(transport_id, response_bytes)
  ← {"success": true, "data": {"task": {…}}, "error": null}
```

### C. Reminder check cycle

```
reminder_worker.main()   →  loop every 60 s
  → run_reminder_check()
      → ReminderAgent.generate_reminders(hours=24)
          → db.get_tasks()
          → filter to [now, now+24h]
          → for each: get_reminder_type(hours_left)
          → db.reminder_was_sent(task_id, type)  →  skip if true
          → build reminder dict
      → for each reminder:
          → EmailService.send_email(subject, body)
              → smtplib.SMTP(smtp_server, 587)
              → STARTTLS + login
              → send_message
          → db.mark_reminder_sent(task_id, reminder_type)
```

---

## 10. Configuration and Environment Variables

| Variable | Used by | Required | Default | Purpose |
|---|---|---|---|---|
| `GROQ_API_KEY` | `agent.py` | Yes | — | Groq API authentication |
| `GROQ_MODEL` | `agent.py` | No | `openai/gpt-oss-120b` | LLM model name; shown in sidebar |
| `MCP_PORT` | `mcp_server.py` | No | `8000` | HTTP listen port |
| `MCP_HOST` | `mcp_server.py` | No | `127.0.0.1` | HTTP listen host |
| `MCP_API_KEY` | `mcp_server.py` | No* | — | Bearer token; required if `MCP_HOST` is non-local |
| `EMAIL_SENDER` | `email_service.py` | Yes (reminders) | — | SMTP From address |
| `EMAIL_RECIPIENT` | `email_service.py` | Yes (reminders) | — | SMTP To address |
| `EMAIL_PASSWORD` | `email_service.py` | Yes (reminders) | — | SMTP password |
| `EMAIL_SMTP_SERVER` | `email_service.py` | No | `smtp.gmail.com` | SMTP host |
| `EMAIL_SMTP_PORT` | `email_service.py` | No | `587` | SMTP port |
| `EMAIL_ADDRESS` | `email_agent.py` (legacy) | No | — | Legacy EmailAgent From address |
| `REMINDER_EMAIL` | `email_agent.py` (legacy) | No | — | Legacy EmailAgent To address |
| `SMTP_HOST` | `email_agent.py` (legacy) | No | `smtp.gmail.com` | Legacy EmailAgent SMTP host |

*`MCP_API_KEY` is effectively required for non-localhost deployments — the server raises `RuntimeError` at startup if absent.

---

## 11. Known Edge Cases

### Task ID collision risk

`create_task` computes `next_id = max(existing)+1` with two separate DB reads and writes. Concurrent creates from two processes can produce the same ID. `INSERT OR REPLACE` would silently overwrite the first task. **Mitigation:** use `AUTOINCREMENT` or a `SELECT … FOR UPDATE`-equivalent (serialised writes under WAL).

### Token ↔ execution join fragility

`get_token_usage_for_execution` joins `token_usage` to `execution_events` using a ±2-second `created_at` window and `operation` name. Under high concurrency, two simultaneous LLM calls of the same operation type could be attributed to the wrong execution.

### `planning_agent.py` dead code

`collaborative_daily_plan` is defined twice in the same class. The second definition (with token optimisation) shadows the first. The first definition is never called.

### Root-level `reminder_service.py` runtime failure

`reminder_service.py` at the project root calls `db.mark_reminder_sent(task_id)` without the required `reminder_type` argument. This raises `TypeError` at runtime. Use `reminder_worker.py` instead.

### Historical transport gaps

7 executions recorded before `mcp_transport.py` was introduced have MCP events in `execution_events` but no corresponding rows in `mcp_transport`. These gaps are permanent (not backfilled). The dashboard uses `execution_events` as the authoritative count to compensate.

### WAL mode idempotency

`PRAGMA journal_mode=WAL` is executed on every connection. SQLite ignores it if already set at the file level, so this is safe but slightly redundant. It can be moved to a one-time `initialize()` call.
