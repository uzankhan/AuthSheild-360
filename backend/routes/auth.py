# backend/routes/auth.py
"""
AuthShield 360 – Authentication Routes (Role-Based Flow)

Scenario mapping per SRS:
  - student → Password ONLY
  - teacher → Password + Mobile OTP
  - admin   → Password + Mobile OTP + Email OTP
"""

from datetime import datetime, timedelta
from flask import Blueprint, request, jsonify, current_app, make_response, g

from backend.database import db
from backend.models import User, Session, OTPChallenge
from backend.security import (
    verify_password, hash_otp, verify_otp, generate_otp, generate_token,
    sha256_hex, create_session, set_session_cookie, clear_session_cookie,
    get_session_from_cookie, is_locked, record_failure, clear_failures,
    login_required,
)
from backend.services.audit import log_event
from backend.services.sms import send_sms
from backend.services.email import send_email

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")


# ============================================================
# Helpers
# ============================================================
def _json():
    return request.get_json(silent=True) or {}


def _mask_mobile(m: str) -> str:
    if len(m) < 4: return "****"
    return "*" * (len(m) - 4) + m[-4:]


def _mask_email(e: str) -> str:
    if "@" not in e: return "***"
    name, domain = e.split("@", 1)
    masked = (name[0] + "*" * (len(name) - 2) + name[-1]) if len(name) > 2 else name[0] + "*"
    return f"{masked}@{domain}"


ROLE_MODE = {
    "student": "password",
    "teacher": "otp",
    "admin":   "full",
}


# ============================================================
# STEP 1 – Password verification (role decides next step)
# ============================================================
@auth_bp.route("/login", methods=["POST"])
def login():
    data = _json()
    username = (data.get("username") or "").strip().lower()
    password = data.get("password") or ""

    if not username or not password or len(username) > 64 or len(password) > 256:
        log_event("Login Attempt", "Password", "FAIL", "Malformed input", username)
        return jsonify({"ok": False, "message": "Access denied"}), 400

    user = User.query.filter_by(username=username).first()
    generic_fail = ("Access denied", 401)

    # Dummy verify for timing equalization
    if not user or not user.is_active:
        verify_password(
            "$argon2id$v=19$m=65536,t=3,p=4$c29tZXNhbHRzb21lc2FsdA$"
            "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", password,
        )
        log_event("Login Attempt", "Password", "FAIL", "Unknown user", username)
        return jsonify({"ok": False, "message": generic_fail[0]}), generic_fail[1]

    locked, remaining = is_locked(user)
    if locked:
        log_event("Login Attempt", "Password", "LOCKED",
                  f"Locked, {remaining} min remaining", username, user.role)
        return jsonify({"ok": False, "locked": True, "remaining": remaining,
                        "message": f"Account locked. Try again in {remaining} min."}), 423

    if not verify_password(user.password_hash, password):
        count = record_failure(user)
        log_event("Login Attempt", "Password", "FAIL",
                  f"Invalid password (attempt {count})", username, user.role)
        if count >= current_app.config["LOCKOUT_THRESHOLD"]:
            return jsonify({"ok": False, "locked": True,
                            "remaining": current_app.config["LOCKOUT_MINUTES"],
                            "message": "Too many failed attempts. Account locked."}), 423
        return jsonify({"ok": False, "message": generic_fail[0]}), generic_fail[1]

    # Password OK
    clear_failures(user)
    log_event("Password Verified", "Password", "SUCCESS",
              "Credentials accepted", username, user.role)

    mode = ROLE_MODE.get(user.role, "password")

    # ---- Student: done immediately ----
    if mode == "password":
        token, sess = create_session(
            user_id=user.id, stage="authenticated", mode="password",
            lifetime=current_app.config["PERMANENT_SESSION_LIFETIME"],
        )
        log_event("Access Granted", "Password", "SUCCESS",
                  f"Session created (password-only) · Welcome {user.display_name}",
                  user.username, user.role, session_ref=sess.token_hash[:16])

        resp = make_response(jsonify({
            "ok": True,
            "status": "authenticated",
            "mode": "password",
            "message": "Access Granted",
            "user": user.to_public_dict(),
        }))
        set_session_cookie(resp, token,
                           int(current_app.config["PERMANENT_SESSION_LIFETIME"].total_seconds()))
        return resp

    # ---- Teacher / Admin: create pending session and issue mobile OTP ----
    token, sess = create_session(
        user_id=user.id, stage="pending_otp_mobile", mode=mode,
        lifetime=current_app.config["PENDING_SESSION_LIFETIME"],
    )

    log_event("MFA Required", "Role Policy", "INFO",
              f"Role '{user.role}' requires MFA ({mode})",
              user.username, user.role, session_ref=sess.token_hash[:16])

    resp = make_response(_issue_mobile_otp(user, sess, resend=False))
    set_session_cookie(resp, token,
                       int(current_app.config["PENDING_SESSION_LIFETIME"].total_seconds()))
    return resp


