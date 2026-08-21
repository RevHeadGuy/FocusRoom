from datetime import datetime, timedelta

from orchestrator.agent import get_agent


agent = get_agent()

due = datetime.now() + timedelta(minutes=30)

result = agent.create_task(
    title="Automatic Email Test",
    priority="high",
    due_date=due.isoformat()
)

print(result)