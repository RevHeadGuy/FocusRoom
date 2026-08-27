# Architecture Diagram — Productivity Agent

---

## 1. System Overview — Four Processes

```
╔══════════════════════════════════════════════════════════════════════════════════╗
║                         PRODUCTIVITY AGENT — ARCHITECTURE                       ║
╚══════════════════════════════════════════════════════════════════════════════════╝

  ┌─────────────────────────────────────────────────────────────────────────────┐
  │  PROCESS 1 — Streamlit Frontend  (streamlit_app.py)                         │
  │                                                                              │
  │   Overview │ Tasks │ Plan │ Memory │ Assistant                               │
  │      │          │       │        │          │                                │
  │      └──────────┴───────┴────────┘          │                               │
  │             direct agent.* calls      supervisor.run(prompt)                │
  └─────────────────────┬───────────────────────┬───────────────────────────────┘
                        │                       │
          Python import │                       │ Python import
                        │                       │
  ┌─────────────────────▼───────────────────────▼───────────────────────────────┐
  │  PROCESS 1 (shared) — Agent Core                                             │
  │                                                                              │
  │  ┌──────────────────────────────┐   ┌────────────────────────────────────┐  │
  │  │  ProductivityOrchestrator    │   │  ProductivitySupervisor            │  │
  │  │  (agent.py)                  │   │  (orchestrator.py)                 │  │
  │  │                              │   │                                    │  │
  │  │  create_task / list_tasks    │   │  Tier 1: deterministic router      │  │
  │  │  complete_task / update_task │   │  Tier 2: LLM router → Groq API     │  │
  │  │  save_memory / search_memory │   │                                    │  │
  │  │  create_daily_plan           │   │  ThreadPoolExecutor (max_workers=2) │  │
  │  │  productivity_report         │   │  ┌────────────┐  ┌──────────────┐  │  │
  │  │  call_llm ──────────────────────▶  │ TASK_AGENT │  │ MEMORY_AGENT │  │  │
  │  │            Groq API          │   │  │ (parallel) │  │  (parallel)  │  │  │
  │  └──────────────────────────────┘   │  └─────┬──────┘  └──────┬───────┘  │  │
  │                                     │        └────────┬────────┘          │  │
  │                                     │                 ▼                   │  │
  │                                     │        ┌─────────────────┐          │  │
  │                                     │        │  PLANNING_AGENT │          │  │
  │                                     │        │  (sequential)   │          │  │
  │                                     │        │  LLM max=400tok │          │  │
  │                                     │        └─────────────────┘          │  │
  │                                     └────────────────────────────────────┘  │
  │                                                                              │
  │  ┌──────────────────────────────┐   ┌────────────────────────────────────┐  │
  │  │  mcp_transport.py            │   │  telemetry.py                      │  │
  │  │  record_mcp_call()           │   │  ContextVar _current_execution_id  │  │
  │  │  in-process byte measurement │   │  start / record_event / finish     │  │
  │  └──────────────┬───────────────┘   └────────────────────────────────────┘  │
  └─────────────────┼────────────────────────────────────────────────────────────┘
                    │                                    │ all DB reads / writes
                    ▼                                    ▼
  ┌─────────────────────────────────────────────────────────────────────────────┐
  │  SHARED — Database  (productivity.db — SQLite, WAL mode)                    │
  │                                                                              │
  │   tasks              memories           token_usage                         │
  │   ──────────────     ─────────────      ──────────────────────              │
  │   id                 key (PK)           id                                  │
  │   title              value              operation                           │
  │   description        category           model                               │
  │   priority           updated_at         prompt_tokens                       │
  │   status                                completion_tokens                   │
  │   due_date           mcp_transport      total_tokens                        │
  │   project            ─────────────      created_at ◀── ±2s join key        │
  │   created_at         id                                                     │
  │   completed_at       execution_id       execution_events  ◀── authoritative │
  │   reminder_24_sent   method             ──────────────────     MCP counts   │
  │   reminder_1_sent    path               id                                  │
  │   reminder_15_sent   request_bytes      execution_id (UUID)                 │
  │                      response_bytes     event_type                          │
  │                      status_code        name                                │
  │                      created_at         details (JSON)                      │
  │                                         created_at                          │
  └─────────────────────────────────────────────────────────────────────────────┘
                    ▲                                    ▲
                    │                                    │
  ┌─────────────────┴────────────────┐   ┌──────────────┴──────────────────────┐
  │  PROCESS 2 — MCP Server          │   │  PROCESS 3 — Reminder Worker         │
  │  (orchestrator/mcp_server.py)    │   │  (reminder_worker.py)                │
  │                                  │   │                                      │
  │  Starlette ASGI  :8000/mcp       │   │  loop every 60 s                     │
  │                                  │   │                                      │
  │  ┌───────────────────────────┐   │   │  ReminderAgent                       │
  │  │ APIKeyMiddleware           │   │   │    get_upcoming_tasks(24h)           │
  │  │ hmac.compare_digest       │   │   │    get_reminder_type(hours_left)     │
  │  └─────────────┬─────────────┘   │   │    reminder_was_sent? → skip         │
  │  ┌─────────────▼─────────────┐   │   │         │                            │
  │  │ TransportMetricsMiddleware │   │   │         ▼                            │
  │  │ raw ASGI intercept         │   │   │  EmailService                        │
  │  │ request_bytes  ──────────────▶│   │    smtplib SMTP + STARTTLS           │
  │  │ response_bytes ◀────────────── │   │    send_message                      │
  │  │ → mcp_transport (DB)      │   │   │         │                            │
  │  └─────────────┬─────────────┘   │   │         ▼                            │
  │  ┌─────────────▼─────────────┐   │   │  mark_reminder_sent (DB)             │
  │  │ 10 MCP Tools               │   │   │                                      │
  │  │ ─────────────────────────  │   │   └──────────────────────────────────────┘
  │  │ productivity_assistant ────────▶  ProductivitySupervisor.run()
  │  │ create_task / list_tasks   │   │
  │  │ update / complete / delete │   │   ┌──────────────────────────────────────┐
  │  │ save_memory / search_memory│   │   │  EXTERNAL SERVICES                   │
  │  │ daily_plan                 │   │   │                                      │
  │  │ productivity_report        │   │   │  Groq API  ◀── call_llm()            │
  │  └────────────────────────────┘   │   │  (supervisor_decision,               │
  │                                   │   │   planning_request)                  │
  │  ◀── Kiro IDE                     │   │                                      │
  │  ◀── Claude Desktop               │   │  SMTP Server ◀── EmailService        │
  │  ◀── any MCP client               │   │  (Gmail / any provider)              │
  └───────────────────────────────────┘   └──────────────────────────────────────┘
```

