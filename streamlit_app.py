import os
import html
from datetime import date, datetime, time

import streamlit as st
from dotenv import load_dotenv

from orchestrator.agent import get_agent
from orchestrator.orchestrator import ProductivitySupervisor


load_dotenv()


# STREAMLIT CONFIG

st.set_page_config(
    page_title="Focusroom | Productivity OS",
    page_icon="◒",
    layout="wide",
    initial_sidebar_state="expanded",
)

# CSS

def inject_styles():

    st.html(
        """
        <style>

        @import url(
            'https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500'
            '&family=Space+Grotesk:wght@400;500;600;700&display=swap'
        );

        :root {
            --ink: #dbe8e4;
            --muted: #8da39e;
            --line: rgba(182, 221, 210, .14);
            --panel: #14201f;
            --panel-2: #1b2a28;
            --mint: #a5e3c9;
            --coral: #ff8d76;
            --gold: #f0c879;
        }

        html, body, [class*="css"] {
            font-family: 'Space Grotesk', sans-serif;
        }

        [data-testid="stAppViewContainer"] {
            background:
                radial-gradient(
                    circle at 90% 0%,
                    rgba(75, 130, 116, .22),
                    transparent 33%
                ),
                linear-gradient(
                    135deg,
                    #0b1213 0%,
                    #101b1b 49%,
                    #0d1415 100%
                );
            color: var(--ink);
        }

        [data-testid="stSidebar"] {
            background: #0d1717;
            border-right: 1px solid var(--line);
        }

        [data-testid="stHeader"] {
            background: transparent;
        }

        .block-container {
            max-width: 1440px;
            padding: 3rem 4rem 5rem;
        }

        h1, h2, h3 {
            color: var(--ink);
        }

        h1 {
            font-size: clamp(2.4rem, 5vw, 5.2rem) !important;
            line-height: .95 !important;
        }

        h2 {
            font-size: 1.55rem !important;
        }

        p,
        label {
            color: var(--muted);
        }

        .eyebrow {
            color: var(--mint);
            font-family: 'DM Mono', monospace;
            font-size: .72rem;
            letter-spacing: .12em;
            text-transform: uppercase;
            margin-bottom: 1rem;
        }

        .lede {
            font-size: 1.05rem;
            max-width: 540px;
            line-height: 1.6;
        }

        .metric-card,
        .task-card,
        .memory-card,
        .plan-card {
            background:
                linear-gradient(
                    145deg,
                    rgba(28, 45, 42, .92),
                    rgba(16, 27, 27, .92)
                );
            border: 1px solid var(--line);
            border-radius: 8px;
            padding: 1.1rem 1.2rem;
            box-sizing: border-box;
        }

        .metric-card {
            min-height: 110px;
        }

        .metric-label {
            color: var(--muted);
            font-family: 'DM Mono', monospace;
            font-size: .68rem;
            text-transform: uppercase;
        }

        .metric-value {
            color: var(--ink);
            font-size: 2rem;
            font-weight: 600;
            margin-top: .35rem;
        }

        .task-card {
            margin-bottom: 8px;
        }

        .task-title {
            color: var(--ink);
            font-size: 1.05rem;
            font-weight: 600;
        }

        .task-meta {
            color: var(--muted);
            font-family: 'DM Mono', monospace;
            font-size: .72rem;
            margin-top: .45rem;
        }

        .priority-critical {
            color: var(--coral);
        }

        .priority-high {
            color: var(--gold);
        }

        .priority-medium {
            color: var(--mint);
        }

        .priority-low {
            color: #91a6d8;
        }

        .status-pill {
            color: var(--mint);
            font-family: 'DM Mono', monospace;
            font-size: .7rem;
            text-transform: uppercase;
        }

        .section-rule {
            border-top: 1px solid var(--line);
            margin: 2.5rem 0 1.6rem;
        }

        .stButton > button {
            border-radius: 6px;
            border: 1px solid var(--line);
        }

        .stButton > button[kind="primary"] {
            background: var(--mint);
            color: #10201b;
            border: 0;
        }

        </style>
        """
    )


# SERVICES

@st.cache_resource
def services():

    agent = get_agent()
    supervisor = ProductivitySupervisor()

    return agent, supervisor


# HELPERS

def safe(value):

    if value is None:
        return ""

    return html.escape(str(value))


