from orchestrator.database import Database
from orchestrator.reminder_agent import ReminderAgent
from orchestrator.email_service import EmailService


db = Database()

email_service = EmailService()

reminder_agent = ReminderAgent(
    db=db,
    email_service=email_service
)

result = reminder_agent.send_reminders(
    hours=24
)

print(result)