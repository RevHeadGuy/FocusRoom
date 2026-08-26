import json
import contextvars
from concurrent.futures import ThreadPoolExecutor, as_completed

from .agent import get_agent
from .task_agent import TaskAgent
from .memory_agent import MemoryAgent
from .planning_agent import PlanningAgent
from .mcp_transport import record_mcp_call
from .telemetry import (
    finish_execution,
    record_event,
    set_execution_id,
    start_execution,
)


class ProductivitySupervisor:

    def __init__(self):
        self.agent = get_agent()
        self.task_agent = TaskAgent()
        self.memory_agent = MemoryAgent()
        self.planning_agent = PlanningAgent()

    # ============================================================
    # SUPERVISOR DECISION
    # ============================================================

    def decide_agent(self, user_message):

        supervisor_prompt = """\
Return JSON only. No markdown, no explanation.

Schema: {"actions": [{"agent": <A>, "action": <X>, "arguments": <O>}, ...]}

Agents, actions, argument shapes:
  TASK_AGENT   | create {title,priority?,description?,due_date?,project?}
               | list   {status?}
               | update {task_id,title?,priority?,status?,due_date?,project?}
               | complete {task_id}
               | delete {task_id}
               | overdue {}
               | high_priority {}
  MEMORY_AGENT | save   {key,value,category?}
               | search {query}
  PLANNING_AGENT | daily {}
                 | weekly {}
                 | report {}

Rules:
- Include every agent actually needed; do not collapse into one.
- For planning: add TASK_AGENT(list) and/or MEMORY_AGENT(search) first, then PLANNING_AGENT.
- PLANNING_AGENT always comes last.
- Return ONLY the JSON object."""

        response = self.agent.call_llm(
            [
                {
                    "role": "system",
                    "content": supervisor_prompt,
                },
                {
                    "role": "user",
                    "content": user_message,
                },
            ],
            operation="supervisor_decision",
        )

        response = response.strip()

        # Remove accidental markdown fences
        if response.startswith("```"):
            response = response.replace("```json", "", 1)
            response = response.replace("```", "", 1)
            response = response.strip()

        try:
            decisions = self.parse_decisions(response)

        except Exception as error:
            raise ValueError(
                "Supervisor returned invalid JSON: "
                f"{error}\n"
                f"Response: {response}"
            )

        return [
            self.normalize_decision(
                decision,
                user_message,
            )
            for decision in decisions
        ]

    # ============================================================
    # DETERMINISTIC ROUTER
    # ============================================================
    # Covers the patterns that appear in 90 %+ of real requests.
    # Returns a list of decisions (same shape as decide_agent) when
    # the intent is unambiguous, or None to fall through to the LLM.
    #
    # Zero LLM tokens are spent when this method returns a list.
    # ============================================================

    _DAILY_PLAN_PHRASES = (
        "daily plan", "plan my day", "plan today", "plan for today",
        "create my plan", "make my plan", "build my plan",
        "what should i do today", "today's plan", "day plan",
        "schedule today", "prioritize today", "prioritise today",
    )
    _TASK_ONLY_PHRASES = (
        "list tasks", "show tasks", "my tasks", "pending tasks",
        "open tasks", "active tasks", "what tasks",
        "show me my tasks", "list my tasks",
    )
    _OVERDUE_PHRASES = (
        "overdue", "overdue tasks", "late tasks", "past due",
    )
    _HIGH_PRIORITY_PHRASES = (
        "high priority", "critical tasks", "urgent tasks",
        "most important", "top priority",
    )
    _REPORT_PHRASES = (
        "productivity report", "my report", "progress report",
        "how am i doing", "show report",
    )

    def _route_deterministically(self, user_message: str):
        """
        Match the user message against known patterns without calling
        the LLM.  Returns a list of validated decision dicts, or None
        if the message is ambiguous and should go to the LLM router.
        """
        msg = user_message.lower().strip()

        # ── Daily plan (most common demo query) ──────────────────
        # Matches anything that mentions planning for today,
        # whether or not it mentions tasks/preferences/memories.
        if any(ph in msg for ph in self._DAILY_PLAN_PHRASES):
            query = "work preferences"
            # If user mentions specific topics, use those as query
            for keyword in ("goals", "preferences", "focus", "priorities"):
                if keyword in msg:
                    query = keyword
                    break
            return [
                {"agent": "TASK_AGENT",    "action": "list",   "arguments": {}},
                {"agent": "MEMORY_AGENT",  "action": "search", "arguments": {"query": query}},
                {"agent": "PLANNING_AGENT","action": "daily",  "arguments": {}},
            ]

        # ── List tasks only ───────────────────────────────────────
        if any(ph in msg for ph in self._TASK_ONLY_PHRASES):
            status = None
            if "pending" in msg or "open" in msg or "active" in msg:
                status = "todo"
            elif "completed" in msg or "done" in msg or "finished" in msg:
                status = "completed"
            args = {"status": status} if status else {}
            return [
                {"agent": "TASK_AGENT", "action": "list", "arguments": args},
            ]

        # ── Overdue tasks ─────────────────────────────────────────
        if any(ph in msg for ph in self._OVERDUE_PHRASES):
            return [
                {"agent": "TASK_AGENT", "action": "overdue", "arguments": {}},
            ]

        # ── High priority ─────────────────────────────────────────
        if any(ph in msg for ph in self._HIGH_PRIORITY_PHRASES):
            return [
                {"agent": "TASK_AGENT", "action": "high_priority", "arguments": {}},
            ]

        # ── Productivity report ───────────────────────────────────
        if any(ph in msg for ph in self._REPORT_PHRASES):
            return [
                {"agent": "PLANNING_AGENT", "action": "report", "arguments": {}},
            ]

        # ── Ambiguous — let the LLM decide ───────────────────────
        return None



    def parse_decisions(self, response):

        parsed = json.loads(response)

        if not isinstance(parsed, dict):
            raise ValueError(
                "Supervisor response must be a JSON object."
            )

        actions = parsed.get("actions")

        if not isinstance(actions, list):
            raise ValueError(
                "Supervisor response must contain "
                "an 'actions' array."
            )

        if len(actions) == 0:
            raise ValueError(
                "Supervisor returned no actions."
            )

        for action in actions:

            if not isinstance(action, dict):
                raise ValueError(
                    "Every item in 'actions' must be an object."
                )

            if "agent" not in action:
                raise ValueError(
                    "Action missing 'agent'."
                )

            if "action" not in action:
                raise ValueError(
                    "Action missing 'action'."
                )

        return actions

    # ============================================================
    # NORMALIZE DECISION
    # ============================================================

    def normalize_decision(
        self,
        decision,
        user_message,
    ):

        agent = decision.get("agent")
        action = decision.get("action")
        arguments = decision.get("arguments") or {}

        if not isinstance(arguments, dict):
            arguments = {}

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
            "productivity reports": "report",
        }

        action = action_aliases.get(
            action,
            action,
        )

        valid_actions = {
            "TASK_AGENT": {
                "create",
                "list",
                "update",
                "complete",
                "delete",
                "overdue",
                "high_priority",
            },
            "MEMORY_AGENT": {
                "save",
                "search",
            },
            "PLANNING_AGENT": {
                "daily",
                "weekly",
                "report",
            },
        }

        if agent not in valid_actions:
            raise ValueError(
                f"Unknown agent: {agent}"
            )

        if action not in valid_actions[agent]:
            raise ValueError(
                f"Invalid action '{action}' "
                f"for {agent}"
            )

        decision["agent"] = agent
        decision["action"] = action
        decision["arguments"] = arguments

        return decision

    # ============================================================
    # EXECUTE MULTI-AGENT WORKFLOW
    # ============================================================

    def run(
        self,
        user_message,
        execution_id=None,
    ):

        if not user_message.strip():
            return {
                "success": False,
                "error": "Request cannot be empty.",
            }

        owns_execution = execution_id is None

        if owns_execution:
            execution_id = start_execution()
        else:
            set_execution_id(execution_id)

        try:

            # ====================================================
            # ROUTING  — deterministic first, LLM as fallback
            # ====================================================

            decisions = self._route_deterministically(user_message)

            if decisions is not None:
                # Validate and normalise the deterministic decisions
                # through the same pipeline used for LLM decisions.
                decisions = [
                    self.normalize_decision(d, user_message)
                    for d in decisions
                ]
                print(
                    f"[SUPERVISOR] Deterministic route: "
                    f"{len(decisions)} action(s) — 0 LLM tokens"
                )
            else:
                decisions = self.decide_agent(user_message)
                print(
                    f"[SUPERVISOR] LLM route: "
                    f"{len(decisions)} action(s) selected"
                )

            record_event(
                self.agent.db,
                "Agent",
                "supervisor",
                {
                    "request": user_message,
                    "actions": decisions,
                },
            )

            print(
                f"[SUPERVISOR] "
                f"{len(decisions)} action(s) selected"
            )

            task_result   = None
            memory_result = None
            planning_result = None

            # ====================================================
            # TASK_AGENT + MEMORY_AGENT  — run in parallel
            # Both are pure data-fetch operations with no
            # dependency on each other, so we submit them
            # concurrently and collect results as they finish.
            # ====================================================

            task_decisions   = [d for d in decisions if d["agent"] == "TASK_AGENT"]
            memory_decisions = [d for d in decisions if d["agent"] == "MEMORY_AGENT"]

            def _run_task(decision):
                action    = decision["action"]
                arguments = decision["arguments"]

                _mcp_tool = {
                    "list":         "list_tasks",
                    "create":       "create_task",
                    "update":       "update_task",
                    "complete":     "complete_task",
                    "delete":       "delete_task",
                    "overdue":      "list_tasks",
                    "high_priority":"list_tasks",
                }.get(action, action)

                record_event(self.agent.db, "Agent", "TASK_AGENT",
                             {"action": action, "arguments": arguments})
                record_event(self.agent.db, "MCP", _mcp_tool,
                             {"agent": "TASK_AGENT", "action": action, "arguments": arguments})

                result = self.task_agent.handle(action, arguments)

                record_mcp_call(self.agent.db, tool=_mcp_tool,
                                arguments=arguments, result=result,
                                execution_id=execution_id)
                record_event(self.agent.db, "Result", "task_agent_result",
                             {"agent": "TASK_AGENT", "result": result})

                return ("task", _mcp_tool, result)

            def _run_memory(decision):
                action    = decision["action"]
                arguments = decision["arguments"]

                _mcp_tool = {
                    "save":   "save_memory",
                    "search": "search_memory",
                }.get(action, action)

                record_event(self.agent.db, "Agent", "MEMORY_AGENT",
                             {"action": action, "arguments": arguments})
                record_event(self.agent.db, "MCP", _mcp_tool,
                             {"agent": "MEMORY_AGENT", "action": action, "arguments": arguments})

                result = self.memory_agent.handle(action, arguments)

                record_mcp_call(self.agent.db, tool=_mcp_tool,
                                arguments=arguments, result=result,
                                execution_id=execution_id)
                record_event(self.agent.db, "Result", "memory_agent_result",
                             {"agent": "MEMORY_AGENT", "result": result})

                return ("memory", _mcp_tool, result)

            # --------------------------------------------------
            # Each worker gets its own copy of the current context
            # so ctx.run() is never entered twice on the same thread.
            # A single shared copy would raise
            # "cannot enter context: ... is already entered"
            # when the thread pool reuses a thread for the second task.
            # --------------------------------------------------

            futures = []

            with ThreadPoolExecutor(max_workers=2) as pool:

                for d in task_decisions:
                    print(f"[SUPERVISOR] Agent: TASK_AGENT   | Action: {d['action']} (parallel)")
                    task_ctx = contextvars.copy_context()
                    futures.append(pool.submit(task_ctx.run, _run_task, d))

                for d in memory_decisions:
                    print(f"[SUPERVISOR] Agent: MEMORY_AGENT | Action: {d['action']} (parallel)")
                    memory_ctx = contextvars.copy_context()
                    futures.append(pool.submit(memory_ctx.run, _run_memory, d))

                for future in as_completed(futures):
                    kind, _mcp_tool, result = future.result()
                    if kind == "task":
                        task_result = result
                    else:
                        memory_result = result

            # ====================================================
            # PLANNING AGENT
            # ====================================================

            for decision in decisions:

                if decision["agent"] != "PLANNING_AGENT":
                    continue

                agent_name = decision["agent"]
                action = decision["action"]

                arguments = dict(
                    decision["arguments"]
                )

                # --------------------------------------------------
                # Normalise upstream results before handing them to
                # the planning agent.
                #
                # task_result  → list of task dicts  (or None / error)
                # memory_result→ list of memory dicts (or None / error)
                #
                # We convert both to clean JSON strings so the LLM
                # prompt always receives well-formed text, and we
                # gracefully handle error dicts returned by agents.
                # --------------------------------------------------

                import json as _json

                def _clean_context(value, label):
                    if value is None:
                        return f"No {label} available."
                    if isinstance(value, dict) and value.get("error"):
                        return f"{label} error: {value['error']}"
                    if isinstance(value, (list, dict)):
                        # Compact JSON — no indent, no extra whitespace.
                        # The planning_agent parses this back to a list
                        # before encoding; pretty-printing only wastes tokens.
                        return _json.dumps(value, separators=(",", ":"), default=str)
                    return str(value)

                task_context_str   = _clean_context(task_result,   "tasks")
                memory_context_str = _clean_context(memory_result, "memories")

                # Pass clean strings — not raw Python objects
                arguments["original_request"] = user_message
                arguments["task_context"]      = task_context_str
                arguments["memory_context"]    = memory_context_str

                print(
                    f"[SUPERVISOR] Agent: {agent_name}"
                )
                print(
                    f"[SUPERVISOR] Action: {action}"
                )

                # Record the planning event WITHOUT the large context
                # blobs to keep execution_events rows lean.
                record_event(
                    self.agent.db,
                    "Agent",
                    agent_name,
                    {
                        "action": action,
                        "task_items":   len(task_result)   if isinstance(task_result,   list) else None,
                        "memory_items": len(memory_result) if isinstance(memory_result, list) else None,
                    },
                )

                # Map action → canonical MCP tool name
                _planning_mcp_tool = {
                    "daily": "daily_plan",
                    "weekly": "weekly_plan",
                    "report": "productivity_report",
                }.get(action, action)

                record_event(
                    self.agent.db,
                    "MCP",
                    _planning_mcp_tool,
                    {"agent": agent_name, "action": action},
                )

                planning_result = self.planning_agent.handle(
                    action,
                    arguments,
                )

                # ── measure actual transport bytes ──────────────
                # Use a lightweight request payload — strip the large
                # task_context / memory_context strings that were
                # already measured in the upstream calls.
                _planning_request = {
                    "action":           action,
                    "original_request": arguments.get("original_request", ""),
                }
                record_mcp_call(
                    self.agent.db,
                    tool         = _planning_mcp_tool,
                    arguments    = _planning_request,
                    result       = planning_result,
                    execution_id = execution_id,
                )

            # ====================================================
            # FINAL RESULT
            # ====================================================

            result = (
                planning_result
                if planning_result is not None
                else memory_result
                if memory_result is not None
                else task_result
            )

            record_event(
                self.agent.db,
                "Result",
                "agent_result",
                {
                    "result": result,
                },
            )

            return result

        finally:

            if owns_execution:
                finish_execution()