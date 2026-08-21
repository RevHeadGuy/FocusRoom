import os
import smtplib
from email.message import EmailMessage
from dotenv import load_dotenv


load_dotenv()


class EmailAgent:

    def __init__(self):

        self.smtp_host = os.getenv(
            "SMTP_HOST",
            "smtp.gmail.com"
        )

        self.smtp_port = int(
            os.getenv(
                "SMTP_PORT",
                "587"
            )
        )

        self.email = os.getenv(
            "EMAIL_ADDRESS"
        )

        self.password = os.getenv(
            "EMAIL_PASSWORD"
        )

        self.recipient = os.getenv(
            "REMINDER_EMAIL"
        )

    def send_email(
        self,
        subject,
        body
    ):

        if not self.email:
            raise ValueError(
                "EMAIL_ADDRESS is not configured"
            )

        if not self.password:
            raise ValueError(
                "EMAIL_PASSWORD is not configured"
            )

        if not self.recipient:
            raise ValueError(
                "REMINDER_EMAIL is not configured"
            )

        message = EmailMessage()

        message["From"] = self.email
        message["To"] = self.recipient
        message["Subject"] = subject

        message.set_content(body)

        with smtplib.SMTP(
            self.smtp_host,
            self.smtp_port
        ) as server:

            server.starttls()

            server.login(
                self.email,
                self.password
            )

            server.send_message(
                message
            )

        return {
            "success": True,
            "message": "Email sent successfully"
        }