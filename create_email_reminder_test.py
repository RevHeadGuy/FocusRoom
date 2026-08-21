from orchestrator.agent import get_agent


agent = get_agent()

result = agent.create_task(
    title="Email Reminder Test",
    priority="high",
    due_date="2026-08-20T18:00:00"
)

print(result)