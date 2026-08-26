import json as _json
from datetime import datetime, timedelta

from .agent import get_agent
from .task_agent import TaskAgent
from .memory_agent import MemoryAgent
from .telemetry import get_execution_id, record_event

# ── Token budget constants ────────────────────────────────────────
_MAX_TASKS       = 15   # hard cap on tasks sent to the LLM
_MAX_MEMORIES    = 5    # hard cap on memory entries
_TASK_DUE_WINDOW = 14   # only tasks due within this many days
_PLAN_MAX_TOKENS = 400  # completion cap — a 3-section plan fits in 300-350

# Priority codes: single char keeps task lines short
_PRI = {"critical": "!!", "high": "!", "medium": "-", "low": "~"}


# ── Module-level helpers (defined once, not per-call) ─────────────

def _filter_tasks(raw):
    """Active tasks due within the window, sorted by priority."""
    if isinstance(raw, str):
        try:
            raw = _json.loads(raw)
        except Exception:
            return []
    if not isinstance(raw, list):
        return []

    active  = {"todo", "in_progress"}
    cutoff  = datetime.now().date() + timedelta(days=_TASK_DUE_WINDOW)
    order   = {"critical": 0, "high": 1, "medium": 2, "low": 3}

    keep = []
    for t in raw:
        if t.get("status") not in active:
            continue
        due = t.get("due_date")
        if due:
            try:
                d = datetime.fromisoformat(due).date()
                if d > cutoff:
                    continue
            except ValueError:
                pass
        keep.append(t)

    keep.sort(key=lambda t: (
        order.get(t.get("priority", "medium"), 2),
        t.get("due_date") or "9999",
    ))
    return keep[:_MAX_TASKS]


def _encode_tasks(task_list):
    """
    Ultra-compact task encoding — every character counts.

    Format per line:  !! Title (due mm-dd)
    !! = priority symbol, no field labels, date truncated to mm-dd.
    """
    if not task_list:
        return "none"
    lines = []
    for t in task_list:
        pri  = _PRI.get(t.get("priority", "medium"), "-")
        name = t.get("title", "?")
        due  = t.get("due_date") or ""
        due_short = due[5:10] if len(due) >= 10 else ""
        suffix = f" ({due_short})" if due_short else ""
        lines.append(f"{pri} {name}{suffix}")
    return "\n".join(lines)


def _filter_memories(raw):
    """Top _MAX_MEMORIES memories (DB already returns newest-first)."""
    if isinstance(raw, str):
        try:
            raw = _json.loads(raw)
        except Exception:
            return []
    if not isinstance(raw, list):
        return []
    return raw[:_MAX_MEMORIES]


def _encode_memories(memories):
    """
    One line per memory: value only, key omitted if it adds no meaning.
    Values capped at 80 chars.
    """
    if not memories:
        return "none"
    return "; ".join(
        str(m.get("value", ""))[:80]
        for m in memories
    )


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

        record_event(
            self.agent.db,
            "Agent",
            "PLANNING_AGENT",
            {"action": action, "arguments": arguments}
        )

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

        # --------------------------------------------------
        # The supervisor pre-serialises task_context and
        # memory_context as clean JSON strings before passing
        # them here.  When called standalone (no supervisor),
        # both keys are absent and we fall back to independent
        # agent calls.
        # --------------------------------------------------

        task_context   = arguments.get("task_context")
        memory_context = arguments.get("memory_context")

        if task_context is not None:

            print(
                "[PLANNING_AGENT] "
                "Using task context from supervisor."
            )

            # Already a clean string — use directly in prompt
            tasks = task_context

        else:

            print(
                "[PLANNING_AGENT] "
                "Requesting tasks from TASK_AGENT..."
            )

            import json as _json
            raw = self.task_agent.handle("list", {})
            tasks = _json.dumps(raw, indent=2, default=str)

        if memory_context is not None:

            print(
                "[PLANNING_AGENT] "
                "Using memory context from supervisor."
            )

            memories = memory_context

        else:

            print(
                "[PLANNING_AGENT] "
                "Requesting memories from MEMORY_AGENT..."
            )

            topic = arguments.get(
                "original_request",
                arguments.get(
                    "original request",
                    "current goals and priorities"
                )
            )

            if topic and "mcp" in str(topic).lower():
                topic = "MCP"

            import json as _json
            raw = self.memory_agent.handle("search", {"query": topic})
            memories = _json.dumps(raw, indent=2, default=str)

    def collaborative_daily_plan(self, arguments):

        # ── Pull context (supervisor path) or fetch directly ──────
        task_context   = arguments.get("task_context")
        memory_context = arguments.get("memory_context")

        if task_context is not None:
            tasks_raw = _json.loads(task_context) if isinstance(task_context, str) else task_context
        else:
            tasks_raw = self.task_agent.handle("list", {})

        if memory_context is not None:
            memories_raw = _json.loads(memory_context) if isinstance(memory_context, str) else memory_context
        else:
            topic = arguments.get("original_request", "work preferences")
            memories_raw = self.memory_agent.handle("search", {"query": topic})

        # ── Filter: active tasks due within the window ────────────
        tasks_for_prompt   = _filter_tasks(tasks_raw)
        memories_for_prompt = _filter_memories(memories_raw)

        tasks_text    = _encode_tasks(tasks_for_prompt)
        memories_text = _encode_memories(memories_for_prompt)

        n_tasks = len(tasks_for_prompt)
        print(f"[PLANNING_AGENT] {n_tasks} tasks, "
              f"{len(memories_for_prompt)} memories → LLM")

        # ── Minimal prompt ────────────────────────────────────────
        # Every word here costs tokens on every call.
        # Format: tight single-turn message, no system role.
        today = datetime.now().strftime("%a %d %b")
        prompt = (
            f"Plan {today}. Tasks (!! critical, ! high, - medium, ~ low):\n"
            f"{tasks_text}\n"
            f"Context: {memories_text}\n"
            "Reply: MORNING / AFTERNOON / EVENING bullets + 1-line REASONING."
        )

        response = self.agent.call_llm(
            [{"role": "user", "content": prompt}],
            operation="planning_request",
            max_tokens=_PLAN_MAX_TOKENS,
        )

        # ── Derive source_agents from telemetry ───────────────────
        execution_id = get_execution_id()
        source_agents = []
        seen = set()

        if execution_id:
            for trace in self.agent.db.get_recent_execution_events(1):
                if trace["execution_id"] != execution_id:
                    continue
                for ev in trace["events"]:
                    if (ev["event_type"] == "Agent"
                            and ev["name"] not in ("supervisor", "PLANNING_AGENT")
                            and ev["name"] not in seen):
                        source_agents.append(ev["name"])
                        seen.add(ev["name"])

        if not source_agents:
            if task_context   is not None: source_agents.append("TASK_AGENT")
            if memory_context is not None: source_agents.append("MEMORY_AGENT")
            if not source_agents:
                source_agents = ["TASK_AGENT", "MEMORY_AGENT"]

        return {"plan": response, "source_agents": source_agents}