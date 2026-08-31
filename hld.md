# High Level Design (HLD) — Productivity Agent

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Goals and Non-Goals](#2-goals-and-non-goals)
3. [System Components](#3-system-components)
4. [High Level Architecture](#4-high-level-architecture)
5. [Multi-Agent Design](#5-multi-agent-design)
6. [Data Storage Strategy](#6-data-storage-strategy)
7. [MCP Integration](#7-mcp-integration)
8. [Telemetry and Observability](#8-telemetry-and-observability)
9. [Reminder and Notification System](#9-reminder-and-notification-system)
10. [Security Model](#10-security-model)
11. [Token Efficiency Strategy](#11-token-efficiency-strategy)
12. [Technology Stack](#12-technology-stack)
13. [Deployment Model](#13-deployment-model)
14. [Key Design Trade-offs](#14-key-design-trade-offs)

---

## 1. Project Overview

Productivity Agent is a local-first, AI-powered productivity system. It manages tasks, stores contextual memory, and generates daily plans by orchestrating a set of specialised agents that each call an MCP (Model Context Protocol) server as their tool interface.

The system exposes two surfaces:

- **Streamlit dashboard** — a visual interface for managing tasks, memories, plans, and viewing telemetry
- **MCP server** — a protocol-compliant HTTP endpoint that allows AI clients (Kiro IDE, Claude Desktop, or any MCP-compatible tool) to drive the same agent core

Both surfaces share the same Python agent code and the same SQLite database. There is no duplication of business logic.

---

## 2. Goals and Non-Goals

### Goals

- Let a user describe a complex productivity request in natural language and have the system automatically route it to the right combination of agents
- Keep LLM token usage minimal — deterministic routing for known patterns, compact prompts, bounded output lengths
- Give full visibility into every execution: which agents ran, how many MCP calls were made, how many tokens were spent, and the exact trace of events
- Support external AI clients via MCP so the agent core is not locked to the Streamlit UI
- Send proactive email reminders before task deadlines without any user action

### Non-Goals

- Multi-user / cloud deployment (the system is designed for a single local user)
- Real-time collaboration or shared workspaces
- A mobile app or REST API beyond the MCP endpoint
- Advanced ML features (fine-tuning, embeddings, vector search) — memory search is keyword-based
- Calendar or external integrations beyond SMTP email

---

## 3. System Components

| Component | Entry Point | Responsibility |
|---|---|---|
| Streamlit Frontend | `streamlit_app.py` | User interface: task management, memory, daily plan, assistant chat, telemetry dashboard |
| Agent Core | `orchestrator/agent.py` | All domain logic: CRUD for tasks and memories, LLM calls, daily plan, productivity report |
| Supervisor | `orchestrator/orchestrator.py` | Routes user requests to agents, orchestrates parallel execution, aggregates results |
| Task Agent | `orchestrator/task_agent.py` | Thin dispatcher for task-related MCP actions |
| Memory Agent | `orchestrator/memory_agent.py` | Thin dispatcher for memory-related MCP actions |
| Planning Agent | `orchestrator/planning_agent.py` | Generates AI daily plans from pre-fetched task and memory context |
| MCP Server | `orchestrator/mcp_server.py` | Starlette ASGI app exposing 10 MCP tools over Streamable HTTP |
| Database | `orchestrator/database.py` | SQLite wrapper; owns all schema, migrations, and query logic |
| Telemetry | `orchestrator/telemetry.py` | Context-variable execution tracking across threads |
| Transport Recorder | `orchestrator/mcp_transport.py` | Measures and persists MCP byte usage for in-process calls |
| Reminder Worker | `reminder_worker.py` | Independent process: polls DB, sends email alerts before due dates |
| Email Service | `orchestrator/email_service.py` | SMTP send logic used by the reminder pipeline |

---

## 4. High Level Architecture

```
                         ┌──────────────────────────┐
                         │   User / AI Client        │
                         └──────┬───────────┬────────┘
                                │           │
                    Browser UI  │           │  MCP over HTTP
                                │           │
               ┌────────────────▼──┐   ┌───▼────────────────────┐
               │  Streamlit App    │   │  MCP Server            │
               │  (dashboard)      │   │  Starlette ASGI        │
               └────────┬──────────┘   └───────────┬────────────┘
                        │                           │
                        │   direct Python import    │
                        └──────────┬────────────────┘
                                   │
                    ┌──────────────▼──────────────────┐
                    │         Agent Core               │
                    │                                  │
                    │  ProductivityOrchestrator        │
                    │  ProductivitySupervisor          │
                    │  TaskAgent / MemoryAgent         │
                    │  PlanningAgent                   │
                    └──────────┬──────────────────┬───┘
                               │                  │
               ┌───────────────▼───┐     ┌────────▼────────────┐
               │  SQLite DB        │     │  Groq API (LLM)     │
               │  productivity.db  │     │  (external)         │
               │  WAL mode         │     └─────────────────────┘
               └───────────────────┘
                               ▲
                               │
               ┌───────────────┴───────────────────┐
               │  Reminder Worker (independent)     │
               │  ReminderAgent → EmailService      │
               │  → SMTP (external)                 │
               └───────────────────────────────────┘
```

The key structural choice is that **the Streamlit app and the MCP server both import the same agent code directly**. There is no internal API layer between them and the business logic. This keeps the system simple and fast at the cost of requiring both surfaces to run in the same process environment.

---

## 5. Multi-Agent Design

### Why multiple agents

The system splits concerns into three specialised agents rather than sending everything to one general LLM call:

- **TASK_AGENT** — knows how to interact with the task database; no LLM involved
- **MEMORY_AGENT** — knows how to search and store contextual memory; no LLM involved
- **PLANNING_AGENT** — knows how to synthesise tasks and memories into an actionable plan; one focused LLM call

This means the LLM is called only for the planning step (and for routing when the request doesn't match a known pattern). All data retrieval is deterministic.

### Two-tier routing

```
User request
     │
     ▼
Tier 1: Deterministic router
  Does the request match a known phrase pattern?
     │
     ├── YES → resolve action list instantly, 0 tokens
     │
     └── NO
          ▼
     Tier 2: LLM router
       System prompt constrains output to JSON action schema
       parse + validate + normalise decisions
```

Known patterns (Tier 1): daily planning requests, list tasks, overdue tasks, high-priority tasks, productivity report. All other requests fall through to the LLM router.

### Parallel execution

TASK_AGENT and MEMORY_AGENT run concurrently in a `ThreadPoolExecutor`. PLANNING_AGENT runs after both complete, consuming their results as context. This reduces wall-clock time for the most common request type (daily plan) from sequential to parallel.

```
Supervisor
    │
    ├── TASK_AGENT  ──┐  (parallel, separate thread context)
    ├── MEMORY_AGENT ─┤
    │                 │ both complete
    └── PLANNING_AGENT◄┘  (sequential, uses results above)
```

Each thread gets its own copy of the execution context variable (`contextvars.copy_context()`) so telemetry events from parallel workers don't interfere with each other.

### Context propagation to Planning Agent

The Planning Agent does not call the database itself when invoked via the supervisor. The supervisor passes pre-fetched task and memory data as compact JSON strings. This avoids redundant DB reads and gives Planning Agent a consistent snapshot of the data that Task Agent and Memory Agent already retrieved.

---

## 6. Data Storage Strategy

### Single SQLite file

All persistent state lives in one file: `productivity.db`. There are five tables:

| Table | Purpose |
|---|---|
| `tasks` | Task records with status, priority, due dates, reminder flags |
| `memories` | Key-value contextual memory with category and timestamp |
| `token_usage` | Every LLM call: operation, model, token counts |
| `mcp_transport` | Every MCP call: byte sizes, execution ID, method, path |
| `execution_events` | Ordered event log for every execution: agents, MCP calls, LLM calls, results |

### Why SQLite

- Zero infrastructure — runs wherever Python runs
- WAL mode enables concurrent readers + one writer without blocking, which matters because the Streamlit process and the Reminder Worker can be active simultaneously
- The data volume (tasks, memories, telemetry) will not approach SQLite's practical limits for a single-user tool

### Authoritative sources

The design separates "what happened" from "transport measurement":

- **MCP call counts** — read from `execution_events` (always written synchronously by the agent workers)
- **Byte totals** — read from `mcp_transport` (best-effort; may have gaps from historical executions before the transport recorder was introduced)

This separation means the dashboard call count is always correct even if transport byte rows are missing.

---

## 7. MCP Integration

### What MCP provides

MCP (Model Context Protocol) is the interface layer that allows external AI clients to call the agent's tools without knowing anything about the internal implementation. The 10 exposed tools cover the full CRUD surface for tasks and memories, plus planning and assistant capabilities.

### Two call paths for the same tools

```
Path A — Direct (Streamlit):
  streamlit_app.py → agent.create_task(…) → db.save_task(…)

Path B — HTTP (MCP client):
  HTTP POST /mcp → mcp_server.create_task(…) → agent.create_task(…) → db.save_task(…)
```

The MCP server is a thin wrapper. It adds authentication, byte measurement, and execution tracing — the actual business logic is identical in both paths.

### Transport measurement

HTTP calls are measured at the ASGI level by `TransportMetricsMiddleware`, which intercepts raw request and response body bytes. In-process calls (supervisor calling agents directly) are measured by `mcp_transport.record_mcp_call`, which computes byte size from the JSON representation of the tool arguments and result. Both write to the same `mcp_transport` table.

---

## 8. Telemetry and Observability

Every execution produces a structured event log. The dashboard surfaces four panels from this data:

| Panel | Data source | What it shows |
|---|---|---|
| AI Usage | `token_usage` grouped by operation | Requests, prompt tokens, completion tokens, total tokens per operation + averages |
| Agent Execution | `execution_events` WHERE type='Agent' | Which agents ran (tick/cross) in the most recent execution |
| MCP | `execution_events` WHERE type='MCP' + `mcp_transport` | Tool call counts (authoritative) + transport byte totals |
| Execution Trace | `execution_events` ordered by ID | Step-by-step event log for the most recent execution |

### Execution ID lifecycle

Each user request gets a UUID (`execution_id`) that flows through every layer:

```
start_execution() → UUID stored in ContextVar
    ↓
All record_event() calls tag rows with this UUID
    ↓
All mcp_transport rows tagged with this UUID
    ↓
finish_execution() → ContextVar cleared
```

This makes it possible to reconstruct the exact sequence of events for any single request.

### Token attribution

Token usage rows in `token_usage` are linked to execution events via a timestamp proximity join (±2 seconds, same operation name). This is a pragmatic approach that avoids adding an `execution_id` column to `token_usage` while still enabling per-execution breakdowns.

---

## 9. Reminder and Notification System

The reminder system is a separate, independently runnable process. It has no dependency on the Streamlit app or the MCP server — it only needs the database and SMTP credentials.

### Reminder stages

Three reminder thresholds per task to give progressively urgent notices:

| Stage | When sent | Condition |
|---|---|---|
| 24-hour | Day before | `0.25h < hours_left ≤ 24h` |
| 1-hour | Hour before | `0.25h < hours_left ≤ 1h` |
| 15-minute | Final warning | `hours_left ≤ 0.25h` |

### Deduplication

Each reminder type is sent at most once per task. A boolean flag column in the `tasks` table (`reminder_24_sent`, `reminder_1_sent`, `reminder_15_sent`) provides persistent deduplication that survives process restarts.

---

## 10. Security Model

| Concern | Mechanism |
|---|---|
| MCP API authentication | `APIKeyMiddleware` using `hmac.compare_digest` for timing-safe bearer token comparison |
| Remote exposure guard | Server raises `RuntimeError` at startup if `MCP_HOST` is non-localhost and no `MCP_API_KEY` is set |
| Secrets management | All credentials (API keys, SMTP password) loaded from `.env` file via `python-dotenv`; never hardcoded |
| Local-only default | MCP server binds to `127.0.0.1` by default; changing to a network interface requires explicit configuration |
| SQLite access | No network exposure; file-level OS permissions are the only access control |

The system is designed for local single-user deployment. It is not hardened for multi-tenant or public internet exposure.

---

## 11. Token Efficiency Strategy

LLM calls are the primary operational cost. The system applies several techniques to minimise token usage:

| Technique | Where applied | Effect |
|---|---|---|
| Deterministic routing | Supervisor Tier 1 | Eliminates routing LLM call for known request patterns |
| Compact task encoding | PlanningAgent | `"!! Title (mm-dd)"` format instead of full JSON objects |
| Context windowing | PlanningAgent | Max 15 tasks (≤14 days ahead), top 5 memories |
| Output length cap | PlanningAgent | `max_tokens=400` for plan generation |
| Memory value truncation | PlanningAgent | Memory values capped at 80 characters in prompt |
| Pre-fetched context | Supervisor → PlanningAgent | Planning Agent receives data already retrieved; no redundant DB reads or extra LLM calls for data gathering |
| No LLM for CRUD | TaskAgent, MemoryAgent | Task listing, memory search, task creation — all fully deterministic |

The result is that a standard daily planning request calls the LLM at most twice: once for routing (if the deterministic router doesn't match) and once for plan generation.

---

## 12. Technology Stack

| Layer | Technology | Why |
|---|---|---|
| Language | Python 3.12+ | Ecosystem fit for AI/ML tooling |
| UI framework | Streamlit | Rapid interactive dashboard with minimal frontend code |
| LLM provider | Groq API | Fast inference; OpenAI-compatible client interface |
| Agent protocol | MCP (Model Context Protocol) Python SDK v2.0 | Standard protocol for AI tool integration |
| MCP transport | Starlette ASGI (Streamable HTTP) | Lightweight async HTTP server |
| Database | SQLite (WAL mode) | Zero-infrastructure persistence; sufficient for single-user scale |
| Email | smtplib + STARTTLS | Standard library; no extra dependencies for SMTP |
| Concurrency | `concurrent.futures.ThreadPoolExecutor` + `contextvars` | Thread-based parallelism with isolated execution context per thread |
| Dependency management | pip + `requirements.txt` + `.venv` | Standard Python tooling |
| Configuration | `python-dotenv` + `.env` file | Keeps secrets out of source code |

---

## 13. Deployment Model

The system runs as up to three separate OS processes on the same machine:

```
Process 1: Streamlit app
  streamlit run streamlit_app.py
  Imports agent core directly
  Serves the dashboard on localhost:8501

Process 2: MCP Server  (optional)
  python -m orchestrator.mcp_server
  Serves MCP tools on localhost:8000
  Required only for external AI client access

Process 3: Reminder Worker  (optional)
  python reminder_worker.py
  Polls DB every 60 seconds
  Required only if email reminders are wanted
```

All three processes share `productivity.db`. SQLite WAL mode makes concurrent access safe.

There is no container, orchestration layer, or cloud dependency. The entire system runs on a developer laptop.

---

## 14. Key Design Trade-offs

| Decision | Benefit | Cost |
|---|---|---|
| Single SQLite file | Zero infrastructure, simple deployment | Not horizontally scalable; single-machine only |
| Direct import (no internal API) | No serialisation overhead, simpler code | Streamlit and agent core must run in the same Python process |
| Keyword-based memory search | No embedding model needed, fully local | Less semantically accurate than vector search |
| Timestamp proximity join for token attribution | No schema change to `token_usage` | Can misattribute tokens under high concurrency |
| Manual task ID generation (`max+1`) | Simple | Race condition risk under concurrent creates |
| Three separate OS processes | Independent scaling and restarts | No automatic process supervision (no systemd/Docker) |
| Deterministic router as Tier 1 | Saves tokens for common requests | Phrase lists must be manually maintained as new request types emerge |
