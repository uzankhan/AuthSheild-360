# backend/services/audit.py
from flask import request
from backend.database import db
from backend.models import AuditLog
from backend.security import client_ip, user_agent


def log_event(action, factor=None, result="INFO", details="",
              user=None, role=None, session_ref=None):
    entry = AuditLog(
        username=user,
        role=role,
        action=action,
        factor=factor,
        result=result,
        details=(details or "")[:500],
        ip=client_ip(),
        user_agent=(request.headers.get("User-Agent") or "")[:255],
        session_ref=session_ref,
    )
    db.session.add(entry)
    db.session.commit()
    return entry