def task_due_label(task):

    due_date = task.get("due_date")

    if not due_date:
        return "No due date"

    try:

        due = datetime.fromisoformat(
            due_date
        )

        return (
            "Due "
            + due.strftime(
                "%d %b %Y, %I:%M %p"
            )
        )

    except Exception:

        return f"Due {due_date}"

# TASK CARD

def render_task(task, agent):

    task_id = task.get("id")

    title = safe(
        task.get(
            "title",
            "Untitled task"
        )
    )

    priority = safe(
        task.get(
            "priority",
            "medium"
        )
    )

    status = task.get(
        "status",
        "todo"
    )

    due = safe(
        task_due_label(task)
    )

    status_text = safe(
        status.replace(
            "_",
            " "
        )
    )

    st.html(
        f"""
        <div class="task-card">

            <div class="task-title">
                {title}
            </div>

            <div class="task-meta">

                <span class="priority-{priority}">
                    {priority}
                </span>

                &nbsp; · &nbsp;

                {due}

                &nbsp; · &nbsp;

                <span class="status-pill">
                    {status_text}
                </span>

            </div>

        </div>
        """
    )

    if status != "completed":

        if st.button(
            "Complete",
            key=f"complete_{task_id}",
            use_container_width=True
        ):

            result = agent.complete_task(
                task_id
            )

            if result.get("error"):

                st.error(
                    result["error"]
                )

            else:

                st.success(
                    "Task completed."
                )

                st.rerun()


# METRICS

def render_metrics(report):

    columns = st.columns(4)

    metrics = [
        (
            "Active tasks",
            report.get(
                "active_tasks",
                0
            )
        ),
        (
            "Completed",
            report.get(
                "completed_tasks",
                0
            )
        ),
        (
            "High priority",
            report.get(
                "high_priority_active_tasks",
                0
            )
        ),
        (
            "Completion rate",
            f"{report.get('completion_rate', 0)}%"
        ),
    ]

    for column, (label, value) in zip(
        columns,
        metrics
    ):

        with column:

            st.html(
                f"""
                <div class="metric-card">

                    <div class="metric-label">
                        {safe(label)}
                    </div>

                    <div class="metric-value">
                        {safe(value)}
                    </div>

                </div>
                """
            )


def _fmt_bytes(n):
    """Human-readable byte count."""
    if n >= 1024 * 1024:
        return f"{n / (1024 * 1024):.1f} MB"
    if n >= 1024:
        return f"{n / 1024:.1f} KB"
    return f"{n} B"


