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

        return sqlite3.connect(
            self.db_path
        )

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

            conn.commit()

        # Upgrade existing databases if necessary
        self.initialize_reminder_columns()

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