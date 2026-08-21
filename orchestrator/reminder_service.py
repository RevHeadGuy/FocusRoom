import time
from datetime import datetime

from orchestrator.database import Database
from orchestrator.reminder_agent import ReminderAgent
from orchestrator.email_service import EmailService


class ReminderService:

    def __init__(self):

        self.db = Database()

        self.reminder_agent = ReminderAgent(
            self.db
        )

        self.email_service = EmailService()

        # Remember which tasks have already
        # received a reminder.
        self.sent_reminders = set()

    def check_reminders(self):

        print(
            f"[REMINDER] Checking tasks at "
            f"{datetime.now().isoformat()}"
        )

        reminders = (
            self.reminder_agent.generate_reminders(
                hours=24
            )
        )

        if not reminders:

            print(
                "[REMINDER] No upcoming reminders."
            )

            return

        for reminder in reminders:

            task_id = reminder["task_id"]

            # Don't send the same reminder repeatedly
            if task_id in self.sent_reminders:

                continue

            subject = (
                f"Task Reminder: "
                f"{reminder['title']}"
            )

            body = f"""
Productivity Agent Reminder

Task: {reminder['title']}

Priority: {reminder['priority']}

Due: {reminder['due_date']}

Time remaining:
{reminder['hours_left']} hours

{reminder['message']}

Please complete the task before the deadline.
"""

            try:

                print(
                    f"[REMINDER] Sending email "
                    f"for task #{task_id}"
                )

                self.email_service.send_email(
                    subject=subject,
                    body=body
                )

                self.sent_reminders.add(
                    task_id
                )

                print(
                    f"[REMINDER] Email sent "
                    f"for task #{task_id}"
                )

            except Exception as error:

                print(
                    f"[REMINDER ERROR] "
                    f"Task #{task_id}: {error}"
                )

    def run(self, interval_minutes=5):

        print("=" * 55)
        print(" AUTOMATIC REMINDER SERVICE")
        print("=" * 55)

        print(
            f"Checking every "
            f"{interval_minutes} minutes."
        )

        while True:

            try:

                self.check_reminders()

            except Exception as error:

                print(
                    f"[SERVICE ERROR] {error}"
                )

            time.sleep(
                interval_minutes * 60
            )


if __name__ == "__main__":

    service = ReminderService()

    service.run(
        interval_minutes=5
    )