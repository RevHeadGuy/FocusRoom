from .agent import get_agent
from .task_agent import TaskAgent
from .memory_agent import MemoryAgent


class PlanningAgent:

    def __init__(self):

        self.agent = get_agent()

        self.task_agent = TaskAgent()

        self.memory_agent = MemoryAgent()

    def handle(
        self,
        action,
        arguments
    ):

        action = action.lower().strip()

        aliases = {

            "daily plan": "daily",
            "daily planning": "daily",

            "plan day": "daily",
            "plan my day": "daily",

            "weekly plan": "weekly",
            "weekly planning": "weekly",

            "productivity report":
                "report",

            "productivity reports":
                "report",

            "productivity":
                "report"
        }

        action = aliases.get(
            action,
            action
        )

        if action == "daily":

            return self.collaborative_daily_plan(
                arguments
            )

        if action == "weekly":

            return self.agent.create_weekly_plan()

        if action == "report":

            return self.agent.productivity_report()

        return {
            "error":
            f"Unknown planning action: {action}"
        }

    # ==================================================
    # MULTI-AGENT COLLABORATION
    # ==================================================

    def collaborative_daily_plan(
        self,
        arguments
    ):

        print(
            "[PLANNING_AGENT] "
            "Requesting tasks..."
        )

        tasks = self.task_agent.handle(
            "list",
            {}
        )

        print(
            "[PLANNING_AGENT] "
            "Requesting memories..."
        )

        topic = arguments.get(
            "original request",
            "current goals and priorities"
        )

        if "mcp" in topic.lower():

            topic = "MCP"

        memories = self.memory_agent.handle(
            "search",
            {
                "query": topic
            }
        )

        print(
            "[PLANNING_AGENT] ",
            memories
        )

        prompt = f"""
You are the Planning Agent in a
multi-agent productivity system.

You received information from two
specialized agents.

TASK AGENT DATA:
{tasks}

MEMORY AGENT DATA:
{memories}

Create a practical daily plan.

Rules:

1. Critical tasks first.
2. High priority tasks next.
3. Tasks related to the user's goals
   should receive higher priority.
4. Do not invent tasks.
5. Use the actual tasks provided.
6. Consider the user's memories.
7. Keep the plan realistic.

Return:

MORNING
- tasks

AFTERNOON
- tasks

EVENING
- tasks

PRIORITY REASONING
- explanation
"""

        response = self.agent.call_llm(
            [
                {
                    "role": "system",
                    "content":
                    "You are an expert productivity planner."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        )

        return {
            "plan": response,

            "source_agents": [
                "TASK_AGENT",
                "MEMORY_AGENT"
            ]
        }