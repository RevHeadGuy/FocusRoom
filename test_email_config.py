import os
from dotenv import load_dotenv

load_dotenv()

print(
    "EMAIL_SENDER:",
    os.getenv("EMAIL_SENDER")
)

print(
    "EMAIL_RECIPIENT:",
    os.getenv("EMAIL_RECIPIENT")
)

print(
    "EMAIL_PASSWORD configured:",
    bool(os.getenv("EMAIL_PASSWORD"))
)