# ============================================================
# Mobile OTP issuance
# ============================================================
def _issue_mobile_otp(user, sess, resend=False):
    cfg = current_app.config

    if resend:
        last = (OTPChallenge.query
                .filter_by(session_id=sess.id, purpose="mobile")
                .order_by(OTPChallenge.created_at.desc()).first())
        if last:
            elapsed = (datetime.utcnow() - last.last_sent_at).total_seconds()
            if elapsed < cfg["OTP_RESEND_COOLDOWN"]:
                return jsonify({"ok": False,
                                "message": f"Please wait {int(cfg['OTP_RESEND_COOLDOWN']-elapsed)}s"}), 429
            if last.resend_count >= cfg["OTP_MAX_RESENDS"]:
                return jsonify({"ok": False, "message": "Too many resends. Start over."}), 429

    OTPChallenge.query.filter_by(session_id=sess.id, purpose="mobile", consumed=False)\
        .update({"consumed": True})
    db.session.commit()

    otp = generate_otp(cfg["OTP_LENGTH"])
    challenge_token = generate_token(24)
    prev = (OTPChallenge.query
            .filter_by(session_id=sess.id, purpose="mobile")
            .order_by(OTPChallenge.created_at.desc()).first())

    ch = OTPChallenge(
        challenge_hash=sha256_hex(challenge_token),
        user_id=user.id, session_id=sess.id, purpose="mobile",
        otp_hash=hash_otp(otp), max_attempts=cfg["OTP_MAX_ATTEMPTS"],
        expires_at=datetime.utcnow() + timedelta(seconds=cfg["OTP_MOBILE_VALID_SECONDS"]),
        ip=request.remote_addr or "0.0.0.0",
        resend_count=(prev.resend_count + 1 if prev else 0),
    )
    db.session.add(ch)
    db.session.commit()

    to_number = cfg["TEST_MOBILE"]
    msg = (f"AuthShield 360 verification code: {otp}. "
           f"Valid for {cfg['OTP_MOBILE_VALID_SECONDS']}s. Never share.")

    sms_result = send_sms(to_number, msg)
    sms_ok = sms_result.get("ok", False)
    sms_hint = sms_result.get("dev_hint", False)

    log_event(
        "OTP Sent", "Mobile OTP",
        "SUCCESS" if sms_ok else ("INFO" if sms_hint else "FAIL"),
        f"To {_mask_mobile(to_number)} — {'sent' if sms_ok else (sms_result.get('error') or 'failed')}",
        user.username, user.role, session_ref=sess.token_hash[:16],
    )

    payload = {
        "ok": True,
        "status": "otp_sent",
        "factor": "mobile",
        "destination": _mask_mobile(to_number),
        "expires_in": cfg["OTP_MOBILE_VALID_SECONDS"],
        "challenge_token": challenge_token,
        "delivered": sms_ok,
        "message": (None if sms_ok else
                    ("SMS delivery unavailable — OTP shown on screen for demo."
                     if sms_hint else "SMS could not be delivered.")),
    }
    # DEV fallback: show OTP on screen so demo still works
    if sms_hint:
        payload["dev_otp"] = otp

    return jsonify(payload)


@auth_bp.route("/resend-otp", methods=["POST"])
def resend_otp():
    sess = get_session_from_cookie()
    if not sess or sess.stage not in ("pending_otp_mobile", "pending_otp_email"):
        return jsonify({"ok": False, "message": "Session invalid"}), 401
    user = User.query.get(sess.user_id)

    if sess.stage == "pending_otp_mobile":
        return _issue_mobile_otp(user, sess, resend=True)
    return _issue_email_otp(user, sess, resend=True)


