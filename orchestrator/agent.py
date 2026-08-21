import os
from datetime import datetime

from dotenv import load_dotenv
from groq import Groq

from .database import Database


load_dotenv()


class ProductivityOrchestrator:

    def __init__(self):

        self.db = Database()

        api_key = os.getenv("GROQ_API_KEY")

        if not api_key:
            raise ValueError(
                "GROQ_API_KEY is missing from .env"
            )

        self.client = Groq(
            api_key=api_key
        )

        self.model = os.getenv(
            "GROQ_MODEL",
            "openai/gpt-oss-120b"
        )

        print(
            "[SYSTEM] Initializing Productivity Orchestrator..."
        )

        print(
            "[SYSTEM] Productivity Orchestrator ready."
        )

    # ==================================================
    # LLM
    # ==================================================

    def call_llm(self, messages):

        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=0
        )

        return response.choices[0].message.content

    # ==================================================
    # JSON CLEANER
    # ==================================================

    def clean_json(self, text):

        text = text.strip()

        if text.startswith("```"):

            lines = text.splitlines()

            lines = [
                line
                for line in lines
                if not line.strip().startswith("```")
            ]

            text = "\n".join(lines)

        start = text.find("{")
        end = text.rfind("}")

        if start != -1 and end != -1:

            text = text[start:end + 1]

        return text

    # ==================================================
    # CREATE TASK
    # ==================================================

    def create_task(
        self,
        title,
        description=None,
        priority="medium",
        due_date=None,
        project=None
    ):

        allowed_priorities = {
            "low",
            "medium",
            "high",
            "critical"
        }

        priority = str(priority).lower()

        if priority not in allowed_priorities:

            return {
                "error":
                    f"Invalid priority: {priority}"
            }

        if not title or not title.strip():

            return {
                "error":
                    "Task title cannot be empty."
            }

        # Generate next task ID

        existing_tasks = self.db.get_tasks()

        next_id = 1

        if existing_tasks:

            next_id = max(
                task["id"]
                for task in existing_tasks
            ) + 1

        task = {
            "id": next_id,
            "title": title.strip(),
            "description": description,
            "priority": priority,
            "status": "todo",
            "due_date": due_date,
            "project": project,
            "created_at":
                datetime.now().isoformat(),
            "completed_at": None
        }

        self.db.save_task(task)

        # IMPORTANT:
        # Return the raw task.
        # mcp_server.py handles the success wrapper.

        return self.db.get_task(next_id)

    # ==================================================
    # LIST TASKS
    # ==================================================

    def list_tasks(self, status=None):

        return self.db.get_tasks(
            status=status
        )

    # ==================================================
    # GET TASK
    # ==================================================

    def get_task(self, task_id):

        return self.db.get_task(
            task_id
        )

    # ==================================================
    # UPDATE TASK
    # ==================================================

    def update_task(
        self,
        task_id,
        **updates
    ):

        task = self.db.get_task(
            task_id
        )

        if not task:

            return {
                "error":
                    f"Task {task_id} not found."
            }

        allowed_fields = {
            "title",
            "description",
            "priority",
            "status",
            "due_date",
            "project"
        }

        clean_updates = {
            key: value
            for key, value in updates.items()
            if key in allowed_fields
            and value is not None
        }

        if not clean_updates:

            return {
                "error":
                    "No valid fields provided for update."
            }

        # ----------------------------------------------
        # Validate priority
        # ----------------------------------------------

        if "priority" in clean_updates:

            allowed_priorities = {
                "low",
                "medium",
                "high",
                "critical"
            }

            priority = str(
                clean_updates["priority"]
            ).lower()

            if priority not in allowed_priorities:

                return {
                    "error":
                        f"Invalid priority: {priority}"
                }

            clean_updates[
                "priority"
            ] = priority

        # ----------------------------------------------
        # Validate status
        # ----------------------------------------------

        if "status" in clean_updates:

            allowed_statuses = {
                "todo",
                "in_progress",
                "completed"
            }

            status = str(
                clean_updates["status"]
            ).lower()

            if status not in allowed_statuses:

                return {
                    "error":
                        f"Invalid status: {status}"
                }

            clean_updates[
                "status"
            ] = status

        # ----------------------------------------------
        # Update database
        # ----------------------------------------------

        updated_task = self.db.update_task(
            task_id,
            clean_updates
        )

        if not updated_task:

            return {
                "error":
                    "Task update failed."
            }

        # Return raw task.
        # MCP server handles wrapper.

        return updated_task

    # ==================================================
    # COMPLETE TASK
    # ==================================================

    def complete_task(
        self,
        task_id
    ):

        task = self.db.get_task(
            task_id
        )

        if not task:

            return {
                "error":
                    f"Task {task_id} not found."
            }

        updated_task = self.db.update_task(
            task_id,
            {
                "status": "completed"
            }
        )

        if not updated_task:

            return {
                "error":
                    "Task completion failed."
            }

        # Add completion timestamp

        updated_task[
            "completed_at"
        ] = datetime.now().isoformat()

        self.db.save_task(
            updated_task
        )

        # Get final database record

        updated_task = self.db.get_task(
            task_id
        )

        return updated_task

    # ==================================================
    # DELETE TASK
    # ==================================================

    def delete_task(
        self,
        task_id
    ):

        task = self.db.get_task(
            task_id
        )

        if not task:

            return {
                "success": False,
                "error":
                    f"Task {task_id} not found."
            }

        deleted = self.db.delete_task(
            task_id
        )

        if not deleted:

            return {
                "success": False,
                "error":
                    "Task deletion failed."
            }

        return {
            "success": True,
            "task_id": task_id,
            "message":
                "Task deleted successfully"
        }

    # ==================================================
    # SAVE MEMORY
    # ==================================================

    def save_memory(
        self,
        key,
        value,
        category="general"
    ):

        memory = {
            "key": key,
            "value": value,
            "category": category,
            "updated_at":
                datetime.now().isoformat()
        }

        self.db.save_memory(
            memory
        )

        return memory

    # ==================================================
    # SEARCH MEMORY
    # ==================================================

    def search_memory(
        self,
        query
    ):

        return self.db.search_memory(
            query
        )

    # ==================================================
    # GET MEMORIES
    # ==================================================

    def get_memories(self):

        return self.db.get_memories()

    # ==================================================
    # OVERDUE TASKS
    # ==================================================

    def find_overdue_tasks(self):

        tasks = self.db.get_tasks()

        today = datetime.now().date()

        overdue = []

        for task in tasks:

            if task["status"] == "completed":
                continue

            due_date = task.get(
                "due_date"
            )

            if not due_date:
                continue

            try:

                date_value = datetime.fromisoformat(
                    due_date
                ).date()

            except ValueError:

                try:

                    date_value = datetime.strptime(
                        due_date,
                        "%Y-%m-%d"
                    ).date()

                except ValueError:

                    continue

            if date_value < today:

                overdue.append(task)

        return overdue

    # ==================================================
    # HIGH PRIORITY TASKS
    # ==================================================

    def find_high_priority_tasks(self):

        tasks = self.db.get_tasks()

        return [
            task
            for task in tasks
            if task["priority"]
            in {
                "high",
                "critical"
            }
            and task["status"]
            != "completed"
        ]

    # ==================================================
    # DAILY PLAN
    # ==================================================

    def create_daily_plan(self):

        tasks = self.db.get_tasks()

        active_tasks = [
            task
            for task in tasks
            if task["status"]
            != "completed"
        ]

        memories = self.db.get_memories()

        return {
            "date":
                datetime.now()
                .date()
                .isoformat(),
            "tasks":
                active_tasks,
            "memories":
                memories
        }

    # ==================================================
    # PRODUCTIVITY REPORT
    # ==================================================

    def productivity_report(self):

        tasks = self.db.get_tasks()

        total_tasks = len(tasks)

        completed_tasks = sum(
            1
            for task in tasks
            if task["status"]
            == "completed"
        )

        active_tasks = sum(
            1
            for task in tasks
            if task["status"]
            != "completed"
        )

        overdue_tasks = len(
            self.find_overdue_tasks()
        )

        high_priority_active = len(
            self.find_high_priority_tasks()
        )

        completion_rate = 0

        if total_tasks > 0:

            completion_rate = (
                completed_tasks
                / total_tasks
            ) * 100

        memories = self.db.get_memories()

        projects = {
            task["project"]
            for task in tasks
            if task.get("project")
        }

        return {
            "total_tasks":
                total_tasks,

            "completed_tasks":
                completed_tasks,

            "active_tasks":
                active_tasks,

            "overdue_tasks":
                overdue_tasks,

            "high_priority_active_tasks":
                high_priority_active,

            "completion_rate":
                round(
                    completion_rate,
                    2
                ),

            "total_projects":
                len(projects),

            "memory_items":
                len(memories)
        }


# ==================================================
# SINGLETON
# ==================================================

_agent = None


def get_agent():

    global _agent

    if _agent is None:

        _agent = ProductivityOrchestrator()

    return _agent


# ==================================================
# DIRECT TERMINAL MODE
# ==================================================

if __name__ == "__main__":

    agent = get_agent()

    print()
    print("=" * 40)
    print(" PRODUCTIVITY ORCHESTRATOR")
    print("=" * 40)
    print()
    print("Type 'exit' to stop.")

    while True:

        user = input("\nYou: ").strip()

        if user.lower() == "exit":

            print("Goodbye!")

            break

        try:

            result = agent.call_llm(
                [
                    {
                        "role": "user",
                        "content": user
                    }
                ]
            )

            print("\nAgent:")
            print(result)

        except Exception as error:

            print(
                f"\n[ERROR] {error}"
            )