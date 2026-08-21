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

        st.html(
            """
            <div class="section-rule"></div>
            """
        )

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

        prompt = st.text_area(
            "Request",
            placeholder=(
                "Plan my day and prioritize "
                "my learning"
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
                    "Thinking through your request..."
                ):

                    try:

                        result = supervisor.run(
                            prompt.strip()
                        )

                        st.markdown(
                            "### Result"
                        )

                        st.write(
                            result
                        )

                    except Exception as e:

                        st.error(
                            f"Assistant error: {e}"
                        )


# ENTRY POINT

if __name__ == "__main__":
    main()