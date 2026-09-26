# backend/routes/portal.py
from flask import Blueprint, jsonify, g
from backend.models import StudentRecord, Assignment, ExamResult
from backend.security import role_required
from backend.services.audit import log_event

portal_bp = Blueprint("portal", __name__, url_prefix="/api/portal")


@portal_bp.route("/records", methods=["GET"])
@role_required("student", "teacher", "admin")
def records():
    if g.user.role == "student":
        rows = StudentRecord.query.filter_by(owner_username=g.user.username).all()
    elif g.user.role == "teacher":
        rows = StudentRecord.query.all()
    else:
        rows = StudentRecord.query.all()
    return jsonify({"ok": True, "data": [
        {"id": r.student_code, "name": r.name, "class": r.class_name,
         "attendance": r.attendance, "status": r.status} for r in rows
    ]})


@portal_bp.route("/assignments", methods=["GET"])
@role_required("student", "teacher", "admin")
def assignments():
    if g.user.role == "student" and g.user.class_name:
        rows = Assignment.query.filter(
            (Assignment.target_class == g.user.class_name) |
            (Assignment.target_class == "All")
        ).all()
    else:
        rows = Assignment.query.order_by(Assignment.due_date).all()
    return jsonify({"ok": True, "data": [
        {"title": a.title, "due": a.due_date, "status": a.status, "for": a.target_class}
        for a in rows
    ]})


@portal_bp.route("/results", methods=["GET"])
@role_required("student", "teacher", "admin")
def results():
    if g.user.role == "student":
        rows = ExamResult.query.filter_by(owner_username=g.user.username).all()
    else:
        rows = ExamResult.query.all()
    return jsonify({"ok": True, "data": [
        {"student": r.student_name, "subject": r.subject,
         "score": r.score, "grade": r.grade} for r in rows
    ]})