# ============================================================
# STEP 3 – Verify OTP
# ============================================================
@auth_bp.route("/verify-otp", methods=["POST"])
def verify_otp_endpoint():
    sess = get_session_from_cookie()
    if not sess or sess.stage not in ("pending_otp_mobile", "pending_otp_email"):
        return jsonify({"ok": False, "message": "Session invalid or expired"}), 401

    data = _json()
    challenge_token = (data.get("challenge_token") or "").strip()
    otp = (data.get("otp") or "").strip()

    if not challenge_token or not otp or not otp.isdigit():
        return jsonify({"ok": False, "message": "Invalid request"}), 400

    purpose = "mobile" if sess.stage == "pending_otp_mobile" else "email"
    ch = OTPChallenge.query.filter_by(
        challenge_hash=sha256_hex(challenge_token),
        session_id=sess.id, purpose=purpose,
    ).first()

    if not ch or ch.consumed:
        log_event("OTP Verification", f"{purpose.capitalize()} OTP", "FAIL",
                  "Unknown/consumed challenge", session_ref=sess.token_hash[:16])
        return jsonify({"ok": False, "message": "Invalid or expired OTP"}), 400

        # Check expiry with 30-second grace period (network latency buffer)
    from datetime import timedelta as _td
    if ch.expires_at + _td(seconds=30) < datetime.utcnow():
        ch.consumed = True
        db.session.commit()
        log_event("OTP Verification", f"{purpose.capitalize()} OTP", "FAIL",
                  "Expired OTP", session_ref=sess.token_hash[:16])
        return jsonify({"ok": False, "message": "Code expired. Please request a new one."}), 400

    if ch.attempts >= ch.max_attempts:
        ch.consumed = True
        db.session.commit()
        log_event("OTP Verification", f"{purpose.capitalize()} OTP", "FAIL",
                  "Max attempts exceeded", session_ref=sess.token_hash[:16])
        return jsonify({"ok": False, "message": "Too many attempts. Start over."}), 429

    if not verify_otp(ch.otp_hash, otp):
        ch.attempts += 1
        db.session.commit()
        left = ch.max_attempts - ch.attempts
        log_event("OTP Verification", f"{purpose.capitalize()} OTP", "FAIL",
                  f"Wrong OTP ({left} left)", session_ref=sess.token_hash[:16])
        return jsonify({"ok": False, "message": f"Invalid OTP. {left} attempt(s) left."}), 401

    ch.consumed = True
    db.session.commit()
    user = User.query.get(sess.user_id)

    log_event("OTP Verification", f"{purpose.capitalize()} OTP", "SUCCESS",
              "OTP accepted", user.username, user.role, session_ref=sess.token_hash[:16])

    # ---- Admin: mobile done → email OTP ----
    if purpose == "mobile" and sess.mode == "full":
        sess.stage = "pending_otp_email"
        db.session.commit()
        return _issue_email_otp(user, sess, resend=False)

    # ---- Teacher / Admin final ----
    return _finalize_auth(sess, user)


