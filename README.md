# FocusRoom

> **Make room for the work that matters.**

FocusRoom is an AI-powered **Productivity Operating System** that turns
natural-language requests into actions across tasks, persistent memory,
daily planning, and a multi-agent orchestration layer.

Instead of forcing users to manage several productivity features
separately, FocusRoom gives them one assistant that can understand
intent, call the right specialist agents, use MCP tools, and return a
focused result.

------------------------------------------------------------------------

## ✨ What makes FocusRoom different?

FocusRoom is built around one idea:

**The assistant should do the coordination, not the user.**

A request such as:

> *"Check my pending tasks, consider my work preferences, and create my
> daily plan."*

can flow through the system as:

``` text
User Request
     │
     ▼
┌───────────────┐
│   Supervisor  │
│ Intent / Route│
└───────┬───────┘
        │
   ┌────┴──────────────┐
   ▼                   ▼
Task Agent        Memory Agent
   │                   │
   ▼                   ▼
list_tasks        search_memory
   │                   │
   └─────────┬─────────┘
             ▼
      Planning Agent
             │
             ▼
        daily_plan
             │
             ▼
       Focused Result
```

The project combines **multi-agent orchestration + MCP + persistent
memory + task management + AI planning** in one productivity workflow.

------------------------------------------------------------------------

## 🚀 Core capabilities

### 🧠 Natural-language assistant

Users can interact with FocusRoom conversationally rather than learning
individual commands.

Examples:

``` text
Show my pending tasks
```

``` text
Create a task called Prepare Q3 presentation with high priority.
```

``` text
Plan my day and prioritize my MCP learning.
```

``` text
Check my pending tasks and create my daily plan.
```

The `ProductivitySupervisor` interprets the request and routes work to
the appropriate agent.

------------------------------------------------------------------------

### 🤖 Multi-agent architecture

FocusRoom separates responsibilities across specialized agents:

  -----------------------------------------------------------------------
  Agent                               Responsibility
  ----------------------------------- -----------------------------------
  **Supervisor**                      Understands intent and coordinates
                                      execution

  **Task Agent**                      Creates, lists, updates, completes,
                                      and deletes tasks

  **Memory Agent**                    Stores and retrieves persistent
                                      user context

  **Planning Agent**                  Converts task + memory context into
                                      a daily plan
  -----------------------------------------------------------------------

This keeps individual components focused while allowing them to
collaborate.

------------------------------------------------------------------------

### 🧩 MCP integration

FocusRoom exposes productivity capabilities through an MCP server.

Current MCP tools include:

``` text
productivity_assistant
create_task
list_tasks
update_task
complete_task
delete_task
save_memory
search_memory
daily_plan
productivity_report
```

The MCP layer provides a standardized tool interface between the
assistant and productivity operations.

The project also includes MCP transport telemetry for measuring:

-   Request count
-   Request bytes
-   Response bytes
-   HTTP status
-   Transport activity
-   Execution IDs

------------------------------------------------------------------------

### 📅 AI daily planning

The planning workflow combines:

``` text
Tasks
  +
Relevant memories
  +
User request
  ↓
Planning Agent
  ↓
Morning / Afternoon / Evening
  +
Priority reasoning
```

The planner is designed to avoid inventing tasks and instead schedule
work from the available task context.

------------------------------------------------------------------------

## ⚡ Token-efficient AI pipeline

A major engineering focus of FocusRoom is reducing unnecessary LLM
usage.

The planning pipeline uses several optimizations:

### 1. Deterministic routing

Common requests can bypass the supervisor LLM.

For example:

``` text
"plan my day"
"daily plan"
"create my daily plan"
```

can be recognized directly and routed to:

``` text
TASK_AGENT → MEMORY_AGENT → PLANNING_AGENT
```

The LLM remains available as a fallback for requests that cannot be
confidently classified.

### 2. Task filtering

Only relevant active tasks are passed into the planning prompt.

### 3. Compact task representation

Instead of sending verbose task JSON, the planner receives compact
representations such as:

``` text
!! Ship landing page (08-25)
! Write tests (08-25)
- Update docs
```

### 4. Memory limiting

Only a small number of relevant/recent memories are included rather than
sending the entire memory store.

### 5. Compact context serialization

Planning context uses compact JSON instead of human-formatted indented
JSON.

### 6. Completion limits

The planning model has a maximum completion-token budget so that a
simple daily plan cannot produce unnecessarily long output.

### Example optimization target

A representative planning prompt was reduced to approximately:

``` text
~124 prompt tokens
+ up to 400 completion tokens
≈ 524-token planning budget
```

The exact token usage depends on the model, input data, and generated
response.

------------------------------------------------------------------------

## 📊 Built-in execution telemetry

FocusRoom records execution information so the system can be measured
instead of treated as a black box.

Example telemetry:

``` text
AI USAGE

Operation                 Prompt   Completion   Total
------------------------------------------------------
supervisor_decision        ...       ...        ...
planning_request           ...       ...        ...
TOTAL                      ...       ...        ...
AVG / exec                 ...       ...        ...
```

Execution traces expose the path taken by a request:

``` text
supervisor
    ↓
TASK_AGENT
    ↓
MCP:list_tasks
    ↓
MEMORY_AGENT
    ↓
MCP:search_memory
    ↓
PLANNING_AGENT
    ↓
MCP:daily_plan
    ↓
LLM:planning_request
    ↓
agent_result
```

This makes it possible to investigate:

