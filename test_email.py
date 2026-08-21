from orchestrator.email_service import EmailService

email_service = EmailService()

email_service.send_email(
    subject="Productivity Agent Test",
    body="This is a test email from your Productivity Agent."
)

print("Email sent successfully!")