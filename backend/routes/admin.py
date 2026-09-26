# backend/routes/admin.py
from flask import Blueprint, jsonify, request, g
from datetime import datetime
from backend.database import db
from backend.models import User, Session, AuditLog, TestMatrixResult, StudentRecord
from backend.security import role_required, hash_password
from backend.middleware import admin_ip_guard
from backend.services.audit import log_event

admin_bp = Blueprint("admin", __name__, url_prefix="/api/admin")


# ============ Overview ============
@admin_bp.route("/overview", methods=["GET"])
@admin_ip_guard
@role_required("admin")
def overview():
    return jsonify({"ok": True, "data": {
        "total_users": User.query.count(),
        "students": User.query.filter_by(role="student").count(),
        "teachers": User.query.filter_by(role="teacher").count(),
        "admins": User.query.filter_by(role="admin").count(),
        "active_sessions": Session.query.filter_by(
            stage="authenticated", revoked=False).count(),
    }})


# ============ Users CRUD ============
@admin_bp.route("/users", methods=["GET"])
@admin_ip_guard
@role_required("admin")
def list_users():
    users = User.query.order_by(User.role, User.username).all()
    return jsonify({"ok": True, "data": [{
        "id": u.id, "username": u.username, "display_name": u.display_name,
        "email": u.email, "mobile": u.mobile, "role": u.role,
        "class_name": u.class_name, "is_active": u.is_active,
        "last_login": u.last_login.isoformat() + "Z" if u.last_login else None,
    } for u in users]})


@admin_bp.route("/users", methods=["POST"])
@admin_ip_guard
@role_required("admin")
def create_user():
    d = request.get_json() or {}
    username = (d.get("username") or "").strip().lower()
    if not username or User.query.filter_by(username=username).first():
        return jsonify({"ok": False, "message": "Username exists or invalid"}), 400
    u = User(
        username=username,
        display_name=d.get("display_name", username),
        email=d.get("email", f"{username}@authshield.edu"),
        mobile=d.get("mobile", "+92-300-0000000"),
        password_hash=hash_password(d.get("password", "Student@123")),
        role=d.get("role", "student"),
        class_name=d.get("class_name"),
    )
    db.session.add(u)
    db.session.commit()
    log_event("User Created", "Admin", "INFO",
              f"User {username} created", g.user.username, g.user.role)
    return jsonify({"ok": True, "id": u.id})


@admin_bp.route("/users/<int:uid>", methods=["PUT"])
@admin_ip_guard
@role_required("admin")
def update_user(uid):
    u = User.query.get(uid)
    if not u:
        return jsonify({"ok": False, "message": "User not found"}), 404
    d = request.get_json() or {}
    for field in ("display_name", "email", "mobile", "role", "class_name"):
        if field in d:
            setattr(u, field, d[field])
    if "password" in d and d["password"]:
        u.password_hash = hash_password(d["password"])
    if "is_active" in d:
        u.is_active = bool(d["is_active"])
    db.session.commit()
    log_event("User Updated", "Admin", "INFO",
              f"User {u.username} updated", g.user.username, g.user.role)
    return jsonify({"ok": True})


@admin_bp.route("/users/<int:uid>", methods=["DELETE"])
@admin_ip_guard
@role_required("admin")
def delete_user(uid):
    u = User.query.get(uid)
    if not u:
        return jsonify({"ok": False, "message": "Not found"}), 404
    if u.username == g.user.username:
        return jsonify({"ok": False, "message": "Cannot delete yourself"}), 400
    # Revoke sessions and delete record
    Session.query.filter_by(user_id=uid).update({"revoked": True})
    StudentRecord.query.filter_by(owner_username=u.username).delete()
    db.session.delete(u)
    db.session.commit()
    log_event("User Deleted", "Admin", "INFO",
              f"User {u.username} deleted", g.user.username, g.user.role)
    return jsonify({"ok": True})


@admin_bp.route("/users/<int:uid>/force-logout", methods=["POST"])
@admin_ip_guard
@role_required("admin")
def force_logout(uid):
    count = Session.query.filter_by(user_id=uid, revoked=False)\
        .update({"revoked": True})
    db.session.commit()
    log_event("Force Logout", "Admin", "INFO",
              f"Revoked {count} sessions for user_id={uid}",
              g.user.username, g.user.role)
    return jsonify({"ok": True, "revoked": count})


