from datetime import datetime, timedelta


class ReminderAgent:

    def __init__(self, db):
        self.db = db

    # FIND UPCOMING TASKS

    def get_upcoming_tasks(self, hours=24):

        tasks = self.db.get_tasks()

        now = datetime.now()
        limit = now + timedelta(hours=hours)

        upcoming = []

        for task in tasks:

            # Never remind for completed tasks
            if task.get("status") == "completed":
                continue

            due_date = task.get("due_date")

            if not due_date:
                continue

            try:

                due = datetime.fromisoformat(
                    due_date
                )

            except (ValueError, TypeError):

                continue

            if now <= due <= limit:

                upcoming.append(task)

        return upcoming

    # DETERMINE REMINDER STAGE

    def get_reminder_type(self, hours_left):

        if hours_left <= 0.25:
            return "15"

        if hours_left <= 1:
            return "1"

        if hours_left <= 24:
            return "24"

        return None

    # GENERATE REMINDERS

    def generate_reminders(self, hours=24):

        tasks = self.get_upcoming_tasks(
            hours=hours
        )

        reminders = []

        now = datetime.now()

        for task in tasks:

            try:

                due_date = datetime.fromisoformat(
                    task["due_date"]
                )

            except (ValueError, TypeError):

                continue

            time_left = due_date - now

            hours_left = (
                time_left.total_seconds()
                / 3600
            )

            reminder_type = self.get_reminder_type(
                hours_left
            )

            if not reminder_type:
                continue

            # Don't send the same reminder twice
            if self.db.reminder_was_sent(
                task["id"],
                reminder_type
            ):
                continue

            if reminder_type == "24":
                message = (
                    f"Reminder: "
                    f"'{task['title']}' "
                    f"is due in "
                    f"{round(hours_left, 1)} hours."
                )

            elif reminder_type == "1":
                message = (
                    f"Reminder: "
                    f"'{task['title']}' "
                    f"is due in approximately "
                    f"{round(hours_left * 60)} minutes."
                )

            else:
                message = (
                    f"Urgent reminder: "
                    f"'{task['title']}' "
                    f"is due in "
                    f"{round(max(hours_left * 60, 0))} minutes."
                )

            reminders.append({
                "task_id": task["id"],
                "title": task["title"],
                "priority": task["priority"],
                "due_date": task["due_date"],
                "hours_left": round(
                    hours_left,
                    2
                ),
                "reminder_type": reminder_type,
                "message": message
            })

        return reminders