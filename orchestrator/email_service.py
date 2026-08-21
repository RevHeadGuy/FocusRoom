import os
import smtplib
from email.message import EmailMessage
from dotenv import load_dotenv


load_dotenv()


class EmailService:

    def __init__(self):

        self.sender = os.getenv("EMAIL_SENDER")
        self.password = os.getenv("EMAIL_PASSWORD")
        self.recipient = os.getenv("EMAIL_RECIPIENT")

        self.smtp_server = os.getenv(
            "EMAIL_SMTP_SERVER",
            "smtp.gmail.com"
        )

        self.smtp_port = int(
            os.getenv(
                "EMAIL_SMTP_PORT",
                "587"
            )
        )

    def send_email(self, subject, body):

        if not self.sender:
            raise ValueError(
                "EMAIL_SENDER is not configured."
            )

        if not self.password:
            raise ValueError(
                "EMAIL_PASSWORD is not configured."
            )

        if not self.recipient:
            raise ValueError(
                "EMAIL_RECIPIENT is not configured."
            )

        message = EmailMessage()

        message["From"] = self.sender
        message["To"] = self.recipient
        message["Subject"] = subject

        message.set_content(body)

        with smtplib.SMTP(
            self.smtp_server,
            self.smtp_port
        ) as server:

            server.starttls()

            server.login(
                self.sender,
                self.password
            )

            server.send_message(message)

        return True