import time

from orchestrator.database import Database
from orchestrator.reminder_agent import ReminderAgent
from orchestrator.email_service import EmailService


CHECK_INTERVAL = 60
REMINDER_WINDOW_HOURS = 24


def run_reminder_check():

    db = Database()

    reminder_agent = ReminderAgent(db)

    email_service = EmailService()

    reminders = reminder_agent.generate_reminders(
        hours=REMINDER_WINDOW_HOURS
    )

    if not reminders:

        print(
            "[REMINDER] No reminders to send."
        )

        return

    for reminder in reminders:

        task_id = reminder["task_id"]

        print(
            f"[REMINDER] "
            f"Sending {reminder['reminder_type']}h "
            f"reminder for task #{task_id}"
        )

        try:

            email_service.send_email(

                subject=(
                    f"Task Reminder: "
                    f"{reminder['title']}"
                ),

                body=(
                    f"Hello,\n\n"
                    f"This is an automatic reminder "
                    f"from your Productivity Agent.\n\n"
                    f"Task: {reminder['title']}\n"
                    f"Priority: {reminder['priority']}\n"
                    f"Due: {reminder['due_date']}\n"
                    f"Time remaining: "
                    f"{reminder['hours_left']} hours\n\n"
                    f"{reminder['message']}\n\n"
                    f"Productivity Agent"
                )
            )

            # Mark ONLY after email succeeds
            db.mark_reminder_sent(
                task_id,
                reminder["reminder_type"]
            )

            print(
                f"[REMINDER] "
                f"Email sent successfully "
                f"for task #{task_id}"
            )

        except Exception as error:

            print(
                f"[REMINDER ERROR] "
                f"Task #{task_id}: {error}"
            )


def main():

    print("=" * 55)
    print(" PRODUCTIVITY AGENT - REMINDER WORKER")
    print("=" * 55)

    print(
        f"Checking every "
        f"{CHECK_INTERVAL} seconds..."
    )

    print(
        "Reminder schedule: "
        "24 hours → 1 hour → 15 minutes"
    )

    while True:

        try:

            run_reminder_check()

        except Exception as error:

            print(
                f"[WORKER ERROR] {error}"
            )

        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":

    main()