def render_telemetry(report):
    """
    Render the four-panel telemetry dashboard:
      1. AI USAGE
      2. AGENT EXECUTION
      3. MCP
      4. EXECUTION TRACE
    """

    # ----------------------------------------------------------------
    # Pull data from report
    # ----------------------------------------------------------------

    usage               = report.get("token_usage", {})
    by_op               = report.get("token_usage_by_operation", [])
    avg_tok             = report.get("avg_tokens_per_execution", {})
    agent_status        = report.get("agent_execution_status", {})
    mcp_data            = report.get("mcp_tool_counts", {})
    tool_counts         = mcp_data.get("tool_counts", [])
    transport           = mcp_data.get("transport", report.get("mcp_transport", {}))
    cur_transport       = report.get("current_execution_transport", {})
    cur_token_usage     = report.get("current_execution_token_usage", {})
    traces              = report.get("recent_executions", [])

    # ----------------------------------------------------------------
    # CSS additions for telemetry panels
    # ----------------------------------------------------------------

    st.html("""
        <style>
        .tel-panel {
            background: linear-gradient(145deg, rgba(28,45,42,.92), rgba(16,27,27,.92));
            border: 1px solid rgba(182,221,210,.14);
            border-radius: 8px;
            padding: 1.2rem 1.4rem 1.4rem;
            margin-bottom: 1rem;
            font-family: 'DM Mono', monospace;
        }
        .tel-header {
            color: #a5e3c9;
            font-size: .68rem;
            letter-spacing: .14em;
            text-transform: uppercase;
            border-bottom: 1px solid rgba(182,221,210,.14);
            padding-bottom: .55rem;
            margin-bottom: .9rem;
        }
        .tel-row {
            display: flex;
            justify-content: space-between;
            align-items: baseline;
            color: #dbe8e4;
            font-size: .82rem;
            margin-bottom: .35rem;
        }
        .tel-key  { color: #8da39e; }
        .tel-val  { color: #dbe8e4; font-weight: 600; }
        .tel-tick { color: #a5e3c9; }
        .tel-cross{ color: #ff8d76; }
        .tel-trace-step {
            color: #dbe8e4;
            font-size: .82rem;
            padding: .2rem 0 .2rem .6rem;
            border-left: 2px solid rgba(165,227,201,.25);
            margin-bottom: .15rem;
        }
        .tel-trace-arrow {
            color: #8da39e;
            font-size: .75rem;
            padding-left: .7rem;
            margin-bottom: .15rem;
        }
        </style>
    """)

    col_left, col_right = st.columns(2, gap="large")

    # ================================================================
    # LEFT COLUMN — AI USAGE + AGENT EXECUTION
    # ================================================================

    with col_left:

        # ------------------------------------------------------------
        # 1. AI USAGE  —  operation breakdown table
        # ------------------------------------------------------------

        # Column headers
        ai_table_html = """
            <div class="tel-row" style="border-bottom:1px solid rgba(182,221,210,.12);
                 padding-bottom:.4rem; margin-bottom:.5rem;">
                <span class="tel-key" style="flex:2;">Operation</span>
                <span class="tel-key" style="flex:1;text-align:right;">Req</span>
                <span class="tel-key" style="flex:1.4;text-align:right;">Prompt</span>
                <span class="tel-key" style="flex:1.4;text-align:right;">Compl</span>
                <span class="tel-key" style="flex:1.4;text-align:right;">Total</span>
            </div>"""

        if by_op:
            for row in by_op:
                op   = html.escape(row.get("operation", "unknown"))
                req  = row.get("requests", 0)
                pt   = f"{row.get('prompt_tokens', 0):,}"
                ct   = f"{row.get('completion_tokens', 0):,}"
                tt   = f"{row.get('total_tokens', 0):,}"
                ai_table_html += f"""
                    <div class="tel-row">
                        <span class="tel-key" style="flex:2;">{op}</span>
                        <span class="tel-val" style="flex:1;text-align:right;">{req}</span>
                        <span class="tel-val" style="flex:1.4;text-align:right;">{pt}</span>
                        <span class="tel-val" style="flex:1.4;text-align:right;">{ct}</span>
                        <span class="tel-val" style="flex:1.4;text-align:right;">{tt}</span>
                    </div>"""

            # Totals row
            ai_table_html += f"""
                <div class="tel-row" style="border-top:1px solid rgba(182,221,210,.12);
                     margin-top:.4rem; padding-top:.4rem;">
                    <span class="tel-val" style="flex:2;">TOTAL</span>
                    <span class="tel-val" style="flex:1;text-align:right;">{usage.get("requests",0)}</span>
                    <span class="tel-val" style="flex:1.4;text-align:right;">{usage.get("prompt_tokens",0):,}</span>
                    <span class="tel-val" style="flex:1.4;text-align:right;">{usage.get("completion_tokens",0):,}</span>
                    <span class="tel-val" style="flex:1.4;text-align:right;">{usage.get("total_tokens",0):,}</span>
                </div>"""

            # Average per execution row
            n_exec   = avg_tok.get("executions", 0)
            avg_p    = avg_tok.get("avg_prompt", 0)
            avg_c    = avg_tok.get("avg_completion", 0)
            avg_t    = avg_tok.get("avg_total", 0)
            avg_label = f"AVG / exec ({n_exec})" if n_exec else "AVG / exec"
            ai_table_html += f"""
                <div class="tel-row" style="margin-top:.25rem; opacity:.75;">
                    <span class="tel-key" style="flex:2;">{html.escape(avg_label)}</span>
                    <span class="tel-key" style="flex:1;text-align:right;">—</span>
                    <span class="tel-key" style="flex:1.4;text-align:right;">{avg_p:,}</span>
                    <span class="tel-key" style="flex:1.4;text-align:right;">{avg_c:,}</span>
                    <span class="tel-key" style="flex:1.4;text-align:right;">{avg_t:,}</span>
                </div>"""
        else:
            ai_table_html += """
                <div class="tel-row">
                    <span class="tel-key">No LLM calls recorded yet</span>
                </div>"""

        st.html(f"""
            <div class="tel-panel">
                <div class="tel-header">AI USAGE</div>
                {ai_table_html}
            </div>
        """)

        # ------------------------------------------------------------
        # 2. AGENT EXECUTION
        # ------------------------------------------------------------

        all_agents = ["TASK_AGENT", "MEMORY_AGENT", "PLANNING_AGENT"]

        # Also surface supervisor if it ran
        if "supervisor" in agent_status:
            all_agents = ["supervisor"] + all_agents

        agent_rows_html = ""

        for agent_name in all_agents:
            ran  = agent_status.get(agent_name, False)
            tick = '<span class="tel-tick">✓</span>' if ran else '<span class="tel-cross">✗</span>'
            agent_rows_html += f"""
                <div class="tel-row">
                    <span class="tel-key">{html.escape(agent_name)}</span>
                    <span>{tick}</span>
                </div>"""

        st.html(f"""
            <div class="tel-panel">
                <div class="tel-header">AGENT EXECUTION</div>
                {agent_rows_html}
            </div>
        """)

    # ================================================================
    # RIGHT COLUMN — MCP + EXECUTION TRACE
    # ================================================================

    with col_right:

        # ------------------------------------------------------------
        # 3. MCP
        # ------------------------------------------------------------

        # -- Lifetime tool call counts --
        tool_rows_html = ""

        if tool_counts:
            for entry in tool_counts:
                tool_rows_html += f"""
                    <div class="tel-row">
                        <span class="tel-key">{html.escape(entry.get("tool", "unknown"))}</span>
                        <span class="tel-val">{entry.get("calls", 0)}</span>
                    </div>"""
        else:
            tool_rows_html = '<div class="tel-row"><span class="tel-key">No MCP calls recorded yet</span></div>'

        # -- Lifetime transport totals --
        # total_calls = authoritative count from execution_events
        # requests    = rows actually written to mcp_transport (may lag)
        req_bytes    = transport.get("request_bytes", 0)
        resp_bytes   = transport.get("response_bytes", 0)
        total_calls  = transport.get("total_calls", transport.get("requests", 0))

        lifetime_html = f"""
            <div class="tel-row" style="margin-top:.7rem; padding-top:.6rem;
                 border-top:1px solid rgba(182,221,210,.12);">
                <span class="tel-key">Transport Requests</span>
                <span class="tel-val">{total_calls}</span>
            </div>
            <div class="tel-row">
                <span class="tel-key">Request Bytes</span>
                <span class="tel-val">{html.escape(_fmt_bytes(req_bytes))}</span>
            </div>
            <div class="tel-row">
                <span class="tel-key">Response Bytes</span>
                <span class="tel-val">{html.escape(_fmt_bytes(resp_bytes))}</span>
            </div>"""

        # -- Current execution transport --
        cur_req   = cur_transport.get("requests", 0)
        cur_rqb   = cur_transport.get("request_bytes", 0)
        cur_rsb   = cur_transport.get("response_bytes", 0)

        current_exec_html = f"""
            <div class="tel-row" style="margin-top:.9rem; padding-top:.6rem;
                 border-top:1px solid rgba(182,221,210,.18);">
                <span style="color:#a5e3c9; font-size:.68rem;
                      letter-spacing:.10em; text-transform:uppercase;">
                    Current Execution
                </span>
            </div>
            <div class="tel-row">
                <span class="tel-key">MCP requests</span>
                <span class="tel-val">{cur_req}</span>
            </div>
            <div class="tel-row">
                <span class="tel-key">Request bytes</span>
                <span class="tel-val">{html.escape(_fmt_bytes(cur_rqb))}</span>
            </div>
            <div class="tel-row">
                <span class="tel-key">Response bytes</span>
                <span class="tel-val">{html.escape(_fmt_bytes(cur_rsb))}</span>
            </div>"""

        st.html(f"""
            <div class="tel-panel">
                <div class="tel-header">MCP</div>
                {tool_rows_html}
                {lifetime_html}
                {current_exec_html}
            </div>
        """)

        # ------------------------------------------------------------
        # 4. EXECUTION TRACE
        # ------------------------------------------------------------

        if not traces:
            st.html("""
                <div class="tel-panel">
                    <div class="tel-header">EXECUTION TRACE</div>
                    <div class="tel-row">
                        <span class="tel-key">No executions recorded yet.</span>
                    </div>
                </div>
            """)
        else:
            trace  = traces[0]
            events = trace.get("events", [])

            steps_html = ""

            for i, event in enumerate(events):
                etype = event.get("event_type", "")
                name  = event.get("name", "")

                # Format step label
                if etype == "MCP":
                    label = f"MCP:{html.escape(name)}"
                elif etype in ("Agent", "Result"):
                    label = html.escape(name)
                else:
                    label = f"{html.escape(etype)}:{html.escape(name)}"

                steps_html += f'<div class="tel-trace-step">{label}</div>'

                if i < len(events) - 1:
                    steps_html += '<div class="tel-trace-arrow">↓</div>'

            st.html(f"""
                <div class="tel-panel">
                    <div class="tel-header">EXECUTION TRACE</div>
                    {steps_html}
                </div>
            """)


