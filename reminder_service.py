import time

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

    # ==================================================
    # CHECK AND SEND REMINDERS
    # ==================================================

    def check_reminders(self):

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

            print(
                f"[REMINDER] Sending email for "
                f"task #{reminder['task_id']}"
            )

            subject = (
                f"Task Reminder: "
                f"{reminder['title']}"
            )

            body = (
                f"Hello,\n\n"

                f"This is a reminder about your "
                f"upcoming task.\n\n"

                f"Task: {reminder['title']}\n"
                f"Priority: {reminder['priority']}\n"
                f"Due: {reminder['due_date']}\n"
                f"Time remaining: "
                f"{reminder['hours_left']} hours\n\n"

                f"{reminder['message']}\n\n"

                f"— Productivity Agent"
            )

            try:

                self.email_service.send_email(
                    subject=subject,
                    body=body
                )

                # IMPORTANT:
                # Only mark the reminder as sent
                # AFTER the email succeeds.

                self.db.mark_reminder_sent(
                    reminder["task_id"]
                )

                print(
                    f"[REMINDER] Email sent for "
                    f"task #{reminder['task_id']}"
                )

            except Exception as error:

                print(
                    f"[REMINDER ERROR] "
                    f"Task #{reminder['task_id']}: "
                    f"{error}"
                )

    # ==================================================
    # CONTINUOUS WORKER
    # ==================================================

    def run(self, interval_minutes=30):

        print(
            "[REMINDER SERVICE] Started."
        )

        print(
            f"[REMINDER SERVICE] "
            f"Checking every "
            f"{interval_minutes} minutes."
        )

        while True:

            self.check_reminders()

            time.sleep(
                interval_minutes * 60
            )


if __name__ == "__main__":

    service = ReminderService()

    service.run(
        interval_minutes=30
    )