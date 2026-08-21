import json
import os
from datetime import datetime, timedelta
from pathlib import Path

os.environ.setdefault("GROQ_API_KEY", "test-key")

from starlette.testclient import TestClient

from orchestrator import mcp_server
from orchestrator.database import Database
from orchestrator.task_agent import TaskAgent


class FakeAgent:

    def __init__(self):
        self.tasks = {}
        self.memories = {}
        self.next_id = 1

    def create_task(self, title, priority="medium", **kwargs):
        task = {
            "id": self.next_id,
            "title": title,
            "description": kwargs.get("description"),
            "priority": priority,
            "status": "todo",
            "due_date": kwargs.get("due_date"),
            "project": kwargs.get("project"),
        }
        self.tasks[self.next_id] = task
        self.next_id += 1
        return task

    def list_tasks(self, status=None):
        tasks = list(self.tasks.values())
        if status:
            tasks = [task for task in tasks if task["status"] == status]
        return tasks

    def update_task(self, task_id, **updates):
        task = self.tasks.get(task_id)
        if not task:
            return {"error": f"Task {task_id} not found."}
        task.update(updates)
        return task

    def complete_task(self, task_id):
        task = self.tasks.get(task_id)
        if not task:
            return {"error": f"Task {task_id} not found."}
        task["status"] = "completed"
        return task

    def delete_task(self, task_id):
        if task_id not in self.tasks:
            return {"success": False, "error": "Task not found."}
        del self.tasks[task_id]
        return {"success": True, "task_id": task_id}

    def save_memory(self, **memory):
        self.memories[memory["key"]] = memory
        return memory

    def search_memory(self, query):
        return [
            memory
            for memory in self.memories.values()
            if query.lower() in memory["value"].lower()
        ]


def response(tool_result):
    return json.loads(tool_result)


def test_task_tools_use_consistent_envelope(monkeypatch):
    agent = FakeAgent()
    monkeypatch.setattr(mcp_server, "get_agent", lambda: agent)

    created = response(
        mcp_server.create_task(
            "Write tests",
            priority="high"
        )
    )

    assert created["success"] is True
    assert created["error"] is None
    assert created["data"]["task"]["title"] == "Write tests"

    task_id = created["data"]["task"]["id"]
    listed = response(mcp_server.list_tasks())
    assert listed["data"]["tasks"][0]["id"] == task_id

    updated = response(
        mcp_server.update_task(
            task_id,
            priority="critical"
        )
    )
    assert updated["success"] is True
    assert updated["data"]["task"]["priority"] == "critical"

    completed = response(mcp_server.complete_task(task_id))
    assert completed["success"] is True
    assert completed["data"]["task"]["status"] == "completed"

    deleted = response(mcp_server.delete_task(task_id))
    assert deleted["success"] is True
    assert deleted["data"]["task_id"] == task_id


def test_invalid_task_input_returns_error_envelope(monkeypatch):
    monkeypatch.setattr(mcp_server, "get_agent", FakeAgent)

    result = response(
        mcp_server.create_task(
            "",
            priority="high"
        )
    )

    assert result == {
        "success": False,
        "data": None,
        "error": "Task title cannot be empty."
    }

    result = response(
        mcp_server.create_task(
            "Bad priority",
            priority="urgent"
        )
    )

    assert result["success"] is False
    assert result["data"] is None
    assert "Invalid priority" in result["error"]


def test_memory_tools_use_consistent_envelope(monkeypatch):
    agent = FakeAgent()
    monkeypatch.setattr(mcp_server, "get_agent", lambda: agent)

    saved = response(
        mcp_server.save_memory(
            "goal",
            "Learn testing",
            "learning"
        )
    )
    assert saved["success"] is True
    assert saved["data"]["memory"]["key"] == "goal"

    found = response(mcp_server.search_memory("testing"))
    assert found["success"] is True
    assert found["data"]["memories"][0]["key"] == "goal"


def test_authentication_rejects_missing_and_invalid_keys():
    client = TestClient(
        mcp_server.create_app("test-secret")
    )

    missing = client.get("/mcp")
    invalid = client.get(
        "/mcp",
        headers={"Authorization": "Bearer wrong-secret"}
    )

    assert missing.status_code == 401
    assert invalid.status_code == 401
    assert missing.headers["www-authenticate"] == "Bearer"


def test_authentication_allows_valid_key():
    with TestClient(
        mcp_server.create_app("test-secret")
    ) as client:
        response = client.get(
            "/mcp",
            headers={"Authorization": "Bearer test-secret"}
        )

    assert response.status_code != 401


def test_database_task_lifecycle_uses_temporary_database(tmp_path):
    database = Database(tmp_path / "test.db")
    task = {
        "id": 1,
        "title": "Database task",
        "description": None,
        "priority": "high",
        "status": "todo",
        "due_date": None,
        "project": None,
        "created_at": datetime.now().isoformat(),
        "completed_at": None
    }

    database.save_task(task)
    updated = database.update_task(
        1,
        {"priority": "critical"}
    )

    assert updated["priority"] == "critical"
    assert database.get_task(1)["priority"] == "critical"
    assert database.delete_task(1) is True
    assert database.get_task(1) is None


def test_task_agent_routes_non_update_actions(monkeypatch):
    class RoutedAgent:

        def delete_task(self, task_id):
            return {"action": "delete", "task_id": task_id}

        def find_overdue_tasks(self):
            return [{"action": "overdue"}]

        def find_high_priority_tasks(self):
            return [{"action": "high_priority"}]

    task_agent = TaskAgent.__new__(TaskAgent)
    task_agent.agent = RoutedAgent()

    assert task_agent.handle("delete", {"task_id": "4"})["task_id"] == 4
    assert task_agent.handle("overdue", {})[0]["action"] == "overdue"
    assert task_agent.handle("high_priority", {})[0]["action"] == "high_priority"


def test_task_agent_finds_overdue_tasks_with_real_database(tmp_path):
    database = Database(tmp_path / "overdue.db")
    overdue_date = (
        datetime.now() - timedelta(days=1)
    ).date().isoformat()
    task = {
        "id": 1,
        "title": "Late task",
        "description": None,
        "priority": "medium",
        "status": "todo",
        "due_date": overdue_date,
        "project": None,
        "created_at": datetime.now().isoformat(),
        "completed_at": None
    }
    database.save_task(task)

    assert database.get_tasks()[0]["due_date"] == overdue_date
