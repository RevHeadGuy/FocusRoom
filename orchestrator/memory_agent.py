from .agent import get_agent
from .telemetry import record_event


class MemoryAgent:

    def __init__(self):
        self.agent = get_agent()

    def handle(self, action, arguments):

        action = action.lower().strip()

        # NOTE: the supervisor already records an "Agent / MEMORY_AGENT"
        # event before calling handle().  We only record here when
        # invoked directly (i.e. when there is no active execution_id),
        # so the trace never shows the same agent step twice.
        from .telemetry import get_execution_id
        if not get_execution_id():
            record_event(
                self.agent.db,
                "Agent",
                "MEMORY_AGENT",
                {"action": action, "arguments": arguments}
            )

        aliases = {
            "save memory": "save",
            "save memories": "save",
            "remember": "save",
            "store memory": "save",

            "search memory": "search",
            "search memories": "search",
            "find memory": "search",
            "find memories": "search",
            "recall": "search",
        }

        action = aliases.get(action, action)

        # SAVE MEMORY
        if action == "save":

            key = (
                arguments.get("key")
                or arguments.get("memory_key")
                or "general_memory"
            )

            value = (
                arguments.get("value")
                or arguments.get("memory")
                or arguments.get("content")
            )

            category = arguments.get(
                "category",
                "general"
            )

            if not value:
                return {
                    "error": "Memory value is missing."
                }

            return self.agent.save_memory(
                key=key,
                value=value,
                category=category
            )

        # SEARCH MEMORY
        if action == "search":

            query = (
                arguments.get("query")
                or arguments.get("memory")
                or arguments.get("topic")
            )

            if not query:
                return {
                    "error": "Memory search query is missing."
                }

            return self.agent.search_memory(
                query
            )

        return {
            "error":
            f"Unknown memory action: {action}"
        }