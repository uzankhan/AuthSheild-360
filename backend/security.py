# backend/security.py
"""
AuthShield 360 – Security Core
Handles: Argon2id password hashing, OTP hashing, secure token generation,
session cookie management, RBAC decorators, and failed-login lockout.
"""

import hashlib
import secrets
from datetime import datetime, timedelta
from functools import wraps

from flask import request, jsonify, g, current_app
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, VerificationError, InvalidHashError

from backend.database import db
from backend.models import User, Session, OTPChallenge, AuditLog


# ============================================================
# Argon2id Password Hasher (OWASP recommended params)
# ============================================================
_ph = PasswordHasher(
    time_cost=3,        # iterations
    memory_cost=65536,  # 64 MB
    parallelism=4,
    hash_len=32,
    salt_len=16,
)


def hash_password(pw: str) -> str:
    """Hash a plaintext password with Argon2id."""
    return _ph.hash(pw)


def verify_password(hash_: str, pw: str) -> bool:
    """Constant-time verification of password against Argon2id hash."""
    try:
        return _ph.verify(hash_, pw)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def hash_otp(otp: str) -> str:
    """Hash a plaintext OTP with Argon2id before storing."""
    return _ph.hash(otp)


def verify_otp(hash_: str, otp: str) -> bool:
    """Constant-time verification of OTP against Argon2id hash."""
    try:
        return _ph.verify(hash_, otp)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


# ============================================================
# Cryptographic token generation
# ============================================================
def generate_token(nbytes: int = 32) -> str:
    """URL-safe random token (used for session tokens, challenge tokens)."""
    return secrets.token_urlsafe(nbytes)


def sha256_hex(s: str) -> str:
    """SHA-256 hash as hex string (used for storing session token hashes)."""
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def generate_otp(length: int = 6) -> str:
    """Cryptographically secure numeric OTP, zero-padded."""
    return str(secrets.randbelow(10 ** length)).zfill(length)


# ============================================================
# Client information helpers
# ============================================================
def client_ip() -> str:
    """Return client IP, honoring X-Forwarded-For only if TRUST_PROXY=True."""
    if current_app.config.get("TRUST_PROXY"):
        xff = request.headers.get("X-Forwarded-For", "")
        if xff:
            return xff.split(",")[0].strip()
    return request.remote_addr or "0.0.0.0"


def user_agent() -> str:
    """Return trimmed User-Agent string."""
    return (request.headers.get("User-Agent") or "")[:255]


# ============================================================
# Custom auth session (separate cookie from Flask's session)
# ============================================================
def _auth_cookie_name() -> str:
    """Get the custom auth cookie name from config."""
    return current_app.config.get(
        "AUTH_COOKIE_NAME",
        current_app.config.get("SESSION_COOKIE_NAME", "as360_sid"),
    )


def get_session_from_cookie():
    """
    Read session token from the custom auth cookie and return the
    matching Session row if valid (not revoked, not expired).
    Returns None otherwise.
    """
    token = request.cookies.get(_auth_cookie_name())
    if not token:
        return None

    token_hash = sha256_hex(token)
    s = Session.query.filter_by(token_hash=token_hash, revoked=False).first()

    if not s:
        return None

    if s.expires_at < datetime.utcnow():
        s.revoked = True
        db.session.commit()
        return None

    s.last_seen = datetime.utcnow()
    db.session.commit()
    return s


def create_session(user_id, stage: str, mode: str, lifetime: timedelta):
    """
    Create a new Session row and return (plaintext_token, Session_row).
    The plaintext token goes into the cookie; only its SHA-256 hash is stored.
    """
    token = generate_token()
    s = Session(
        token_hash=sha256_hex(token),
        user_id=user_id,
        stage=stage,
        mode=mode,
        ip=client_ip(),
        user_agent=user_agent(),
        expires_at=datetime.utcnow() + lifetime,
    )
    db.session.add(s)
    db.session.commit()
    return token, s


def set_session_cookie(resp, token: str, max_age_seconds: int):
    """Set the custom auth cookie with hardened flags."""
    resp.set_cookie(
        _auth_cookie_name(),
        token,
        max_age=max_age_seconds,
        httponly=True,
        secure=current_app.config.get("SESSION_COOKIE_SECURE", False),
        samesite="Lax",
        path="/",
    )
    return resp


def clear_session_cookie(resp):
    """Delete the custom auth cookie."""
    resp.delete_cookie(_auth_cookie_name(), path="/")
    return resp


# ============================================================
# Decorators: login_required and role_required (RBAC)
# ============================================================
def login_required(f):
    """Block request if there's no valid authenticated session."""
    @wraps(f)
    def wrapper(*args, **kwargs):
        s = get_session_from_cookie()

        if not s or s.stage != "authenticated" or not s.user_id:
            return jsonify({"ok": False, "message": "Authentication required"}), 401

        user = User.query.get(s.user_id)
        if not user or not user.is_active:
            return jsonify({"ok": False, "message": "Account disabled"}), 403

        g.session = s
        g.user = user
        return f(*args, **kwargs)
    return wrapper


def role_required(*roles):
    """
    Restrict a route to specific roles (e.g. admin, teacher).
    Logs an RBAC violation on failure.
    """
    def deco(f):
        @wraps(f)
        @login_required
        def wrapper(*args, **kwargs):
            if g.user.role not in roles:
                # Lazy import to avoid circular dependency
                try:
                    from backend.services.audit import log_event
                    log_event(
                        action="Unauthorized Access Attempt",
                        factor="RBAC",
                        result="FAIL",
                        details=f"Role '{g.user.role}' tried to access {request.path}",
                        user=g.user.username,
                        role=g.user.role,
                        session_ref=g.session.token_hash[:16],
                    )
                except Exception:
                    pass
                return jsonify({"ok": False, "message": "Access denied"}), 403
            return f(*args, **kwargs)
        return wrapper
    return deco


# ============================================================
# Failed-login lockout
# ============================================================
def is_locked(user: User):
    """
    Check if account is currently locked.
    Returns (locked: bool, remaining_minutes: int).
    Auto-clears expired lockouts.
    """
    if user.locked_until and user.locked_until > datetime.utcnow():
        remaining = int((user.locked_until - datetime.utcnow()).total_seconds() / 60) + 1
        return True, remaining

    if user.locked_until and user.locked_until <= datetime.utcnow():
        user.locked_until = None
        user.failed_count = 0
        db.session.commit()

    return False, 0


def record_failure(user: User) -> int:
    """
    Increment failed_count. If threshold reached, lock the account.
    Returns the current failed attempt count.
    """
    user.failed_count = (user.failed_count or 0) + 1

    threshold = current_app.config.get("LOCKOUT_THRESHOLD", 5)
    lockout_minutes = current_app.config.get("LOCKOUT_MINUTES", 15)

    if user.failed_count >= threshold:
        user.locked_until = datetime.utcnow() + timedelta(minutes=lockout_minutes)

    db.session.commit()
    return user.failed_count


def clear_failures(user: User):
    """Reset failed-attempt counter and lockout after successful login."""
    user.failed_count = 0
    user.locked_until = None
    db.session.commit()