def render_telemetry_detail(report):
    """Collapsible raw detail: per-execution token breakdown + event log."""

    with st.expander("Raw telemetry detail", expanded=False):

        # ── Per-execution token usage ──────────────────────────────
        cur_token = report.get("current_execution_token_usage", {})
        cur_ops   = cur_token.get("by_operation", [])
        cur_tot   = cur_token.get("totals", {})

        if cur_ops:
            st.caption("Token usage — current execution")
            rows = [
                {
                    "operation":  r.get("operation", "unknown"),
                    "requests":   r.get("requests", 0),
                    "prompt":     r.get("prompt_tokens", 0),
                    "completion": r.get("completion_tokens", 0),
                    "total":      r.get("total_tokens", 0),
                }
                for r in cur_ops
            ]
            rows.append({
                "operation":  "TOTAL",
                "requests":   cur_tot.get("requests", 0),
                "prompt":     cur_tot.get("prompt_tokens", 0),
                "completion": cur_tot.get("completion_tokens", 0),
                "total":      cur_tot.get("total_tokens", 0),
            })
            st.dataframe(rows, hide_index=True, use_container_width=True)

        # ── Execution event log ────────────────────────────────────
        traces = report.get("recent_executions", [])

        if traces:
            trace = traces[0]
            st.caption(f"Execution ID: {trace['execution_id']}")

            for i, event in enumerate(trace.get("events", []), start=1):
                label = f"{i}. {event['event_type']} → {event['name']}"
                with st.expander(label, expanded=False):
                    st.json(event.get("details", {}))