---

## 2. Supervisor Request Flow

The critical path for the main use case: `"Check my tasks, consider my preferences, and plan my day."`

```
  User prompt
       │
       ▼
  ProductivitySupervisor.run()
       │
       ├─ Tier 1: _route_deterministically()  ─── 0 LLM tokens
       │    matches _DAILY_PLAN_PHRASES
       │    → [TASK_AGENT:list, MEMORY_AGENT:search, PLANNING_AGENT:daily]
       │
       │    (if no match → Tier 2)
       │    Tier 2: decide_agent()
       │      → call_llm([system, user])
       │      → parse + normalize decisions
       │
       ├─ record_event("Agent", "supervisor", {actions})
       │
       ├─ ThreadPoolExecutor(max_workers=2) ─── copy_context() per thread
       │
       │   ┌─── _run_task ────────────────────────────────────────────┐
       │   │  record_event("Agent", "TASK_AGENT")                     │
       │   │  record_event("MCP",   "list_tasks")                     │
       │   │  task_agent.handle("list", {})                           │
       │   │    → agent.list_tasks() → db.get_tasks()                 │
       │   │  record_mcp_call(db, "list_tasks", args, result)         │
       │   │  record_event("Result", "task_agent_result", result)     │
       │   └──────────────────────────────┬───────────────────────────┘
       │                                  │ (parallel)
       │   ┌─── _run_memory ──────────────┴───────────────────────────┐
       │   │  record_event("Agent", "MEMORY_AGENT")                   │
       │   │  record_event("MCP",   "search_memory")                  │
       │   │  memory_agent.handle("search", {"query": …})             │
       │   │    → agent.search_memory() → db.search_memory()          │
       │   │  record_mcp_call(db, "search_memory", args, result)      │
       │   │  record_event("Result", "memory_agent_result", result)   │
       │   └──────────────────────────────────────────────────────────┘
       │                         │ both complete
       │                         ▼
       ├─ planning_agent.handle("daily", {task_context, memory_context})
       │    _filter_tasks()     → active, ≤14 days ahead, top 15
       │    _filter_memories()  → top 5 entries
       │    _encode_tasks()     → "!! Title (mm-dd)"  compact
       │    _encode_memories()  → values only, max 80 chars
       │    call_llm(max_tokens=400)
       │      → Groq API
       │      → db.save_token_usage()
       │      → record_event("LLM", "planning_request")
       │    return {"plan": "…", "source_agents": […]}
       │
       ├─ record_event("Result", "agent_result")
       └─ finish_execution()
            ▼
       {"plan": "MORNING FOCUS …", "source_agents": ["TASK_AGENT", …]}
```

---

## 3. MCP HTTP Request Flow

