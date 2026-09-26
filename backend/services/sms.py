# backend/services/sms.py
"""
AuthShield 360 – OTP Delivery via WhatsApp Cloud API
100% free (1000 conversations/month). Works in Pakistan.
"""

import re
import requests
from flask import current_app


def _normalize_mobile(number: str) -> str:
    """Convert +92-317-5302914 → 923175302914"""
    if not number:
        return ""
    digits = re.sub(r"\D", "", number)
    if digits.startswith("0") and len(digits) == 11:
        digits = "92" + digits[1:]
    return digits


def _mask_number(n: str) -> str:
    if len(n) < 6:
        return "****"
    return n[:4] + "*" * (len(n) - 8) + n[-4:]


def send_sms(to_number: str, message: str, otp: str = "") -> dict:
    """
    Send OTP via WhatsApp Cloud API.
    Returns: {"ok": bool, "error": str|None, "dev_hint": bool}
    """
    cfg = current_app.config
    normalized = _normalize_mobile(to_number)

    # DEV MODE
    if cfg.get("DEV_MODE_PRINT_OTP", False):
        current_app.logger.info(f"[DEV WHATSAPP → {normalized}] {message}")
        return {"ok": False, "error": "dev_mode", "dev_hint": True}

    token = (cfg.get("WHATSAPP_TOKEN") or "").strip()
    phone_id = (cfg.get("WHATSAPP_PHONE_ID") or "").strip()

    if not (token and phone_id):
        current_app.logger.warning("WhatsApp credentials not set")
        return {"ok": False, "error": "no_credentials", "dev_hint": True}

    if not normalized:
        return {"ok": False, "error": "invalid_number", "dev_hint": False}

    # ============================================================
    # WhatsApp Cloud API endpoint
    # ============================================================
    url = f"https://graph.facebook.com/v20.0/{phone_id}/messages"

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": normalized,
        "type": "text",
        "text": {
            "preview_url": False,
            "body": message,
        },
    }

    current_app.logger.info(f"[WhatsApp] Sending to {_mask_number(normalized)}")

    try:
        r = requests.post(url, json=payload, headers=headers, timeout=15)
        body = (r.text or "").strip()
        current_app.logger.info(f"[WhatsApp] Response ({r.status_code}): {body[:250]}")

        try:
            data = r.json()
        except Exception:
            data = {}

        # Success: {"messages":[{"id":"wamid.xxx"}], ...}
        msgs = data.get("messages")
        if r.status_code == 200 and isinstance(msgs, list) and msgs:
            msg_id = msgs[0].get("id", "N/A")
            current_app.logger.info(f"✅ WhatsApp sent to {_mask_number(normalized)} | id={msg_id}")
            return {"ok": True, "error": None, "dev_hint": False}

        # Error
        err_obj = data.get("error") or {}
        err_msg = err_obj.get("message") or body[:200] or "Unknown error"
        current_app.logger.error(f"❌ WhatsApp rejected | {err_msg}")
        return {"ok": False, "error": str(err_msg)[:200], "dev_hint": True}

    except requests.exceptions.ConnectionError as e:
        current_app.logger.error(f"WhatsApp network/DNS failed: {e}")
        return {"ok": False, "error": "network_unreachable", "dev_hint": True}
    except requests.exceptions.Timeout:
        current_app.logger.error("WhatsApp timeout")
        return {"ok": False, "error": "timeout", "dev_hint": True}
    except Exception as e:
        current_app.logger.error(f"WhatsApp error: {type(e).__name__}: {e}")
        return {"ok": False, "error": str(e)[:120], "dev_hint": True}