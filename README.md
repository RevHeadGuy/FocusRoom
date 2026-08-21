# FocusRoom | Productivity Agent

A personal productivity workspace built with Python, Streamlit, Groq, SQLite, and MCP. It combines task management, daily planning, persistent memories, a multi-agent supervisor, and optional email reminders in one project.

## Features

- Streamlit productivity dashboard
- Create, list, filter, and complete tasks
- Task priorities, due dates, projects, and statuses
- Persistent SQLite storage in `productivity.db`
- Daily plans and productivity reports
- Save and search personal memories
- Groq-powered productivity assistant
- Multi-agent supervisor for task, memory, and planning requests
- MCP server with HTTP tools for external clients
- Optional automatic email reminders

## Requirements

- Python 3.10 or newer
- A Groq API key for the AI features
- Gmail SMTP credentials or another SMTP provider for email reminders

## Setup

### 1. Create a virtual environment

PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

If PowerShell blocks script execution for the current session:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
.\.venv\Scripts\Activate.ps1
```

### 2. Install dependencies

```powershell
python -m pip install -r requirements.txt
```

### 3. Configure environment variables

Copy `.env.example` to `.env` and fill in the values:

```powershell
Copy-Item .env.example .env
```

Required for the Groq-backed agent:

```dotenv
GROQ_API_KEY=your_groq_api_key
GROQ_MODEL=openai/gpt-oss-120b
```

Optional MCP configuration:

```dotenv
MCP_HOST=127.0.0.1
MCP_PORT=8000
MCP_API_KEY=local_or_remote_api_key
```

For email reminders:

```dotenv
EMAIL_SENDER=your_email@gmail.com
EMAIL_RECIPIENT=recipient@example.com
EMAIL_PASSWORD=your_smtp_or_app_password
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
```

Do not commit `.env` or API credentials. They are excluded by `.gitignore`.

## Run the Streamlit app

```powershell
streamlit run streamlit_app.py
```

The app provides these sections:

- **Overview** - task metrics, active work, daily snapshot, and completion progress
- **Tasks** - create and filter tasks, then mark tasks complete
- **Plan** - view the current daily plan and productivity report
- **Memory** - save and search persistent context
- **Assistant** - send natural-language requests to the productivity supervisor

## Run the MCP server

Start the Streamable HTTP MCP server with:

```powershell
python -m orchestrator.mcp_server
```

By default, it runs on `http://127.0.0.1:8000/mcp`.

The server exposes tools for:

- `productivity_assistant`
- `create_task`
- `list_tasks`
- `update_task`
- `complete_task`
- `delete_task`
- `save_memory`
- `search_memory`
- `daily_plan`
- `productivity_report`

When binding the MCP server to a non-local host, set `MCP_API_KEY`. Remote requests must use a bearer token:

```text
Authorization: Bearer <MCP_API_KEY>
```

## Run reminders

The reminder worker checks upcoming tasks and sends configured email notifications:

```powershell
python reminder_worker.py
```

The reminder schedule is configured in the worker and supports reminders at 24 hours, 1 hour, and 15 minutes before a task is due. Email reminders require valid SMTP settings in `.env`.

## Run tests

Use the project virtual environment so pytest is available:

```powershell
.\.venv\Scripts\python -m pytest -q
```

To run a specific test file:

```powershell
.\.venv\Scripts\python -m pytest -q test_multi_agent.py
```

To check Python syntax without starting the app:

```powershell
.\.venv\Scripts\python -m compileall streamlit_app.py orchestrator
```

## Project structure

```text
Productivity_Agent/
|-- streamlit_app.py              # Streamlit user interface
|-- requirements.txt              # Python dependencies
|-- .env.example                  # Environment variable template
|-- productivity.db               # Local SQLite database, generated locally
|-- reminder_service.py           # Reminder service implementation
|-- reminder_worker.py            # Continuous reminder worker
|-- orchestrator/
|   |-- agent.py                  # Core task, memory, plan, and report logic
|   |-- database.py               # SQLite persistence layer
|   |-- orchestrator.py           # Multi-agent supervisor
|   |-- mcp_server.py             # MCP HTTP server and tools
|   |-- memory_agent.py           # Memory agent adapter
|   |-- planning_agent.py         # Planning agent adapter
|   |-- task_agent.py             # Task agent adapter
|-- test_*.py                     # Project tests
```

## Data and security notes

- Tasks and memories are stored locally in SQLite.
- `.env` contains secrets and must remain private.
- For Gmail, use an app password where required instead of your primary account password.
- The MCP API key is required when the server is exposed beyond localhost.
- Back up `productivity.db` if the local task and memory history is important.

## Troubleshooting

### `pytest` is not recognized

Run pytest through the virtual environment:

```powershell
.\.venv\Scripts\python -m pytest -q
```

### The app starts but the assistant is unavailable

Check that `.env` exists and contains a valid `GROQ_API_KEY`, then restart Streamlit.

### Streamlit reports `missing ScriptRunContext`

This warning appears when importing a Streamlit module directly with `python -c`. Start the application with `streamlit run streamlit_app.py` for normal operation.

### Compilation works but tests fail during collection

A collection error means pytest could not finish importing the tests. Read the first reported exception and fix that dependency or constructor mismatch before evaluating the remaining tests.
