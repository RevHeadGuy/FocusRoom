import json
import hmac
import os
from typing import Optional

from mcp.server import MCPServer
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from .agent import get_agent
from .orchestrator import ProductivitySupervisor


# MCP SERVER

mcp = MCPServer(
    "Productivity Orchestrator"
)


# MULTI-AGENT SUPERVISOR

supervisor = ProductivitySupervisor()


# RESULT FORMATTER

def format_result(result):

    if isinstance(result, dict):

        return json.dumps(
            result,
            indent=2,
            default=str
        )

    if isinstance(result, list):

        return json.dumps(
            result,
            indent=2,
            default=str
        )

    return str(result)


def success_result(data):

    return format_result({
        "success": True,
        "data": data,
        "error": None
    })


def error_result(message):

    return format_result({
        "success": False,
        "data": None,
        "error": message
    })


def operation_result(result, data_key=None):

    operation = result

    if (
        data_key
        and isinstance(result, dict)
        and data_key in result
    ):
        operation = result.get(data_key)

    if isinstance(operation, dict):

        if operation.get("success") is False:
            return error_result(
                operation.get("error", "Operation failed.")
            )

        if operation.get("error"):
            return error_result(operation["error"])

    if data_key:
        return success_result({
            data_key: result
        })

    return success_result(result)


class APIKeyMiddleware(BaseHTTPMiddleware):

    def __init__(self, app, api_key):
        super().__init__(app)
        self.api_key = api_key

    async def dispatch(self, request: Request, call_next):

        authorization = request.headers.get(
            "authorization",
            ""
        )

        expected = f"Bearer {self.api_key}"

        if not hmac.compare_digest(
            authorization,
            expected
        ):

            return JSONResponse(
                {
                    "success": False,
                    "data": None,
                    "error": "Authentication required."
                },
                status_code=401,
                headers={
                    "WWW-Authenticate": "Bearer"
                }
            )

        return await call_next(request)


def create_app(api_key=None):

    app = mcp.streamable_http_app(
        host="127.0.0.1"
    )

    api_key = api_key or os.getenv("MCP_API_KEY")

    if api_key:
        app.add_middleware(
            APIKeyMiddleware,
            api_key=api_key
        )

    return app


# MAIN MULTI-AGENT TOOL

@mcp.tool()
def productivity_assistant(
    request: str
) -> str:
    """
    Execute a natural-language productivity request
    using the multi-agent orchestration system.
    """

    if not request or not request.strip():

        return error_result("Request cannot be empty.")

    try:

        result = supervisor.run(
            request.strip()
        )

        return success_result({
            "request": request,
            "result": result
        })

    except Exception as error:

        return error_result(str(error))

# CREATE TASK

@mcp.tool()
def create_task(
    title: str,
    priority: str = "medium",
    description: Optional[str] = None,
    due_date: Optional[str] = None,
    project: Optional[str] = None
) -> str:
    """
    Create a productivity task.
    """

    allowed_priorities = {
        "low",
        "medium",
        "high",
        "critical"
    }

    priority = priority.lower().strip()

    if priority not in allowed_priorities:

        return error_result(
            f"Invalid priority: {priority}. "
            f"Allowed priorities: {sorted(allowed_priorities)}"
        )

    if not title or not title.strip():

        return error_result("Task title cannot be empty.")

    try:

        agent = get_agent()

        result = agent.create_task(
            title=title.strip(),
            priority=priority,
            description=description,
            due_date=due_date,
            project=project
        )

        return operation_result(
            result,
            "task"
        )

    except Exception as error:

        return error_result(str(error))

# LIST TASKS

@mcp.tool()
def list_tasks(
    status: Optional[str] = None
) -> str:
    """
    List productivity tasks.
    """

    try:

        agent = get_agent()

        result = agent.list_tasks(
            status=status
        )

        return success_result({
            "tasks": result
        })

    except Exception as error:

        return error_result(str(error))

# UPDATE TASK