# ============ Sessions ============
@admin_bp.route("/sessions", methods=["GET"])
@admin_ip_guard
@role_required("admin")
def list_sessions():
    now = datetime.utcnow()
    rows = Session.query.filter(
        Session.stage == "authenticated",
        Session.revoked == False,
        Session.expires_at > now,
    ).order_by(Session.last_seen.desc()).limit(100).all()
    data = []
    for s in rows:
        u = User.query.get(s.user_id) if s.user_id else None
        data.append({
            "session_id": s.token_hash[:16],
            "user": u.username if u else "-",
            "role": u.role if u else "-",
            "ip": s.ip, "user_agent": s.user_agent,
            "mode": s.mode,
            "last_seen": s.last_seen.isoformat() + "Z",
        })
    return jsonify({"ok": True, "data": data})


# ============ Records CRUD ============
@admin_bp.route("/records", methods=["GET"])
@admin_ip_guard
@role_required("admin")
def list_records():
    rows = StudentRecord.query.order_by(StudentRecord.student_code).all()
    return jsonify({"ok": True, "data": [{
        "id": r.id, "student_code": r.student_code, "name": r.name,
        "class_name": r.class_name, "attendance": r.attendance,
        "status": r.status, "owner_username": r.owner_username,
    } for r in rows]})


@admin_bp.route("/records/<int:rid>", methods=["PUT"])
@admin_ip_guard
@role_required("admin")
def update_record(rid):
    r = StudentRecord.query.get(rid)
    if not r:
        return jsonify({"ok": False, "message": "Not found"}), 404
    d = request.get_json() or {}
    for f in ("name", "class_name", "attendance", "status"):
        if f in d:
            setattr(r, f, d[f])
    db.session.commit()
    log_event("Record Updated", "Admin", "INFO",
              f"Record {r.student_code} updated",
              g.user.username, g.user.role)
    return jsonify({"ok": True})


@admin_bp.route("/records/<int:rid>", methods=["DELETE"])
@admin_ip_guard
@role_required("admin")
def delete_record(rid):
    r = StudentRecord.query.get(rid)
    if not r:
        return jsonify({"ok": False, "message": "Not found"}), 404
    db.session.delete(r)
    db.session.commit()
    log_event("Record Deleted", "Admin", "INFO",
              f"Record {r.student_code} deleted",
              g.user.username, g.user.role)
    return jsonify({"ok": True})


# ============ Logs ============
@admin_bp.route("/logs", methods=["GET"])
@admin_ip_guard
@role_required("admin")
def logs():
    rows = AuditLog.query.order_by(AuditLog.timestamp.desc()).limit(300).all()
    return jsonify({"ok": True, "data": [r.to_dict() for r in rows]})


@admin_bp.route("/logs/clear", methods=["POST"])
@admin_ip_guard
@role_required("admin")
def clear_logs():
    AuditLog.query.delete()
    db.session.commit()
    return jsonify({"ok": True})


# ============ Test Matrix ============
@admin_bp.route("/test-matrix", methods=["GET"])
@role_required("teacher", "admin")
def get_test_matrix():
    rows = TestMatrixResult.query.order_by(TestMatrixResult.test_id).all()
    return jsonify({"ok": True, "data": [{
        "test_id": r.test_id, "user_role": r.user_role,
        "action": r.action, "expected": r.expected,
        "actual": r.actual, "status": r.status,
    } for r in rows]})


@admin_bp.route("/test-matrix/<test_id>", methods=["POST"])
@role_required("teacher", "admin")
def update_test_matrix(test_id):
    d = request.get_json() or {}
    r = TestMatrixResult.query.filter_by(test_id=test_id).first()
    if not r:
        return jsonify({"ok": False, "message": "Not found"}), 404
    if "actual" in d: r.actual = d["actual"]
    if "status" in d: r.status = d["status"]
    r.tester_username = g.user.username
    r.tested_at = datetime.utcnow()
    db.session.commit()
    return jsonify({"ok": True})

@admin_bp.route("/sessions/<session_id>/kill", methods=["POST"])
@admin_ip_guard
@role_required("admin")
def kill_session(session_id):
    # session_id is the first 16 chars of token_hash
    from backend.models import Session
    sessions = Session.query.filter(
        Session.stage == "authenticated",
        Session.revoked == False,
    ).all()
    killed = 0
    for s in sessions:
        if s.token_hash.startswith(session_id):
            s.revoked = True
            killed += 1
    db.session.commit()
    log_event("Session Killed", "Admin", "INFO",
              f"Killed {killed} session(s)",
              g.user.username, g.user.role)
    return jsonify({"ok": True, "killed": killed})