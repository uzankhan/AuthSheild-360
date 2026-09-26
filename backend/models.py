from datetime import datetime
from backend.database import db # type: ignore[import-not-found]


class User(db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False, index=True)
    email = db.Column(db.String(255), nullable=False)
    mobile = db.Column(db.String(32), nullable=False)
    display_name = db.Column(db.String(128), nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(16), nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    mfa_enabled = db.Column(db.Boolean, default=True, nullable=False)
    failed_count = db.Column(db.Integer, default=0, nullable=False)
    locked_until = db.Column(db.DateTime, nullable=True)
    last_login = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    # NEW: student's own class (for filtering)
    class_name = db.Column(db.String(32), nullable=True)

    def to_public_dict(self):
        return {
            "id": self.id,
            "username": self.username,
            "display_name": self.display_name,
            "role": self.role,
            "email": self.email,
            "mobile": self.mobile,
            "class_name": self.class_name,
        }

class Session(db.Model):
    __tablename__ = "sessions"

    id = db.Column(db.Integer, primary_key=True)
    # Store SHA-256 hash of the token (never plaintext)
    token_hash = db.Column(db.String(128), unique=True, nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    # stage: pending_method | pending_otp_mobile | pending_otp_email | authenticated
    stage = db.Column(db.String(32), nullable=False, default="pending_method")
    mode = db.Column(db.String(16), nullable=True)   # password | otp | full
    ip = db.Column(db.String(64), nullable=False)
    user_agent = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    last_seen = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    revoked = db.Column(db.Boolean, default=False, nullable=False)


class OTPChallenge(db.Model):
    __tablename__ = "otp_challenges"

    id = db.Column(db.Integer, primary_key=True)
    challenge_hash = db.Column(db.String(128), unique=True, nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    session_id = db.Column(db.Integer, db.ForeignKey("sessions.id"), nullable=False)
    purpose = db.Column(db.String(16), nullable=False)   # mobile | email
    otp_hash = db.Column(db.String(255), nullable=False)  # Argon2 hash of OTP
    attempts = db.Column(db.Integer, default=0, nullable=False)
    max_attempts = db.Column(db.Integer, default=5, nullable=False)
    resend_count = db.Column(db.Integer, default=0, nullable=False)
    last_sent_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    consumed = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    ip = db.Column(db.String(64), nullable=False)


class AuditLog(db.Model):
    __tablename__ = "audit_logs"

    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    username = db.Column(db.String(64), nullable=True)
    role = db.Column(db.String(16), nullable=True)
    action = db.Column(db.String(64), nullable=False)
    factor = db.Column(db.String(32), nullable=True)
    result = db.Column(db.String(16), nullable=False)   # SUCCESS | FAIL | LOCKED | INFO
    details = db.Column(db.String(512), nullable=True)
    ip = db.Column(db.String(64), nullable=True)
    user_agent = db.Column(db.String(255), nullable=True)
    session_ref = db.Column(db.String(128), nullable=True)

    def to_dict(self):
        return {
            "time": self.timestamp.isoformat() + "Z",
            "user": self.username or "-",
            "role": self.role or "-",
            "action": self.action,
            "factor": self.factor or "-",
            "result": self.result,
            "details": self.details or "",
            "ip": self.ip or "-",
        }


# ---------- Fictional portal data ----------

class StudentRecord(db.Model):
    __tablename__ = "student_records"
    id = db.Column(db.Integer, primary_key=True)
    student_code = db.Column(db.String(32), unique=True, nullable=False)
    name = db.Column(db.String(128), nullable=False)
    class_name = db.Column(db.String(32), nullable=False)
    attendance = db.Column(db.String(16), nullable=False)
    status = db.Column(db.String(32), nullable=False)
    # NEW: which user owns this record
    owner_username = db.Column(db.String(64), nullable=True, index=True)


class Assignment(db.Model):
    __tablename__ = "assignments"
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    due_date = db.Column(db.String(32), nullable=False)
    status = db.Column(db.String(32), nullable=False)
    target_class = db.Column(db.String(64), nullable=False)


class ExamResult(db.Model):
    __tablename__ = "exam_results"
    id = db.Column(db.Integer, primary_key=True)
    student_name = db.Column(db.String(128), nullable=False)
    subject = db.Column(db.String(64), nullable=False)
    score = db.Column(db.Integer, nullable=False)
    grade = db.Column(db.String(8), nullable=False)
    owner_username = db.Column(db.String(64), nullable=True, index=True)


class TestMatrixResult(db.Model):
    __tablename__ = "test_matrix"
    id = db.Column(db.Integer, primary_key=True)
    test_id = db.Column(db.String(16), unique=True, nullable=False)
    user_role = db.Column(db.String(32), nullable=False)
    action = db.Column(db.String(255), nullable=False)
    expected = db.Column(db.String(255), nullable=False)
    actual = db.Column(db.String(255), nullable=True)
    status = db.Column(db.String(16), nullable=True)  # PASS | FAIL | PENDING
    tested_at = db.Column(db.DateTime, nullable=True)
    evidence = db.Column(db.Text, nullable=True)
    tester_username = db.Column(db.String(64), nullable=True)