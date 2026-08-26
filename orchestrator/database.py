import json
import sqlite3
from pathlib import Path


DB_PATH = (
    Path(__file__).resolve().parent.parent
    / "productivity.db"
)


class Database:

    def __init__(self, db_path=DB_PATH):

        self.db_path = str(db_path)

        self.initialize()

    # ==================================================
    # CONNECTION
    # ==================================================

    def connect(self):

        conn = sqlite3.connect(
            self.db_path,
            timeout=10,          # wait up to 10 s on a locked DB
        )
        # WAL mode allows concurrent readers + one writer without blocking.
        # This is safe to set on every connection — SQLite ignores it if
        # already set at the file level.
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        return conn

    # ==================================================
    # INITIALIZE DATABASE
    # ==================================================

    def initialize(self):

        with self.connect() as conn:

            # ------------------------------------------
            # TASKS TABLE
            # ------------------------------------------

            conn.execute("""
                CREATE TABLE IF NOT EXISTS tasks (
                    id INTEGER PRIMARY KEY,
                    title TEXT NOT NULL,
                    description TEXT,
                    priority TEXT NOT NULL,
                    status TEXT NOT NULL,
                    due_date TEXT,
                    project TEXT,
                    created_at TEXT NOT NULL,
                    completed_at TEXT,
                    reminder_24_sent INTEGER DEFAULT 0,
                    reminder_1_sent INTEGER DEFAULT 0,
                    reminder_15_sent INTEGER DEFAULT 0
                )
            """)

            # ------------------------------------------
            # MEMORIES TABLE
            # ------------------------------------------

            conn.execute("""
                CREATE TABLE IF NOT EXISTS memories (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    category TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS token_usage (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    operation TEXT NOT NULL,
                    model TEXT NOT NULL,
                    prompt_tokens INTEGER NOT NULL DEFAULT 0,
                    completion_tokens INTEGER NOT NULL DEFAULT 0,
                    total_tokens INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS mcp_transport (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    execution_id TEXT,
                    method TEXT NOT NULL,
                    path TEXT NOT NULL,
                    request_bytes INTEGER NOT NULL DEFAULT 0,
                    response_bytes INTEGER NOT NULL DEFAULT 0,
                    status_code INTEGER NOT NULL,
                    created_at TEXT NOT NULL
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS execution_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    execution_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    name TEXT NOT NULL,
                    details TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL
                )
            """)

            conn.commit()

        # Upgrade existing databases if necessary
        self.initialize_reminder_columns()
        self.initialize_mcp_transport_columns()

    # ==================================================
    # ADD REMINDER COLUMNS TO EXISTING DATABASE
    # ==================================================

    def initialize_reminder_columns(self):

        with self.connect() as conn:

            columns = {
                row[1]
                for row in conn.execute(
                    "PRAGMA table_info(tasks)"
                ).fetchall()
            }

            new_columns = {
                "reminder_24_sent":
                    "INTEGER DEFAULT 0",

                "reminder_1_sent":
                    "INTEGER DEFAULT 0",

                "reminder_15_sent":
                    "INTEGER DEFAULT 0"
            }

            for column, definition in new_columns.items():

                if column not in columns:

                    conn.execute(
                        f"""
                        ALTER TABLE tasks
                        ADD COLUMN {column} {definition}
                        """
                    )

            conn.commit()

    # ==================================================
    # ADD execution_id COLUMN TO mcp_transport
    # ==================================================

    def initialize_mcp_transport_columns(self):

        with self.connect() as conn:

            columns = {
                row[1]
                for row in conn.execute(
                    "PRAGMA table_info(mcp_transport)"
                ).fetchall()
            }

            if "execution_id" not in columns:
                conn.execute(
                    "ALTER TABLE mcp_transport "
                    "ADD COLUMN execution_id TEXT"
                )
                conn.commit()

    # ==================================================
    # TASK METHODS
    # ==================================================

    def save_task(self, task):

        with self.connect() as conn:

            conn.execute("""
                INSERT OR REPLACE INTO tasks (
                    id,
                    title,
                    description,
                    priority,
                    status,
                    due_date,
                    project,
                    created_at,
                    completed_at,
                    reminder_24_sent,
                    reminder_1_sent,
                    reminder_15_sent
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                task["id"],
                task["title"],
                task.get("description"),
                task["priority"],
                task["status"],
                task.get("due_date"),
                task.get("project"),
                task["created_at"],
                task.get("completed_at"),

                # Preserve existing reminder state
                task.get("reminder_24_sent", 0),
                task.get("reminder_1_sent", 0),
                task.get("reminder_15_sent", 0)
            ))

            conn.commit()

    # ==================================================
    # GET TASKS
    # ==================================================

    def get_tasks(self, status=None):

        with self.connect() as conn:

            conn.row_factory = sqlite3.Row

            if status:

                rows = conn.execute("""
                    SELECT *
                    FROM tasks
                    WHERE status = ?
                    ORDER BY id
                """, (
                    status,
                )).fetchall()

            else:

                rows = conn.execute("""
                    SELECT *
                    FROM tasks
                    ORDER BY id
                """).fetchall()

            return [
                dict(row)
                for row in rows
            ]

    # ==================================================
    # GET SINGLE TASK
    # ==================================================

    def get_task(self, task_id):

        with self.connect() as conn:

            conn.row_factory = sqlite3.Row

            row = conn.execute("""
                SELECT *
                FROM tasks
                WHERE id = ?
            """, (
                int(task_id),
            )).fetchone()

            if row:

                return dict(row)

            return None

    # ==================================================
    # UPDATE TASK
    # ==================================================

    def update_task(self, task_id, updates):

        allowed_fields = {
            "title",
            "description",
            "priority",
            "status",
            "due_date",
            "project"
        }

        updates = {
            key: value
            for key, value in updates.items()
            if key in allowed_fields
        }

        if not updates:

            return None

        fields = ", ".join(
            f"{key} = ?"
            for key in updates
        )

        values = list(
            updates.values()
        )

        values.append(
            int(task_id)
        )

        with self.connect() as conn:

            cursor = conn.execute(
                f"""
                UPDATE tasks
                SET {fields}
                WHERE id = ?
                """,
                values
            )

            conn.commit()

            if cursor.rowcount == 0:

                return None

        return self.get_task(task_id)

    # ==================================================
    # DELETE TASK
    # ==================================================

    def delete_task(self, task_id):

        with self.connect() as conn:

            cursor = conn.execute(
                """
                DELETE FROM tasks
                WHERE id = ?
                """,
                (
                    int(task_id),
                )
            )

            conn.commit()

            return cursor.rowcount > 0

    # ==================================================
    # REMINDER METHODS
    # ==================================================

    def reminder_was_sent(
        self,
        task_id,
        reminder_type
    ):

        allowed = {
            "24": "reminder_24_sent",
            "1": "reminder_1_sent",
            "15": "reminder_15_sent"
        }

        column = allowed.get(
            str(reminder_type)
        )

        if not column:

            raise ValueError(
                f"Invalid reminder type: "
                f"{reminder_type}"
            )

        with self.connect() as conn:

            row = conn.execute(
                f"""
                SELECT {column}
                FROM tasks
                WHERE id = ?
                """,
                (
                    int(task_id),
                )
            ).fetchone()

            if not row:

                return False

            return bool(row[0])

    # ==================================================

    def mark_reminder_sent(
        self,
        task_id,
        reminder_type
    ):

        allowed = {
            "24": "reminder_24_sent",
            "1": "reminder_1_sent",
            "15": "reminder_15_sent"
        }

        column = allowed.get(
            str(reminder_type)
        )

        if not column:

            raise ValueError(
                f"Invalid reminder type: "
                f"{reminder_type}"
            )

        with self.connect() as conn:

            conn.execute(
                f"""
                UPDATE tasks
                SET {column} = 1
                WHERE id = ?
                """,
                (
                    int(task_id),
                )
            )

            conn.commit()

    # ==================================================
    # MEMORY METHODS
    # ==================================================

    def save_memory(self, memory):

        with self.connect() as conn:

            conn.execute("""
                INSERT OR REPLACE INTO memories (
                    key,
                    value,
                    category,
                    updated_at
                )
                VALUES (?, ?, ?, ?)
            """, (
                memory["key"],
                memory["value"],
                memory["category"],
                memory["updated_at"]
            ))

            conn.commit()

    # ==================================================
    # TOKEN USAGE METHODS

    def save_token_usage(self, usage):

        with self.connect() as conn:

            conn.execute("""
                INSERT INTO token_usage (
                    operation,
                    model,
                    prompt_tokens,
                    completion_tokens,
                    total_tokens,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                usage["operation"],
                usage["model"],
                usage.get("prompt_tokens", 0),
                usage.get("completion_tokens", 0),
                usage.get("total_tokens", 0),
                usage["created_at"]
            ))

            conn.commit()

    def get_token_usage_totals(self):

        with self.connect() as conn:

            conn.row_factory = sqlite3.Row

            row = conn.execute("""
                SELECT
                    COALESCE(SUM(prompt_tokens), 0) AS prompt_tokens,
                    COALESCE(SUM(completion_tokens), 0) AS completion_tokens,
                    COALESCE(SUM(total_tokens), 0) AS total_tokens,
                    COUNT(*) AS requests
                FROM token_usage
            """).fetchone()

            return dict(row) if row else {
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
                "requests": 0
            }

    def get_token_usage_by_operation(self):

        with self.connect() as conn:

            conn.row_factory = sqlite3.Row

            rows = conn.execute("""
                SELECT
                    operation,
                    SUM(prompt_tokens) AS prompt_tokens,
                    SUM(completion_tokens) AS completion_tokens,
                    SUM(total_tokens) AS total_tokens,
                    COUNT(*) AS requests
                FROM token_usage
                GROUP BY operation
                ORDER BY total_tokens DESC
            """).fetchall()

            return [dict(row) for row in rows]

    def save_mcp_transport(self, metrics):

        with self.connect() as conn:

            conn.execute("""
                INSERT INTO mcp_transport (
                    execution_id,
                    method,
                    path,
                    request_bytes,
                    response_bytes,
                    status_code,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                metrics.get("execution_id"),
                metrics["method"],
                metrics["path"],
                metrics.get("request_bytes", 0),
                metrics.get("response_bytes", 0),
                metrics["status_code"],
                metrics["created_at"]
            ))

            conn.commit()

    def start_mcp_transport(self, metrics):

        with self.connect() as conn:

            cursor = conn.execute("""
                INSERT INTO mcp_transport (
                    execution_id,
                    method,
                    path,
                    request_bytes,
                    response_bytes,
                    status_code,
                    created_at
                )
                VALUES (?, ?, ?, ?, 0, ?, ?)
            """, (
                metrics.get("execution_id"),
                metrics["method"],
                metrics["path"],
                metrics.get("request_bytes", 0),
                metrics.get("status_code", 500),
                metrics["created_at"]
            ))

            conn.commit()
            return cursor.lastrowid

    def update_mcp_transport(self, transport_id, response_bytes, status_code):

        with self.connect() as conn:

            conn.execute("""
                UPDATE mcp_transport
                SET response_bytes = ?, status_code = ?
                WHERE id = ?
            """, (
                response_bytes,
                status_code,
                transport_id
            ))

            conn.commit()

    def get_mcp_transport_totals(self):

        with self.connect() as conn:

            row = conn.execute("""
                SELECT
                    COALESCE(SUM(request_bytes), 0) AS request_bytes,
                    COALESCE(SUM(response_bytes), 0) AS response_bytes,
                    COUNT(*) AS requests
                FROM mcp_transport
            """).fetchone()

            return {
                "request_bytes": row[0] if row else 0,
                "response_bytes": row[1] if row else 0,
                "requests": row[2] if row else 0
            }

    def get_mcp_tool_call_counts(self):
        """
        Return per-tool MCP call counts and transport totals.

        Tool call counts come from execution_events (event_type='MCP')
        because that table is written synchronously in the main worker
        and is always complete.

        Transport byte totals come from mcp_transport; the request count
        from that table is also returned separately so the dashboard can
        show both the authoritative call count and the transport-recorded
        count for comparison.
        """

        with self.connect() as conn:

            conn.row_factory = sqlite3.Row

            rows = conn.execute("""
                SELECT
                    name        AS tool,
                    COUNT(*)    AS calls
                FROM execution_events
                WHERE event_type = 'MCP'
                GROUP BY name
                ORDER BY calls DESC
            """).fetchall()

            tool_counts = [dict(row) for row in rows]

            # Authoritative total from execution_events
            total_calls = sum(r["calls"] for r in tool_counts)

        # Byte totals from mcp_transport (best-effort)
        transport = self.get_mcp_transport_totals()
        transport["total_calls"] = total_calls   # authoritative count

        return {
            "tool_counts": tool_counts,
            "transport":   transport,
        }

    def get_mcp_transport_for_execution(self, execution_id):
        """
        Return transport stats (requests, request_bytes, response_bytes)
        for a single execution_id.
        """

        with self.connect() as conn:

            row = conn.execute("""
                SELECT
                    COUNT(*)                        AS requests,
                    COALESCE(SUM(request_bytes), 0) AS request_bytes,
                    COALESCE(SUM(response_bytes),0) AS response_bytes
                FROM mcp_transport
                WHERE execution_id = ?
            """, (execution_id,)).fetchone()

            if row:
                return {
                    "requests":       row[0],
                    "request_bytes":  row[1],
                    "response_bytes": row[2],
                }

            return {"requests": 0, "request_bytes": 0, "response_bytes": 0}

    def get_token_usage_for_execution(self, execution_id):
        """
        Return token usage breakdown by operation for a single execution_id,
        cross-referencing execution_events (which record the LLM call with
        its operation name) against token_usage rows inserted in the same
        time window.

        Strategy: collect the LLM event timestamps from execution_events,
        then fetch the matching token_usage rows inserted at those timestamps.
        SQLite TEXT ISO timestamps sort correctly, so this is a safe join.
        """

        with self.connect() as conn:

            conn.row_factory = sqlite3.Row

            # Get LLM event details for this execution
            events = conn.execute("""
                SELECT name, created_at
                FROM execution_events
                WHERE execution_id = ?
                  AND event_type   = 'LLM'
                ORDER BY id
            """, (execution_id,)).fetchall()

            if not events:
                return {"by_operation": [], "totals": {
                    "requests": 0,
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                    "total_tokens": 0,
                }}

            # For each LLM event, find the token_usage row that was
            # inserted within 2 seconds of it (same operation name).
            by_op = {}

            for ev in events:
                op  = ev["name"]
                ts  = ev["created_at"]

                row = conn.execute("""
                    SELECT
                        operation,
                        prompt_tokens,
                        completion_tokens,
                        total_tokens
                    FROM token_usage
                    WHERE operation = ?
                      AND created_at >= datetime(?, '-2 seconds')
                      AND created_at <= datetime(?, '+2 seconds')
                    ORDER BY ABS(
                        strftime('%s', created_at) - strftime('%s', ?)
                    )
                    LIMIT 1
                """, (op, ts, ts, ts)).fetchone()

                if row:
                    if op not in by_op:
                        by_op[op] = {
                            "operation":        op,
                            "requests":         0,
                            "prompt_tokens":    0,
                            "completion_tokens":0,
                            "total_tokens":     0,
                        }
                    by_op[op]["requests"]          += 1
                    by_op[op]["prompt_tokens"]     += row["prompt_tokens"]
                    by_op[op]["completion_tokens"] += row["completion_tokens"]
                    by_op[op]["total_tokens"]      += row["total_tokens"]

            ops = list(by_op.values())

            totals = {
                "requests":         sum(o["requests"]          for o in ops),
                "prompt_tokens":    sum(o["prompt_tokens"]     for o in ops),
                "completion_tokens":sum(o["completion_tokens"] for o in ops),
                "total_tokens":     sum(o["total_tokens"]      for o in ops),
            }

            return {"by_operation": ops, "totals": totals}

    def get_avg_tokens_per_execution(self):
        """
        Return the average total_tokens per completed execution,
        broken down by operation.

        An 'execution' is one distinct execution_id in execution_events.
        We join execution_events (LLM rows, which carry the timestamp) to
        token_usage rows recorded within a 2-second window, then average
        the per-execution totals.
        """

        with self.connect() as conn:

            conn.row_factory = sqlite3.Row

            # Count distinct executions that have at least one LLM event
            exec_count_row = conn.execute("""
                SELECT COUNT(DISTINCT execution_id) AS n
                FROM execution_events
                WHERE event_type = 'LLM'
            """).fetchone()

            n_executions = exec_count_row["n"] if exec_count_row else 0

            if n_executions == 0:
                return {
                    "executions":   0,
                    "avg_prompt":   0,
                    "avg_completion": 0,
                    "avg_total":    0,
                    "by_operation": [],
                }

            # Lifetime totals (already available)
            totals = self.get_token_usage_totals()

            avg_prompt     = round(totals["prompt_tokens"]     / n_executions)
            avg_completion = round(totals["completion_tokens"] / n_executions)
            avg_total      = round(totals["total_tokens"]      / n_executions)

            # Per-operation averages
            by_op_rows = conn.execute("""
                SELECT
                    operation,
                    COUNT(*)                          AS requests,
                    ROUND(SUM(prompt_tokens)     / ?, 0) AS avg_prompt,
                    ROUND(SUM(completion_tokens) / ?, 0) AS avg_completion,
                    ROUND(SUM(total_tokens)      / ?, 0) AS avg_total
                FROM token_usage
                GROUP BY operation
                ORDER BY avg_total DESC
            """, (n_executions, n_executions, n_executions)).fetchall()

            return {
                "executions":     n_executions,
                "avg_prompt":     avg_prompt,
                "avg_completion": avg_completion,
                "avg_total":      avg_total,
                "by_operation":   [dict(r) for r in by_op_rows],
            }

    def get_agent_execution_status(self):
        """
        Return which agents executed in the most recent execution,
        based on execution_events where event_type = 'Agent'.
        """

        with self.connect() as conn:

            conn.row_factory = sqlite3.Row

            # Get the latest execution_id
            row = conn.execute("""
                SELECT execution_id
                FROM execution_events
                ORDER BY id DESC
                LIMIT 1
            """).fetchone()

            if not row:
                return {}

            latest_id = row["execution_id"]

            rows = conn.execute("""
                SELECT DISTINCT name
                FROM execution_events
                WHERE execution_id = ?
                  AND event_type   = 'Agent'
            """, (latest_id,)).fetchall()

            return {
                r["name"]: True
                for r in rows
            }

    def save_execution_event(self, event):

        with self.connect() as conn:

            conn.execute("""
                INSERT INTO execution_events (
                    execution_id,
                    event_type,
                    name,
                    details,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?)
            """, (
                event["execution_id"],
                event["event_type"],
                event["name"],
                json.dumps(event.get("details", {}), default=str),
                event["created_at"]
            ))

            conn.commit()

    def get_recent_execution_events(self, limit=1):

        with self.connect() as conn:

            conn.row_factory = sqlite3.Row

            executions = conn.execute("""
                SELECT execution_id, MAX(id) AS last_event
                FROM execution_events
                GROUP BY execution_id
                ORDER BY last_event DESC
                LIMIT ?
            """, (limit,)).fetchall()

            traces = []

            for execution in executions:

                rows = conn.execute("""
                    SELECT *
                    FROM execution_events
                    WHERE execution_id = ?
                    ORDER BY id
                """, (execution["execution_id"],)).fetchall()

                traces.append({
                    "execution_id": execution["execution_id"],
                    "events": [
                        {
                            **dict(row),
                            "details": json.loads(row["details"])
                        }
                        for row in rows
                    ]
                })

            return traces

    # ==================================================

    def get_memories(self):

        with self.connect() as conn:

            conn.row_factory = sqlite3.Row

            rows = conn.execute("""
                SELECT *
                FROM memories
                ORDER BY updated_at DESC
            """).fetchall()

            return [
                dict(row)
                for row in rows
            ]

    # ==================================================
    # MEMORY SEARCH
    # ==================================================

    def search_memory(self, query):

        if not query:

            return []

        query = str(
            query
        ).lower().strip()

        words = query.split()

        if not words:

            return []

        with self.connect() as conn:

            conn.row_factory = sqlite3.Row

            conditions = []
            params = []

            for word in words:

                pattern = f"%{word}%"

                conditions.append("""
                    (
                        LOWER(key) LIKE ?
                        OR LOWER(value) LIKE ?
                        OR LOWER(category) LIKE ?
                    )
                """)

                params.extend([
                    pattern,
                    pattern,
                    pattern
                ])

            sql = f"""
                SELECT *
                FROM memories
                WHERE {" OR ".join(conditions)}
                ORDER BY updated_at DESC
            """

            rows = conn.execute(
                sql,
                params
            ).fetchall()

            return [
                dict(row)
                for row in rows
            ]

    # ==================================================
    # STATISTICS
    # ==================================================

    def count_tasks(self):

        with self.connect() as conn:

            result = conn.execute("""
                SELECT COUNT(*)
                FROM tasks
            """).fetchone()

            return result[0]

    # ==================================================

    def count_completed_tasks(self):

        with self.connect() as conn:

            result = conn.execute("""
                SELECT COUNT(*)
                FROM tasks
                WHERE status = 'completed'
            """).fetchone()

            return result[0]

    # ==================================================

    def count_memories(self):

        with self.connect() as conn:

            result = conn.execute("""
                SELECT COUNT(*)
                FROM memories
            """).fetchone()

            return result[0]