# backend/services/email.py
"""
AuthShield 360 – Email Service (Gmail SMTP)
Sends OTP emails via Gmail App Password.
Never raises — returns a dict with status.
"""

import re
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from flask import current_app

def send_email(to_email: str, subject: str, body_text: str) -> dict:
    """
    Send an email via Gmail SMTP.
    Returns: {"ok": bool, "error": str|None, "dev_hint": bool}
    """
    cfg = current_app.config

    # ---- DEV MODE: Print email body to console instead of sending ----
    if cfg.get("DEV_MODE_PRINT_OTP", False):
        current_app.logger.info(
            f"\n[DEV EMAIL → {to_email}]\n"
            f"Subject: {subject}\n"
            f"Body:\n{body_text}\n"
        )
        return {"ok": False, "error": "dev_mode", "dev_hint": True}

    smtp_user = (cfg.get("SMTP_USER") or "").strip()
    smtp_pass = (cfg.get("SMTP_PASSWORD") or "").replace(" ", "").strip() # Spaces remove karne ke liye
    smtp_host = cfg.get("SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(cfg.get("SMTP_PORT", 587))
    smtp_from = (cfg.get("SMTP_FROM") or smtp_user).strip()

    if not (smtp_user and smtp_pass):
        current_app.logger.warning("SMTP credentials not configured – email not sent")
        return {"ok": False, "error": "no_smtp_credentials", "dev_hint": True}

    # Build the email message
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = smtp_from
    msg["To"] = to_email
    msg.attach(MIMEText(body_text, "plain", "utf-8"))

    # ---- Attempt 1: Try STARTTLS on port 587 (Gmail recommended) ----
    try:
        context = ssl.create_default_context()
        with smtplib.SMTP(smtp_host, smtp_port, timeout=20) as server:
            server.ehlo()
            server.starttls(context=context)
            server.ehlo()  # Re-identify after STARTTLS
            server.login(smtp_user, smtp_pass)
            server.sendmail(smtp_from, [to_email], msg.as_string())
        current_app.logger.info(f"✅ Email sent to {to_email} (STARTTLS)")
        return {"ok": True, "error": None, "dev_hint": False}
    except smtplib.SMTPAuthenticationError as e:
        current_app.logger.error(
            f"❌ SMTP auth failed. Check Gmail App Password. "
            f"(Make sure 2FA is ON and you're using an App Password, not your regular password) | {e}"
        )
        return {"ok": False, "error": "smtp_auth_failed", "dev_hint": True}
    except (smtplib.SMTPException, OSError, ConnectionError) as e:
        current_app.logger.error(f"❌ SMTP error (STARTTLS): {type(e).__name__}: {e}")

    # ---- Attempt 2: Try SSL on port 465 (Fallback) ----
    try:
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(smtp_host, 465, timeout=20, context=context) as server:
            server.login(smtp_user, smtp_pass)
            server.sendmail(smtp_from, [to_email], msg.as_string())
        current_app.logger.info(f"✅ Email sent to {to_email} (SSL fallback)")
        return {"ok": True, "error": None, "dev_hint": False}
    except Exception as e:
        current_app.logger.error(f"❌ SSL fallback failed: {e}")
        return {"ok": False, "error": "network_unreachable", "dev_hint": True}