@mcp.tool()
def update_task(
    task_id: int,
    title: Optional[str] = None,
    description: Optional[str] = None,
    priority: Optional[str] = None,
    status: Optional[str] = None,
    due_date: Optional[str] = None,
    project: Optional[str] = None
) -> str:
    """
    Update one or more fields of a productivity task.
    """

    try:

        agent = get_agent()

        updates = {
            "title": title,
            "description": description,
            "priority": priority,
            "status": status,
            "due_date": due_date,
            "project": project
        }

        updates = {
            key: value
            for key, value in updates.items()
            if value is not None
        }

        if not updates:

                return error_result(
                    "No fields provided for update."
                )

        if priority is not None:

            allowed_priorities = {
                "low",
                "medium",
                "high",
                "critical"
            }

            if priority.lower() not in (
                allowed_priorities
            ):

                return error_result(
                    f"Invalid priority: {priority}. "
                    f"Allowed priorities: {sorted(allowed_priorities)}"
                )

            updates["priority"] = (
                priority.lower()
            )

        result = agent.update_task(
            task_id,
            **updates
        )

        return operation_result(
            result,
            "task"
        )

    except Exception as error:

        return error_result(str(error))

# COMPLETE TASK

@mcp.tool()
def complete_task(
    task_id: int
) -> str:
    """
    Mark a productivity task as completed.
    """

    try:

        agent = get_agent()

        result = agent.complete_task(
            task_id
        )

        return operation_result(
            result,
            "task"
        )

    except Exception as error:

        return error_result(str(error))


# DELETE TASK

@mcp.tool()
def delete_task(
    task_id: int
) -> str:
    """
    Permanently delete a productivity task.
    """

    try:

        agent = get_agent()

        result = agent.delete_task(
            task_id
        )

        return operation_result(result)

    except Exception as error:

        return error_result(str(error))


# SAVE MEMORY

@mcp.tool()
def save_memory(
    key: str,
    value: str,
    category: str = "general"
) -> str:
    """
    Save persistent user memory.
    """

    if not key or not key.strip():

        return error_result("Memory key cannot be empty.")

    if not value or not value.strip():

        return error_result("Memory value cannot be empty.")

    try:

        agent = get_agent()

        result = agent.save_memory(
            key=key.strip(),
            value=value.strip(),
            category=category.strip()
        )

        return success_result({
            "memory": result
        })

    except Exception as error:

        return error_result(str(error))

# SEARCH MEMORY

@mcp.tool()
def search_memory(
    query: str
) -> str:
    """
    Search persistent user memories.
    """

    if not query or not query.strip():

        return error_result("Memory query cannot be empty.")

    try:

        agent = get_agent()

        result = agent.search_memory(
            query.strip()
        )

        return success_result({
            "memories": result
        })

    except Exception as error:

        return error_result(str(error))

# DAILY PLAN

@mcp.tool()
def daily_plan() -> str:
    """
    Generate today's productivity plan.
    """

    try:

        agent = get_agent()

        result = agent.create_daily_plan()

        return success_result({
            "plan": result
        })

    except Exception as error:

        return error_result(str(error))

# PRODUCTIVITY REPORT

@mcp.tool()
def productivity_report() -> str:
    """
    Generate a productivity report.
    """

    try:

        agent = get_agent()

        result = agent.productivity_report()

        return success_result({
            "report": result
        })

    except Exception as error:

        return error_result(str(error))

# SERVER START

if __name__ == "__main__":

    import uvicorn

    print()
    print("=" * 55)
    print(" PRODUCTIVITY MCP SERVER")
    print("=" * 55)
    print()
    print("Transport : Streamable HTTP")
    host = os.getenv("MCP_HOST", "127.0.0.1")
    port = int(os.getenv("MCP_PORT", "8000"))
    api_key = os.getenv("MCP_API_KEY")

    if host not in {
        "127.0.0.1",
        "localhost",
        "::1"
    } and not api_key:
        raise RuntimeError(
            "MCP_API_KEY is required when MCP_HOST is not local."
        )

    print(f"Host      : {host}")

    print(f"Port      : {port}")
    print(
        "Authentication: "
        + ("enabled" if api_key else "disabled")
    )
    print("Endpoint  : /mcp")
    print()
    print("MCP Tools:")
    print()
    print("1. productivity_assistant")
    print("2. create_task")
    print("3. list_tasks")
    print("4. update_task")
    print("5. complete_task")
    print("6. delete_task")
    print("7. save_memory")
    print("8. search_memory")
    print("9. daily_plan")
    print("10. productivity_report")
    print()

    uvicorn.run(
        create_app(api_key),
        host=host,
        port=port
    )