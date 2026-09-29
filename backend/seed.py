# backend/seed.py
from backend.database import db
from backend.models import (
    User, StudentRecord, Assignment, ExamResult, TestMatrixResult,
)
from backend.security import hash_password


STUDENTS = [
    {"username": "hamza1",    "name": "Hamza Khan",         "class": "10-A", "attendance": "92%", "status": "Active"},
    {"username": "aqid1",     "name": "Rao Muhammad Aqid",  "class": "10-A", "attendance": "88%", "status": "Active"},
    {"username": "saniya1",   "name": "Saniya Kayani",      "class": "9-B",  "attendance": "95%", "status": "Active"},
    {"username": "huzaifa1",  "name": "Huzaifa Imran",      "class": "11-C", "attendance": "79%", "status": "Warning"},
    {"username": "arham1",    "name": "Arham",              "class": "12-A", "attendance": "97%", "status": "Active"},
    {"username": "aman1",     "name": "Aman-ul-Haq",        "class": "12-A", "attendance": "97%", "status": "Active"},
    {"username": "zara1",     "name": "Zara Sheikh",        "class": "10-B", "attendance": "90%", "status": "Active"},
    {"username": "ali1",      "name": "Ali Hassan",         "class": "9-A",  "attendance": "85%", "status": "Active"},
]


def seed_data():
    if User.query.first():
        return

    # ---------- Admin & Teacher ----------
    users = [
        User(username="admin1", display_name="Imran Khan",
             email="imrankhan@aptech.edu", mobile="+92-300-0000003",
             password_hash=hash_password("Admin@123"), role="admin"),
        User(username="teacher1", display_name="Sir Mustafa Raza",
             email="syedmustafa.raza@gmail.com", mobile="+92-300-0000002",
             password_hash=hash_password("Teacher@123"), role="teacher"),
    ]

    # ---------- Student users + records ----------
    records = []
    for i, s in enumerate(STUDENTS, start=1):
        users.append(User(
            username=s["username"],
            display_name=s["name"],
            email=f"{s['username']}@authshield.edu",
            mobile=f"+92-300-00000{i:02d}",
            password_hash=hash_password("Student@123"),
            role="student",
            class_name=s["class"],
        ))
        records.append(StudentRecord(
            student_code=f"S-{1000+i}",
            name=s["name"],
            class_name=s["class"],
            attendance=s["attendance"],
            status=s["status"],
            owner_username=s["username"],
        ))

    db.session.add_all(users)
    db.session.add_all(records)

    # ---------- Assignments ----------
    db.session.add_all([
        Assignment(title="Mathematics – Quadratic Equations",   due_date="2026-09-28", status="Pending",   target_class="Class 10"),
        Assignment(title="Physics – Laws of Motion Lab Report",  due_date="2026-09-25", status="Submitted", target_class="Class 11"),
        Assignment(title="English – Essay on Cyber Safety",      due_date="2026-10-02", status="Pending",   target_class="All"),
        Assignment(title="Computer Science – AuthShield Case Study", due_date="2026-10-05", status="Open", target_class="Class 12"),
        Assignment(title="Chemistry – Periodic Table Quiz",      due_date="2026-09-30", status="Pending",   target_class="Class 9"),
    ])

    # ---------- Exam Results ----------
    results = []
    subjects = ["Mathematics", "Physics", "English", "Computer Science", "Chemistry"]
    import random
    for s in STUDENTS:
        for subj in random.sample(subjects, 3):
            score = random.randint(65, 98)
            grade = ("A+" if score >= 90 else "A" if score >= 80 else
                     "B" if score >= 70 else "C")
            results.append(ExamResult(
                student_name=s["name"], subject=subj,
                score=score, grade=grade,
                owner_username=s["username"],
            ))
    db.session.add_all(results)

    # ---------- Test Matrix ----------
    tests = [
        ("T01", "Any",     "Valid password-only login",                 "Access granted"),
        ("T02", "Any",     "Compromised test password (password-only)", "Access granted (baseline risk)"),
        ("T03", "Any",     "Correct password without required MFA",     "Access denied / MFA required"),
        ("T04", "Any",     "Valid OTP",                                  "Access granted"),
        ("T05", "Any",     "Invalid OTP",                                "Access denied"),
        ("T06", "Any",     "OTP submitted outside valid time window",   "Access denied"),
        ("T07", "Any",     "Repeated failed login attempts (>=5)",      "Temporary lockout"),
        ("T08", "Student", "Attempt Teacher/Admin resource",            "Access denied"),
        ("T09", "Teacher", "Attempt Admin-only resource",               "Access denied"),
        ("T10", "Any",     "Logout then reuse previous session",        "Session invalidated"),
        ("T11", "Any",     "Email step-up valid OTP",                   "Access granted"),
        ("T12", "Any",     "Email step-up invalid/expired",             "Access denied"),
    ]
    for tid, role, action, expected in tests:
        db.session.add(TestMatrixResult(
            test_id=tid, user_role=role, action=action,
            expected=expected, status="PENDING",
        ))

    db.session.commit()
    print("✅ Seed complete — students, records, results inserted")