```
  External MCP client (Kiro / Claude Desktop / curl)
       │
       │  HTTP POST :8000/mcp
       │  Authorization: Bearer <key>
       ▼
  ┌─────────────────────────────────────────────────────────────┐
  │  APIKeyMiddleware                                            │
  │  hmac.compare_digest(key, MCP_API_KEY)                      │
  │  → 401 on failure                                           │
  └───────────────────────────┬─────────────────────────────────┘
                              ▼
  ┌─────────────────────────────────────────────────────────────┐
  │  TransportMetricsMiddleware  (raw ASGI)                     │
  │  http.request      → accumulate request_bytes               │
  │  http.response.start → db.start_mcp_transport() → row_id   │
  │  http.response.body  → db.update_mcp_transport(row_id, …)  │
  └───────────────────────────┬─────────────────────────────────┘
                              ▼
  ┌─────────────────────────────────────────────────────────────┐
  │  trace_mcp_tool decorator                                   │
  │  start_execution() → execution_id                           │
  │  record_event("MCP Tool", tool_name, {arguments})           │
  └───────────────────────────┬─────────────────────────────────┘
                              ▼
                       MCP Tool function
                    (create_task / list_tasks / …)
                              │
                              ▼
                       agent.* method
                              │
                              ▼
                       db.*  (SQLite)
                              │
                              ▼
  ┌─────────────────────────────────────────────────────────────┐
  │  trace_mcp_tool decorator  (finally)                        │
  │  record_event("Result", "mcp_result", {result})             │
  │  finish_execution()                                         │
  └───────────────────────────┬─────────────────────────────────┘
                              ▼
  {"success": true, "data": {…}, "error": null}
```

---

## 4. Telemetry Data Flow

```
  Each agent action
       │
       ├─ record_event(db, event_type, name, details)
       │       │
       │       ▼
       │   execution_events table
       │   (execution_id, event_type, name, details, created_at)
       │
       ├─ call_llm(messages, operation)
       │       │
       │       ├─ Groq API response
       │       │
       │       ├─ db.save_token_usage(operation, tokens)
       │       │       │
       │       │       ▼
       │       │   token_usage table
       │       │   (operation, prompt, completion, total, created_at)
       │       │
       │       └─ record_event("LLM", operation, usage)
       │               │
       │               ▼
       │           execution_events table  ◀── joined via ±2s window
       │
       └─ record_mcp_call(db, tool, args, result)
               │
               ▼
           mcp_transport table
           (execution_id, method="TOOL", path, req_bytes, resp_bytes)


  Dashboard reads:
  ┌────────────────────────────────────────────────────────────────┐
  │  MCP call counts   ← execution_events WHERE event_type='MCP'  │
  │                      (authoritative — transport rows may lag)  │
  │                                                                │
  │  Byte totals       ← mcp_transport SUM(request/response_bytes)│
  │                                                                │
  │  Token usage       ← token_usage GROUP BY operation           │
  │                                                                │
  │  Agent status      ← execution_events WHERE event_type='Agent'│
  │                      latest execution_id only                  │
  │                                                                │
  │  Execution trace   ← execution_events ORDER BY id             │
  │                      grouped by execution_id                   │
  └────────────────────────────────────────────────────────────────┘
```

---

## 5. Reminder Pipeline

```
  reminder_worker.py  (loop every 60 s)
       │
       ▼
  ReminderAgent.generate_reminders(hours=24)
       │
       ├─ db.get_tasks()
       ├─ filter: status != completed AND due_date in [now, now+24h]
       ├─ get_reminder_type(hours_left)
       │     ≤ 0.25h  → "15"
       │     ≤ 1h     → "1"
       │     ≤ 24h    → "24"
       │     else     → None (skip)
       │
       └─ db.reminder_was_sent(task_id, type)?
              yes → skip
              no  → add to reminders list
                         │
                         ▼
                  EmailService.send_email(subject, body)
                         │
                         ├─ validate EMAIL_SENDER / EMAIL_RECIPIENT / EMAIL_PASSWORD
                         ├─ smtplib.SMTP(EMAIL_SMTP_SERVER, 587)
                         ├─ STARTTLS
                         ├─ login
                         └─ send_message
                                  │
                                  ▼
                         db.mark_reminder_sent(task_id, type)
                         sets reminder_*_sent = 1 in tasks table
```

---

## 6. Component Dependency Map

```
  streamlit_app.py
    ├── orchestrator/agent.py          (ProductivityOrchestrator)
    ├── orchestrator/orchestrator.py   (ProductivitySupervisor)
    │     ├── orchestrator/task_agent.py
    │     │     └── orchestrator/agent.py
    │     ├── orchestrator/memory_agent.py
    │     │     └── orchestrator/agent.py
    │     ├── orchestrator/planning_agent.py
    │     │     └── orchestrator/agent.py
    │     ├── orchestrator/telemetry.py
    │     └── orchestrator/mcp_transport.py
    │           └── orchestrator/database.py
    └── orchestrator/database.py

  orchestrator/mcp_server.py
    ├── orchestrator/agent.py
    ├── orchestrator/orchestrator.py
    ├── orchestrator/telemetry.py
    └── orchestrator/database.py

  reminder_worker.py
    ├── orchestrator/reminder_agent.py
    │     └── orchestrator/database.py
    └── orchestrator/email_service.py

  All modules
    └── orchestrator/database.py      (single shared SQLite connection factory)
```
