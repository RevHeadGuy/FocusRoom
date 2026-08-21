from .agent import get_agent


class TaskAgent:

    def __init__(self):
        self.agent = get_agent()

    def handle(self, action, arguments):

        action = action.lower().strip()

        # ==================================================
        # ACTION ALIASES
        # ==================================================

        aliases = {

            # CREATE
            "create task": "create",
            "create tasks": "create",
            "add task": "create",
            "add tasks": "create",

            # LIST
            "list tasks": "list",
            "show tasks": "list",
            "get tasks": "list",

            # COMPLETE
            "complete task": "complete",
            "complete tasks": "complete",
            "finish task": "complete",
            "finish tasks": "complete",

            # DELETE
            "delete task": "delete",
            "delete tasks": "delete",
            "remove task": "delete",
            "remove tasks": "delete",

            # UPDATE
            "update task": "update",
            "update tasks": "update",
            "edit task": "update",
            "modify task": "update",
            "change task": "update",

            # OVERDUE
            "overdue tasks": "overdue",
            "show overdue tasks": "overdue",

            # HIGH PRIORITY
            "high priority tasks": "high_priority",
            "show high priority tasks": "high_priority"
        }

        action = aliases.get(
            action,
            action
        )

        # ==================================================
        # CREATE TASK
        # ==================================================

        if action == "create":

            title = (
                arguments.get("title")
                or arguments.get("name")
                or arguments.get("task_name")
            )

            if not title:

                return {
                    "success": False,
                    "error": "Task title is missing."
                }

            priority = arguments.get(
                "priority",
                "medium"
            )

            return self.agent.create_task(

                title=title,

                priority=priority,

                description=arguments.get(
                    "description"
                ),

                due_date=arguments.get(
                    "due_date"
                ),

                project=arguments.get(
                    "project"
                )
            )

        # ==================================================
        # LIST TASKS
        # ==================================================

        if action == "list":

            return self.agent.list_tasks(
                arguments.get("status")
            )

        # ==================================================
        # COMPLETE TASK
        # ==================================================

        if action == "complete":

            task_id = (
                arguments.get("task_id")
                or arguments.get("id")
            )

            if not task_id:

                return {
                    "success": False,
                    "error": "Task ID is missing."
                }

            return self.agent.complete_task(
                task_id
            )

        # ==================================================
        # UPDATE TASK
        # ==================================================

        if action == "update":

            task_id = (
                arguments.get("task_id")
                or arguments.get("id")
            )

            if not task_id:

                return {
                    "success": False,
                    "error": "Task ID is missing."
                }

            try:
                task_id = int(task_id)

            except (TypeError, ValueError):

                return {
                    "success": False,
                    "error": "Task ID must be an integer."
                }

            updates = {}

            for field in [
                "title",
                "description",
                "priority",
                "status",
                "due_date",
                "project"
            ]:

                if field in arguments:
                    updates[field] = arguments[field]

            return self.agent.update_task(
                task_id,
                **updates
            )

        # ==================================================
        # DELETE TASK
        # ==================================================

        if action == "delete":

            task_id = (
                arguments.get("task_id")
                or arguments.get("id")
            )

            if not task_id:

                return {
                    "success": False,
                    "error": "Task ID is missing."
                }

            try:
                task_id = int(task_id)

            except (TypeError, ValueError):

                return {
                    "success": False,
                    "error": "Task ID must be an integer."
                }

            return self.agent.delete_task(
                task_id
            )

        # ==================================================
        # OVERDUE TASKS
        # ==================================================

        if action == "overdue":

            return self.agent.find_overdue_tasks()

        # ==================================================
        # HIGH PRIORITY TASKS
        # ==================================================

        if action == "high_priority":

            return self.agent.find_high_priority_tasks()

        # ==================================================
        # UNKNOWN ACTION
        # ==================================================

        return {
            "success": False,
            "error":
                f"Unknown task action: {action}"
        }