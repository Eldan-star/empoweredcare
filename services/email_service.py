import aiosmtplib
from email.message import EmailMessage
from config import SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, SMTP_FROM, SMTP_USE_TLS, FRONTEND_URL
from typing import Optional
import logging

logger = logging.getLogger(__name__)

async def send_email(to: str, subject: str, content: str):
    """Send an email using aiosmtplib."""
    message = EmailMessage()
    message["From"] = SMTP_FROM
    message["To"] = to
    message["Subject"] = subject
    message.set_content(content)

    if not SMTP_USER or not SMTP_PASSWORD:
        logger.info("\n" + "="*50)
        logger.info(f"📧 [DEV EMAIL SIMULATION] To: {to}")
        logger.info(f"Subject: {subject}")
        logger.info(f"Content:\n{content}")
        logger.info("="*50 + "\n")
        return True

    try:
        if SMTP_USE_TLS:
            await aiosmtplib.send(
                message,
                hostname=SMTP_HOST,
                port=SMTP_PORT,
                username=SMTP_USER,
                password=SMTP_PASSWORD,
                use_tls=False,  # Set to False because we're using STARTTLS (port 587)
                start_tls=True,
            )
        else:
            await aiosmtplib.send(
                message,
                hostname=SMTP_HOST,
                port=SMTP_PORT,
                username=SMTP_USER,
                password=SMTP_PASSWORD,
                use_tls=False,
            )
        logger.info(f"📧 Email sent successfully to {to}")
        return True
    except Exception as e:
        logger.error(f"❌ Failed to send email to {to}: {e}")
        logger.info("⚠️ System continuing despite email failure (Development fallback).")
        # Log the invite link since it failed to send
        logger.info("\n" + "="*50)
        logger.info(f"📧 [DEV EMAIL SIMULATION] To: {to}")
        logger.info(f"Subject: {subject}")
        logger.info(f"Content:\n{content}")
        logger.info("="*50 + "\n")
        return True

async def send_invitation_email(email: str, token: str, frontend_url: Optional[str] = None):
    """Send an invitation email to a new employee."""
    base_url = frontend_url or FRONTEND_URL
    invite_link = f"{base_url}/register?token={token}"
    subject = "Invitation to Join Empowered Care"
    content = f"""Welcome to Empowered Care!

An administrator has invited you to join the Empowered Care system.
Please click the link below to complete your registration and set your password:

{invite_link}

The link will expire in 48 hours.

If you were not expecting this invitation, please ignore this email."""
    
    return await send_email(email, subject, content)

async def send_reset_password_email(email: str, token: str, frontend_url: Optional[str] = None):
    """Send a password reset email."""
    base_url = frontend_url or FRONTEND_URL
    reset_link = f"{base_url}/reset-password?token={token}"
    subject = "Reset Your Password - Empowered Care"
    content = f"""Hello,

You have requested to reset your password for your Empowered Care account.
Please click the link below to reset your password:

{reset_link}

The link will expire in 1 hour.

If you did not request a password reset, please ignore this email and your password will remain unchanged."""
    
    return await send_email(email, subject, content)
