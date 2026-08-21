from .agent import get_agent


class MemoryAgent:

    def __init__(self):
        self.agent = get_agent()

    def handle(self, action, arguments):

        action = action.lower().strip()

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