# MAIN

def main():

    inject_styles()

    agent, supervisor = services()

    # --------------------------------------------------------
    # REPORT
    # --------------------------------------------------------

    try:

        report = agent.productivity_report()

    except Exception as e:

        st.error(
            f"Could not load productivity report: {e}"
        )

        report = {
            "active_tasks": 0,
            "completed_tasks": 0,
            "high_priority_active_tasks": 0,
            "completion_rate": 0,
        }

    # SIDEBAR

    with st.sidebar:

        st.html(
            """
            <div class="eyebrow">
                FOCUSROOM / 01
            </div>
            """
        )

        st.title(
            "Your control room"
        )

        st.caption(
            "A quiet place to turn intent "
            "into finished work."
        )

        st.markdown("---")

        view = st.radio(
            "Navigate",
            [
                "Overview",
                "Tasks",
                "Plan",
                "Memory",
                "Assistant"
            ],
            label_visibility="collapsed"
        )

        st.markdown("---")

        st.caption(
            "Model · "
            + os.getenv(
                "GROQ_MODEL",
                "configured Groq model"
            )
        )

        st.caption(
            "Today · "
            + date.today().isoformat()
        )

    # HEADER

    st.html(
        """
        <div class="eyebrow">
            PRODUCTIVITY OPERATING SYSTEM
        </div>
        """
    )

    st.title(
        "Make room for the work that matters."
    )

    st.markdown(
        """
        <p class="lede">
        Your tasks, memories, and next best
        actions in one considered workspace.
        </p>
        """,
        unsafe_allow_html=True
    )

    # OVERVIEW

    if view == "Overview":

        render_metrics(report)

        st.html('<div class="section-rule"></div>')

        st.subheader("System telemetry")

        render_telemetry(report)

        render_telemetry_detail(report)

        st.html('<div class="section-rule"></div>')

        left, right = st.columns(
            [1.35, 1]
        )

        # TASKS

        with left:

            st.subheader(
                "Open loop"
            )

            try:

                tasks = agent.list_tasks()

                active = [
                    task
                    for task in tasks
                    if task.get("status")
                    != "completed"
                ]

            except Exception as e:

                st.error(
                    f"Could not load tasks: {e}"
                )

                active = []

            if not active:

                st.success(
                    "Everything is clear. "
                    "Enjoy the empty space."
                )

            for task in active[:5]:

                render_task(
                    task,
                    agent
                )

        # TODAY

        with right:

            st.subheader(
                "Today at a glance"
            )

            try:

                plan = agent.create_daily_plan()

                task_count = len(
                    plan.get(
                        "tasks",
                        []
                    )
                )

                memory_count = len(
                    plan.get(
                        "memories",
                        []
                    )
                )

                plan_date = safe(
                    plan.get(
                        "date",
                        date.today().isoformat()
                    )
                )

                st.html(
                    f"""
                    <div class="plan-card">

                        <div class="eyebrow">
                            TODAY
                        </div>

                        <h3>
                            {plan_date}
                        </h3>

                        <p>
                            {task_count}
                            active tasks are in motion.
                        </p>

                        <p>
                            {memory_count}
                            memories are available
                            to guide your focus.
                        </p>

                    </div>
                    """
                )

            except Exception as e:

                st.error(
                    f"Could not generate plan: {e}"
                )

            st.subheader(
                "Momentum"
            )

            completion_rate = float(
                report.get(
                    "completion_rate",
                    0
                )
            )

            st.progress(
                min(
                    max(
                        completion_rate / 100,
                        0
                    ),
                    1
                )
            )

            st.caption(
                "Completion rate across all saved tasks"
            )

    # TASKS

    elif view == "Tasks":

        st.subheader(
            "Task desk"
        )

        with st.expander(
            "Add a task",
            expanded=True
        ):

            with st.form(
                "create_task_form"
            ):

                title = st.text_input(
                    "Task title",
                    placeholder=(
                        "What needs your attention?"
                    )
                )

                description = st.text_area(
                    "Description",
                    height=80
                )

                col1, col2, col3 = st.columns(
                    3
                )

                with col1:

                    priority = st.selectbox(
                        "Priority",
                        [
                            "medium",
                            "high",
                            "critical",
                            "low"
                        ]
                    )

                with col2:

                    due_date = st.date_input(
                        "Due date",
                        value=None
                    )

                with col3:

                    due_time = st.time_input(
                        "Due time",
                        value=time(
                            18,
                            0
                        )
                    )

                project = st.text_input(
                    "Project",
                    placeholder="Optional"
                )

                st.caption(
                    "Email reminders use this exact "
                    "due date and time."
                )

                submitted = st.form_submit_button(
                    "Add task",
                    type="primary",
                    use_container_width=True
                )

            if submitted:

                if not title.strip():

                    st.error(
                        "Task title is required."
                    )

                else:

                    combined_due_date = None

                    if due_date:

                        due_datetime = datetime.combine(
                            due_date,
                            due_time
                        )

                        combined_due_date = (
                            due_datetime.isoformat(
                                timespec="seconds"
                            )
                        )

                    try:

                        result = agent.create_task(
                            title.strip(),
                            description=(
                                description.strip()
                                or None
                            ),
                            priority=priority,
                            due_date=combined_due_date,
                            project=(
                                project.strip()
                                or None
                            )
                        )

                        if result.get("error"):

                            st.error(
                                result["error"]
                            )

                        else:

                            st.success(
                                "Task added successfully."
                            )

                            if combined_due_date:

                                st.info(
                                    "Due: "
                                    + datetime.fromisoformat(
                                        combined_due_date
                                    ).strftime(
                                        "%d %b %Y, %I:%M %p"
                                    )
                                )

                            st.rerun()

                    except Exception as e:

                        st.error(
                            f"Could not create task: {e}"
                        )

        # FILTER

        status_filter = st.selectbox(
            "Show",
            [
                "all",
                "todo",
                "in_progress",
                "completed"
            ]
        )

        try:

            tasks = agent.list_tasks(
                None
                if status_filter == "all"
                else status_filter
            )

        except Exception as e:

            st.error(
                f"Could not load tasks: {e}"
            )

            tasks = []

        if not tasks:

            st.info(
                "No tasks found."
            )

        for task in tasks:

            render_task(
                task,
                agent
            )

    # PLAN

    elif view == "Plan":

        st.subheader(
            "Plan the day"
        )

        st.caption(
            "A practical snapshot of your "
            "current workload and stored context."
        )

        try:

            plan = agent.create_daily_plan()

            tasks = plan.get(
                "tasks",
                []
            )

            plan_date = safe(
                plan.get(
                    "date",
                    date.today().isoformat()
                )
            )

            st.html(
                f"""
                <div class="plan-card">

                    <div class="eyebrow">
                        {plan_date}
                    </div>

                    <h3>
                        {len(tasks)} active tasks
                    </h3>

                </div>
                """
            )

            for task in tasks:

                render_task(
                    task,
                    agent
                )

        except Exception as e:

            st.error(
                f"Could not generate plan: {e}"
            )

        st.subheader(
            "Productivity report"
        )

        st.json(
            report
        )

    # MEMORY

    elif view == "Memory":

        st.subheader(
            "Memory shelf"
        )

        with st.form(
            "save_memory_form"
        ):

            key = st.text_input(
                "Memory key",
                placeholder="e.g. current_goal"
            )

            value = st.text_area(
                "What should I remember?",
                height=90
            )

            category = st.text_input(
                "Category",
                value="general"
            )

            submitted = st.form_submit_button(
                "Save memory",
                type="primary"
            )

        if submitted:

            if not key.strip():

                st.error(
                    "Memory key is required."
                )

            elif not value.strip():

                st.error(
                    "Memory value is required."
                )

            else:

                try:

                    result = agent.save_memory(
                        key.strip(),
                        value.strip(),
                        category.strip()
                        or "general"
                    )

                    if (
                        isinstance(result, dict)
                        and result.get("error")
                    ):

                        st.error(
                            result["error"]
                        )

                    else:

                        st.success(
                            "Memory saved."
                        )

                        st.rerun()

                except Exception as e:

                    st.error(
                        f"Could not save memory: {e}"
                    )

        query = st.text_input(
            "Search memories",
            placeholder=(
                "Search your saved context"
            )
        )

        try:

            if query.strip():

                memories = agent.search_memory(
                    query.strip()
                )

            else:

                memories = agent.get_memories()

        except Exception as e:

            st.error(
                f"Could not load memories: {e}"
            )

            memories = []

        for memory in memories:

            st.html(
                f"""
                <div class="memory-card">

                    <div class="eyebrow">
                        {safe(memory.get("category", "general"))}
                    </div>

                    <strong>
                        {safe(memory.get("key", ""))}
                    </strong>

                    <p>
                        {safe(memory.get("value", ""))}
                    </p>

                </div>
                """
            )

    # ASSISTANT

    elif view == "Assistant":

        st.subheader(
            "Ask the assistant"
        )

        st.caption(
            "Try: "
            "\"Check my pending tasks, consider my work preferences, "
            "and create my daily plan.\""
        )

        prompt = st.text_area(
            "Request",
            placeholder=(
                "Check my pending tasks, consider my work "
                "preferences, and create my daily plan."
            ),
            height=140
        )

        if st.button(
            "Run request",
            type="primary"
        ):

            if not prompt.strip():

                st.warning(
                    "Write a request first."
                )

            else:

                with st.spinner(
                    "Orchestrating agents..."
                ):

                    try:

                        result = supervisor.run(
                            prompt.strip()
                        )

                        # Reload report so telemetry reflects this run
                        try:
                            updated_report = agent.productivity_report()
                        except Exception:
                            updated_report = report

                        # ── Result ──────────────────────────────────
                        st.markdown("### Result")

                        if isinstance(result, dict):
                            plan_text = result.get("plan")
                            if plan_text:
                                st.markdown(plan_text)
                            else:
                                st.write(result)
                        else:
                            st.write(result)

                        # ── Telemetry panel ──────────────────────────
                        st.markdown("### Execution telemetry")

                        render_telemetry(updated_report)

                        render_telemetry_detail(updated_report)

                    except Exception as e:

                        st.error(
                            f"Assistant error: {e}"
                        )


# ENTRY POINT

if __name__ == "__main__":
    main()