from orchestrator.database import Database
from orchestrator.reminder_agent import ReminderAgent


db = Database()

agent = ReminderAgent(db)

reminders = agent.generate_reminders(
    hours=24
)

print("\nUPCOMING REMINDERS")
print("=" * 50)

for reminder in reminders:
    print(f"\nTask: {reminder['title']}")
    print(f"Priority: {reminder['priority']}")
    print(f"Due: {reminder['due_date']}")
    print(f"Time left: {reminder['hours_left']} hours")
    print(f"Message: {reminder['message']}")