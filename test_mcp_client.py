import asyncio
import json
import os

import httpx2
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
from dotenv import load_dotenv


load_dotenv()

MCP_PORT = os.getenv("MCP_PORT", "8000")
MCP_API_KEY = os.getenv("MCP_API_KEY")
URL = f"http://127.0.0.1:{MCP_PORT}/mcp"


def get_result(result):
    """Extract JSON result from MCP response."""

    if not result.content:
        return None

    text = result.content[0].text

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


async def cleanup_test_tasks(session):

    result = await session.call_tool(
        "list_tasks",
        {}
    )

    response = get_result(result)

    if not response.get("success"):
        return

    tasks = response.get("data", {}).get(
        "tasks",
        []
    )

    for task in tasks:

        if task.get("title") == "MCP Integration Test":

            await session.call_tool(
                "delete_task",
                {
                    "task_id": task["id"]
                }
            )


async def main():

    print("=" * 55)
    print(" MCP FULL INTEGRATION TEST")
    print("=" * 55)

    headers = {}

    if MCP_API_KEY:
        headers["Authorization"] = (
            f"Bearer {MCP_API_KEY}"
        )

    async with httpx2.AsyncClient(
        headers=headers
    ) as http_client:

        async with streamable_http_client(
            URL,
            http_client=http_client
        ) as (
            read_stream,
            write_stream,
        ):

            session = ClientSession(
                read_stream,
                write_stream
            )

            await session.__aenter__()

            print("\n[1] Connecting to MCP server...")

            await session.initialize()

            print("✓ Connected")

            print("\n[2] Discovering MCP tools...")

            tools = await session.list_tools()

            print(
                f"✓ {len(tools.tools)} tools discovered"
            )

            for tool in tools.tools:

                print(
                    f"   - {tool.name}"
                )

            await cleanup_test_tasks(session)

            print("\n[3] CREATE TASK")

            result = await session.call_tool(
                "create_task",
                {
                    "title":
                        "MCP Integration Test",
                    "priority":
                        "high"
                }
            )

            data = get_result(result)

            print("✓ Create response:")
            print(json.dumps(
                data,
                indent=2
            ))

            task = data.get("data", {}).get(
                "task",
                {}
            )

            task_id = task.get(
                "id"
            )

            if not task_id:

                print(
                    "✗ Could not find task ID"
                )

                return

            print(
                f"✓ Created task ID: {task_id}"
            )

            print("\n[4] LIST TASKS")

            result = await session.call_tool(
                "list_tasks",
                {}
            )

            data = get_result(result)

            tasks = data.get("data", {}).get(
                "tasks",
                []
            )

            found = any(
                task["id"] == task_id
                for task in tasks
            )

            if found:

                print(
                    f"✓ Task {task_id} found"
                )

            else:

                print(
                    f"✗ Task {task_id} not found"
                )

            print("\n[5] UPDATE TASK")

            result = await session.call_tool(
                "update_task",
                {
                    "task_id":
                        task_id,
                    "priority":
                        "critical"
                }
            )

            data = get_result(result)

            print(
                json.dumps(
                    data,
                    indent=2
                )
            )

            if data.get("success"):

                print(
                    f"✓ Task {task_id} updated"
                )

            else:

                print(
                    "✗ Update failed"
                )

            print("\n[6] COMPLETE TASK")

            result = await session.call_tool(
                "complete_task",
                {
                    "task_id":
                        task_id
                }
            )

            data = get_result(result)

            if data.get("success"):

                print(
                    f"✓ Task {task_id} completed"
                )

            else:

                print(
                    "✗ Complete failed"
                )

            print("\n[7] DELETE TASK")

            result = await session.call_tool(
                "delete_task",
                {
                    "task_id":
                        task_id
                }
            )

            data = get_result(result)

            if data.get("success"):

                print(
                    f"✓ Task {task_id} deleted"
                )

            else:

                print(
                    "✗ Delete failed"
                )

            print("\n[8] SAVE MEMORY")

            result = await session.call_tool(
                "save_memory",
                {
                    "key":
                        "mcp_test_goal",
                    "value":
                        "Testing MCP integration",
                    "category":
                        "testing"
                }
            )

            data = get_result(result)

            if data.get("success"):

                print(
                    "✓ Memory saved"
                )

            else:

                print(
                    "✗ Memory save failed"
                )

            print("\n[9] SEARCH MEMORY")

            result = await session.call_tool(
                "search_memory",
                {
                    "query":
                        "MCP integration"
                }
            )

            data = get_result(result)

            if data.get("success"):

                print(
                    "✓ Memory search completed"
                )

                print(
                    json.dumps(
                        data,
                        indent=2
                    )
                )

            else:

                print(
                    "✗ Memory search failed"
                )

            print("\n[10] DAILY PLAN")

            result = await session.call_tool(
                "daily_plan",
                {}
            )

            data = get_result(result)

            if data.get("success"):

                print(
                    "✓ Daily plan generated"
                )

            else:

                print(
                    "✗ Daily plan failed"
                )

            print(
                "\n[11] PRODUCTIVITY REPORT"
            )

            result = await session.call_tool(
                "productivity_report",
                {}
            )

            data = get_result(result)

            if data.get("success"):

                print(
                    "✓ Productivity report generated"
                )

                print(
                    json.dumps(
                        data,
                        indent=2
                    )
                )

            else:

                print(
                    "✗ Productivity report failed"
                )

            print(
                "\n[12] MULTI-AGENT REQUEST"
            )

            request = (
                "Plan my day and "
                "prioritize my MCP learning"
            )

            result = await session.call_tool(
                "productivity_assistant",
                {
                    "request":
                        request
                }
            )

            data = get_result(result)

            if data.get("success"):

                print(
                    "✓ Multi-agent request completed"
                )

                print(
                    json.dumps(
                        data,
                        indent=2
                    )
                )

            else:

                print(
                    "✗ Multi-agent request failed"
                )

            print("\n" + "=" * 55)
            print(" MCP INTEGRATION TEST COMPLETE")
            print("=" * 55)

            await session.__aexit__(
                None,
                None,
                None
            )


if __name__ == "__main__":

    asyncio.run(
        main()
    )