-   unnecessary LLM calls
-   excessive prompt size
-   expensive tool calls
-   response payload growth
-   agent routing problems
-   MCP transport overhead

------------------------------------------------------------------------

## 🏗️ Architecture

``` text
                         ┌──────────────────┐
                         │    Streamlit UI  │
                         └────────┬─────────┘
                                  │
                                  ▼
                    ┌─────────────────────────┐
                    │ Productivity Assistant  │
                    └────────────┬────────────┘
                                 │
                                 ▼
                    ┌─────────────────────────┐
                    │ Productivity Supervisor │
                    │                         │
                    │ deterministic router    │
                    │ + LLM fallback          │
                    └───────┬─────┬─────┬─────┘
                            │     │     │
                  ┌─────────┘     │     └─────────┐
                  ▼               ▼               ▼
           ┌────────────┐  ┌────────────┐  ┌──────────────┐
           │ Task Agent │  │Memory Agent│  │Planning Agent│
           └─────┬──────┘  └─────┬──────┘  └──────┬───────┘
                 │               │                 │
                 ▼               ▼                 ▼
           list/create      search/save        daily plan
                 │               │                 │
                 └───────────────┼─────────────────┘
                                 ▼
                         ┌──────────────┐
                         │ MCP Server   │
                         │ + Transport  │
                         │ + Telemetry  │
                         └──────┬───────┘
                                │
                                ▼
                         ┌──────────────┐
                         │   Database   │
                         └──────────────┘
```

For detailed implementation decisions, see:

-   `lld.md`
-   `architecture.md`

------------------------------------------------------------------------

## 🗂️ Project structure

``` text
FocusRoom/
│
├── orchestrator/
│   ├── agent.py
│   ├── database.py
│   ├── mcp_server.py
│   ├── mcp_transport.py
│   ├── memory_agent.py
│   ├── orchestrator.py
│   ├── planning_agent.py
│   ├── task_agent.py
│   └── telemetry.py
│
├── streamlit_app.py
├── README.md
├── lld.md
└── architecture.md
```

------------------------------------------------------------------------

## 🔄 Example request lifecycle

### User

``` text
"Check my pending tasks and create my daily plan."
```

### Supervisor

Determines that the request needs:

``` text
TASK_AGENT:list
MEMORY_AGENT:search
PLANNING_AGENT:daily
```

### Task Agent

Retrieves active tasks.

### Memory Agent

Retrieves relevant persistent context when needed.

### Planning Agent

Receives a compact context containing the information required to
schedule the work.

### Result

``` text
MORNING
- Prepare the Q3 project demo

AFTERNOON
- Continue project documentation

EVENING
- No tasks scheduled

PRIORITY REASONING
- The highest-priority deadline-sensitive work is scheduled first.
```

------------------------------------------------------------------------

## 🛠️ Technology stack

  Layer                Technology
  -------------------- --------------------------------------
  UI                   Streamlit
  Language             Python
  AI                   LLM-based agent orchestration
  Agent architecture   Supervisor + specialized agents
  Tool protocol        MCP
  MCP transport        Streamable HTTP
  Persistence          Database-backed task/memory storage
  Telemetry            AI execution + MCP transport metrics

------------------------------------------------------------------------

## 🔐 MCP security

The MCP server supports API-key authentication for non-local
deployments.

The server validates:

``` text
Authorization: Bearer <MCP_API_KEY>
```

Local development can run without authentication when bound to a local
host.

------------------------------------------------------------------------

## ▶️ Running the project

Create and activate the virtual environment:

``` powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

Install dependencies:

``` powershell
pip install -r requirements.txt
```

Configure environment variables as required by the project.

Start the Streamlit application:

``` powershell
streamlit run streamlit_app.py
```

The MCP server can be started through the project's MCP server entry
point.

------------------------------------------------------------------------

## 🧪 Development philosophy

FocusRoom is intentionally designed around measurable agent execution.

Instead of simply asking:

> "Does the assistant work?"

the project asks:

> **Which agents ran, which tools were called, how much data moved, and
> how many tokens did the request consume?**

That makes optimization an engineering problem rather than guesswork.

------------------------------------------------------------------------

## 📈 Optimization roadmap

Potential next steps include:

-   Further reduce supervisor LLM calls
-   Improve deterministic intent classification
-   Cache repeated task/memory context
-   Parallelize independent task and memory retrieval
-   Reduce MCP response payloads
-   Add structured planning output
-   Measure latency per agent
-   Add prompt-version tracking
-   Add token-cost dashboards
-   Add automated regression tests for routing and token budgets

------------------------------------------------------------------------

## 🎯 Project goal

FocusRoom is not just a task manager with an AI chatbot.

It is an experiment in building a **personal productivity operating
system** where:

``` text
Natural language
      ↓
Intent
      ↓
Agent orchestration
      ↓
Tools + memory
      ↓
Planning
      ↓
Actionable result
```

The long-term goal is simple:

**Less time managing the system. More time doing the work.**

------------------------------------------------------------------------

## 📄 Documentation

  Document            Purpose
  ------------------- ---------------------------------------------
  `README.md`         Project overview and quick start
  `lld.md`            Low-level design and implementation details
  `architecture.md`   System architecture and workflow diagrams

------------------------------------------------------------------------

## ⭐ Why FocusRoom?

Because productivity software should understand **what you are trying to
accomplish**, not just store a list of tasks.

**FocusRoom turns productivity from a collection of tools into a
coordinated system.**
