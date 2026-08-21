import json

from .agent import get_agent
from .task_agent import TaskAgent
from .memory_agent import MemoryAgent
from .planning_agent import PlanningAgent


class ProductivitySupervisor:

    def __init__(self):

        self.agent = get_agent()

        self.task_agent = TaskAgent()
        self.memory_agent = MemoryAgent()
        self.planning_agent = PlanningAgent()

    # SUPERVISOR DECISION

    def decide_agent(self, user_message):

        prompt = """
You are the Supervisor Agent of a
multi-agent productivity system.

Your job is to select the correct specialized
agent and exact action.

AVAILABLE AGENTS:

TASK_AGENT:
- create
- list
- update
- complete
- delete
- overdue
- high_priority

MEMORY_AGENT:
- save
- search

PLANNING_AGENT:
- daily
- weekly
- report


==================================================
TASK ACTION RULES
==================================================

CREATE:

create, add, make, new task
→ create


LIST:

show, list, get, display my tasks
→ list


UPDATE:

update, edit, modify, change
→ update


COMPLETE:

complete, finish, mark completed,
mark as done
→ complete


DELETE:

delete, remove, erase, discard
→ delete


OVERDUE:

overdue tasks
→ overdue


HIGH PRIORITY:

high priority tasks
→ high_priority


==================================================
IMPORTANT DELETE VS COMPLETE RULE
==================================================

"Delete task 8"
MUST be:

{
    "agent": "TASK_AGENT",
    "action": "delete",
    "arguments": {
        "task_id": 8
    }
}

"Remove task 8"
MUST be:

{
    "agent": "TASK_AGENT",
    "action": "delete",
    "arguments": {
        "task_id": 8
    }
}

"Complete task 8"
MUST be:

{
    "agent": "TASK_AGENT",
    "action": "complete",
    "arguments": {
        "task_id": 8
    }
}

"Finish task 8"
MUST be:

{
    "agent": "TASK_AGENT",
    "action": "complete",
    "arguments": {
        "task_id": 8
    }
}


==================================================
UPDATE RULES
==================================================

"Change task 7 priority to critical"

→

{
    "agent": "TASK_AGENT",
    "action": "update",
    "arguments": {
        "task_id": 7,
        "priority": "critical"
    }
}


"Update task 7 title to Finish MCP"

→

{
    "agent": "TASK_AGENT",
    "action": "update",
    "arguments": {
        "task_id": 7,
        "title": "Finish MCP"
    }
}


"Rename task 7 to Finish MCP project"

→

{
    "agent": "TASK_AGENT",
    "action": "update",
    "arguments": {
        "task_id": 7,
        "title": "Finish MCP project"
    }
}


"Change task 7 due date to 2026-08-20"

→

{
    "agent": "TASK_AGENT",
    "action": "update",
    "arguments": {
        "task_id": 7,
        "due_date": "2026-08-20"
    }
}


==================================================
MEMORY RULES
==================================================

Remember, store, save
→ save

Recall, search, find, remember
→ search


==================================================
PLANNING RULES
==================================================

"Plan my day"
"Daily plan"
→ daily

"Plan my week"
"Weekly plan"
→ weekly

"Productivity report"
"Show my productivity"
→ report


==================================================
CREATE TASK FORMAT
==================================================

{
    "agent": "TASK_AGENT",
    "action": "create",
    "arguments": {
        "title": "...",
        "description": null,
        "priority": "low|medium|high|critical",
        "due_date": null,
        "project": null
    }
}


==================================================
LIST TASK FORMAT
==================================================

{
    "agent": "TASK_AGENT",
    "action": "list",
    "arguments": {
        "status": null
    }
}


==================================================
UPDATE TASK FORMAT
==================================================

{
    "agent": "TASK_AGENT",
    "action": "update",
    "arguments": {
        "task_id": 7,
        "title": null,
        "description": null,
        "priority": null,
        "status": null,
        "due_date": null,
        "project": null
    }
}

Only include fields that actually need
to be changed.


==================================================
COMPLETE TASK FORMAT
==================================================

{
    "agent": "TASK_AGENT",
    "action": "complete",
    "arguments": {
        "task_id": 7
    }
}


==================================================
DELETE TASK FORMAT
==================================================

{
    "agent": "TASK_AGENT",
    "action": "delete",
    "arguments": {
        "task_id": 7
    }
}


==================================================
MEMORY SAVE FORMAT
==================================================

{
    "agent": "MEMORY_AGENT",
    "action": "save",
    "arguments": {
        "key": "...",
        "value": "...",
        "category": "..."
    }
}


==================================================
MEMORY SEARCH FORMAT
==================================================

{
    "agent": "MEMORY_AGENT",
    "action": "search",
    "arguments": {
        "query": "..."
    }
}


==================================================
DAILY PLAN FORMAT
==================================================

{
    "agent": "PLANNING_AGENT",
    "action": "daily",
    "arguments": {}
}


==================================================
WEEKLY PLAN FORMAT
==================================================

{
    "agent": "PLANNING_AGENT",
    "action": "weekly",
    "arguments": {}
}


==================================================
REPORT FORMAT
==================================================

{
    "agent": "PLANNING_AGENT",
    "action": "report",
    "arguments": {}
}


==================================================
STRICT RULES
==================================================

Return ONLY valid JSON.

Never return:
"daily planning"

Use:
"daily"

Never return:
"productivity reports"

Use:
"report"

Never return:
"search memories"

Use:
"search"

Never return:
"create tasks"

Use:
"create"

Never return:
"delete task"

as the action.

Use:
"delete"

Never return:
"update task"

as the action.

Use:
"update"

The action must ALWAYS be one of:

create
list
update
complete
delete
overdue
high_priority
save
search
daily
weekly
report
"""

        response = self.agent.call_llm(
            [
                {
                    "role": "system",
                    "content": prompt
                },
                {
                    "role": "user",
                    "content": user_message
                }
            ]
        )

        response = self.agent.clean_json(
            response
        )

        try:

            decision = json.loads(
                response
            )

        except json.JSONDecodeError as error:

            raise ValueError(
                "Supervisor returned invalid JSON: "
                f"{error}\nResponse: {response}"
            )

        return self.normalize_decision(
            decision,
            user_message
        )

    # NORMALIZE + VALIDATE

    def normalize_decision(
        self,
        decision,
        user_message
    ):

        agent = decision.get(
            "agent"
        )

        action = decision.get(
            "action"
        )

        arguments = decision.get(
            "arguments",
            {}
        )

        text = user_message.lower()

        # HARD DELETE ROUTING

        delete_words = [
            "delete",
            "remove",
            "erase",
            "discard"
        ]

        if (
            agent == "TASK_AGENT"
            and any(
                word in text
                for word in delete_words
            )
        ):

            action = "delete"

        # HARD COMPLETE ROUTING

        complete_phrases = [
            "complete task",
            "complete the task",
            "finish task",
            "finish the task",
            "mark task as done",
            "mark task completed",
            "mark as done"
        ]

        if (
            agent == "TASK_AGENT"
            and any(
                phrase in text
                for phrase in complete_phrases
            )
        ):

            action = "complete"

        # HARD UPDATE ROUTING

        update_words = [
            "update",
            "edit",
            "modify",
            "change",
            "rename"
        ]

        if (
            agent == "TASK_AGENT"
            and any(
                word in text
                for word in update_words
            )
        ):

            action = "update"


        if (
            agent == "TASK_AGENT"
            and any(
                word in text
                for word in delete_words
            )
        ):

            action = "delete"

        # TASK ID NORMALIZATION

        if action in {
            "delete",
            "complete",
            "update"
        }:

            task_id = (
                arguments.get("task_id")
                or arguments.get("id")
            )

            if task_id is not None:

                try:

                    arguments["task_id"] = int(
                        task_id
                    )

                except (
                    TypeError,
                    ValueError
                ):

                    raise ValueError(
                        "Task ID must be an integer."
                    )

        # ACTION ALIASES

        action_aliases = {

            "create task": "create",
            "create tasks": "create",
            "add task": "create",
            "add tasks": "create",

            "list tasks": "list",
            "show tasks": "list",
            "get tasks": "list",

            "update task": "update",
            "update tasks": "update",
            "edit task": "update",
            "modify task": "update",
            "change task": "update",

            "complete task": "complete",
            "complete tasks": "complete",
            "finish task": "complete",
            "finish tasks": "complete",

            "delete task": "delete",
            "delete tasks": "delete",
            "remove task": "delete",
            "remove tasks": "delete",

            "overdue tasks": "overdue",
            "show overdue tasks": "overdue",

            "high priority tasks": "high_priority",
            "show high priority tasks": "high_priority",

            "save memory": "save",
            "search memory": "search",
            "search memories": "search",

            "daily plan": "daily",
            "daily planning": "daily",

            "weekly plan": "weekly",
            "weekly planning": "weekly",

            "productivity report": "report",
            "productivity reports": "report"
        }

        action = action_aliases.get(
            action,
            action
        )

        # VALID AGENTS

        valid_agents = {
            "TASK_AGENT",
            "MEMORY_AGENT",
            "PLANNING_AGENT"
        }

        if agent not in valid_agents:

            raise ValueError(
                f"Unknown agent: {agent}"
            )

        # VALID ACTIONS

        valid_actions = {

            "TASK_AGENT": {
                "create",
                "list",
                "update",
                "complete",
                "delete",
                "overdue",
                "high_priority"
            },

            "MEMORY_AGENT": {
                "save",
                "search"
            },

            "PLANNING_AGENT": {
                "daily",
                "weekly",
                "report"
            }
        }

        if action not in valid_actions[agent]:

            raise ValueError(
                f"Invalid action '{action}' "
                f"for {agent}"
            )

        decision["agent"] = agent
        decision["action"] = action
        decision["arguments"] = arguments

        return decision

    # RUN

    def run(self, user_message):

        if not user_message.strip():

            return {
                "success": False,
                "error": "Request cannot be empty."
            }

        decision = self.decide_agent(
            user_message
        )

        agent_name = decision[
            "agent"
        ]

        action = decision[
            "action"
        ]

        arguments = decision.get(
            "arguments",
            {}
        )

        print(
            f"[SUPERVISOR] Agent: "
            f"{agent_name}"
        )

        print(
            f"[SUPERVISOR] Action: "
            f"{action}"
        )

        # TASK AGENT

        if agent_name == "TASK_AGENT":

            return self.task_agent.handle(
                action,
                arguments
            )

        # MEMORY AGENT

        if agent_name == "MEMORY_AGENT":

            return self.memory_agent.handle(
                action,
                arguments
            )

        # PLANNING AGENT

        if agent_name == "PLANNING_AGENT":

            arguments[
                "original_request"
            ] = user_message

            return self.planning_agent.handle(
                action,
                arguments
            )

        return {
            "success": False,
            "error":
                f"Unknown agent: {agent_name}"
        }

# DIRECT TEST

if __name__ == "__main__":

    supervisor = ProductivitySupervisor()

    print()
    print("=" * 50)
    print(" MULTI-AGENT PRODUCTIVITY SYSTEM")
    print("=" * 50)
    print()
    print("Type 'exit' to stop.")

    while True:

        user = input("\nYou: ").strip()

        if user.lower() == "exit":

            print("Goodbye!")

            break

        try:

            result = supervisor.run(
                user
            )

            print("\nResult:")
            print(result)

        except Exception as error:

            print(
                f"\n[ERROR] {error}"
            )