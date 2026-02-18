import argparse
import os
import smtplib
from email.message import EmailMessage


def _bool_from_env(var_name: str, default: bool = False) -> bool:
    """Parse boolean-like environment variables."""
    raw_value = os.environ.get(var_name)
    if raw_value is None:
        return default
    return raw_value.strip().lower() in {"1", "true", "yes", "on"}


def _get_smtp_config() -> dict:
    """Collect SMTP configuration from environment variables."""
    host = os.environ.get("SMTP_HOST")
    if not host:
        raise RuntimeError("Environment variable SMTP_HOST must be set.")

    port = int(os.environ.get("SMTP_PORT", "587"))
    username = os.environ.get("SMTP_USERNAME")
    password = os.environ.get("SMTP_PASSWORD")
    sender = os.environ.get("SMTP_SENDER", username)
    if not sender:
        raise RuntimeError("Environment variable SMTP_SENDER or SMTP_USERNAME must be set.")

    return {
        "host": host,
        "port": port,
        "username": username,
        "password": password,
        "sender": sender,
        "use_tls": _bool_from_env("SMTP_USE_TLS", True),
        "use_ssl": _bool_from_env("SMTP_USE_SSL", False),
    }


def send_email(recipient: str, subject: str, body: str) -> None:
    """Send an email using SMTP credentials from environment variables."""
    config = _get_smtp_config()

    message = EmailMessage()
    message["From"] = config["sender"]
    message["To"] = recipient
    message["Subject"] = subject
    message.set_content(body)

    smtp_client_cls = smtplib.SMTP_SSL if config["use_ssl"] else smtplib.SMTP

    with smtp_client_cls(config["host"], config["port"], timeout=30) as client:
        if not config["use_ssl"] and config["use_tls"]:
            client.starttls()

        if config["username"] and config["password"]:
            client.login(config["username"], config["password"])

        client.send_message(message)


def main() -> None:
    parser = argparse.ArgumentParser(description="Send an email via SMTP.")
    parser.add_argument("recipient", help="Email address of the recipient.")
    parser.add_argument("subject", help="Subject line for the email.")
    parser.add_argument("body", help="Body text for the email.")
    args = parser.parse_args()

    send_email(args.recipient, args.subject, args.body)


if __name__ == "__main__":
    main()