# ============================================================
# Email OTP issuance
# ============================================================
def _issue_email_otp(user, sess, resend=False):
    cfg = current_app.config

    if resend:
        last = (OTPChallenge.query
                .filter_by(session_id=sess.id, purpose="email")
                .order_by(OTPChallenge.created_at.desc()).first())
        if last:
            elapsed = (datetime.utcnow() - last.last_sent_at).total_seconds()
            if elapsed < cfg["OTP_RESEND_COOLDOWN"]:
                return jsonify({"ok": False,
                                "message": f"Please wait {int(cfg['OTP_RESEND_COOLDOWN']-elapsed)}s"}), 429
            if last.resend_count >= cfg["OTP_MAX_RESENDS"]:
                return jsonify({"ok": False, "message": "Too many resends."}), 429

    OTPChallenge.query.filter_by(session_id=sess.id, purpose="email", consumed=False)\
        .update({"consumed": True})
    db.session.commit()

    otp = generate_otp(cfg["OTP_LENGTH"])
    challenge_token = generate_token(24)
    prev = (OTPChallenge.query
            .filter_by(session_id=sess.id, purpose="email")
            .order_by(OTPChallenge.created_at.desc()).first())

    ch = OTPChallenge(
        challenge_hash=sha256_hex(challenge_token),
        user_id=user.id, session_id=sess.id, purpose="email",
        otp_hash=hash_otp(otp), max_attempts=cfg["OTP_MAX_ATTEMPTS"],
        expires_at=datetime.utcnow() + timedelta(seconds=cfg["OTP_EMAIL_VALID_SECONDS"]),
        ip=request.remote_addr or "0.0.0.0",
        resend_count=(prev.resend_count + 1 if prev else 0),
    )
    db.session.add(ch)
    db.session.commit()

    to_email = cfg["TEST_EMAIL"]
    body = (
        f"AuthShield 360 — Email Step-Up Verification\n\n"
        f"Your verification code is: {otp}\n"
        f"Valid for {cfg['OTP_EMAIL_VALID_SECONDS']} seconds.\n"
        f"Never share this code.\n"
    )

    email_result = send_email(to_email, "AuthShield 360 – Email Verification Code", body)
    email_ok = email_result.get("ok", False)
    email_hint = email_result.get("dev_hint", False)

    log_event(
        "OTP Sent", "Email OTP",
        "SUCCESS" if email_ok else ("INFO" if email_hint else "FAIL"),
        f"To {_mask_email(to_email)} — {'sent' if email_ok else (email_result.get('error') or 'failed')}",
        user.username, user.role, session_ref=sess.token_hash[:16],
    )

    payload = {
        "ok": True,
        "status": "otp_sent",
        "factor": "email",
        "destination": _mask_email(to_email),
        "expires_in": cfg["OTP_EMAIL_VALID_SECONDS"],
        "challenge_token": challenge_token,
        "delivered": email_ok,
        "message": (None if email_ok else
                    ("Email delivery unavailable — OTP shown on screen for demo."
                     if email_hint else "Email could not be delivered.")),
    }
    if email_hint:
        payload["dev_otp"] = otp

    return jsonify(payload)


# ============================================================
# Finalize
# ============================================================
def _finalize_auth(sess, user):
    Session.query.filter(Session.user_id == user.id,
                         Session.id != sess.id,
                         Session.revoked == False).update({"revoked": True})

    sess.stage = "authenticated"
    sess.expires_at = datetime.utcnow() + current_app.config["PERMANENT_SESSION_LIFETIME"]
    db.session.commit()

    user.last_login = datetime.utcnow()
    db.session.commit()

    log_event("Access Granted", sess.mode, "SUCCESS",
              f"Session {sess.token_hash[:16]}… created · Welcome {user.display_name}",
              user.username, user.role, session_ref=sess.token_hash[:16])

    resp = make_response(jsonify({
        "ok": True,
        "status": "authenticated",
        "mode": sess.mode,
        "message": "Access Granted",
        "user": user.to_public_dict(),
    }))
    token = request.cookies.get(current_app.config["AUTH_COOKIE_NAME"])
    set_session_cookie(resp, token,
                       int(current_app.config["PERMANENT_SESSION_LIFETIME"].total_seconds()))
    return resp


# ============================================================
# Session info & logout
# ============================================================
@auth_bp.route("/session", methods=["GET"])
def session_info():
    sess = get_session_from_cookie()
    if not sess or sess.stage != "authenticated" or not sess.user_id:
        return jsonify({"ok": False, "message": "Not authenticated"}), 401
    user = User.query.get(sess.user_id)
    if not user or not user.is_active:
        return jsonify({"ok": False, "message": "Not authenticated"}), 401
    return jsonify({
        "ok": True,
        "user": user.to_public_dict(),
        "mode": sess.mode,
        "session_id": sess.token_hash[:16],
        "login_at": sess.created_at.isoformat() + "Z",
    })


@auth_bp.route("/logout", methods=["POST"])
def logout():
    sess = get_session_from_cookie()
    if sess:
        sess.revoked = True
        db.session.commit()
        user = User.query.get(sess.user_id) if sess.user_id else None
        if user:
            log_event("Logout", "Session", "SUCCESS", "User logged out",
                      user.username, user.role, session_ref=sess.token_hash[:16])
    resp = make_response(jsonify({"ok": True}))
    clear_session_cookie(resp)
    return resp