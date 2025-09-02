#!/usr/bin/env python3
import os
from datetime import datetime, date
from collections import defaultdict
from flask import Flask, render_template, redirect, url_for, request, flash, jsonify, send_file
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, login_required, logout_user, current_user, UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, "kidanta.db")

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY","dev-secret-key")
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{DB_PATH}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"

# -------------------- Models --------------------
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), default="teacher")  # teacher/admin

    def set_password(self, pw):
        self.password_hash = generate_password_hash(pw)

    def check_password(self, pw):
        return check_password_hash(self.password_hash, pw)

class Student(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(120), nullable=False)
    age = db.Column(db.Integer, nullable=False)
    gender = db.Column(db.String(20))
    notes = db.Column(db.Text)
    created_by = db.Column(db.Integer, db.ForeignKey("user.id"))

class Activity(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text)
    category = db.Column(db.String(80))
    age_min = db.Column(db.Integer, default=6)
    age_max = db.Column(db.Integer, default=12)
    created_by = db.Column(db.Integer, db.ForeignKey("user.id"))

class BehaviorLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("student.id"), nullable=False)
    log_date = db.Column(db.Date, nullable=False, default=date.today)
    mood = db.Column(db.Integer, default=3)  # 1-5
    focus = db.Column(db.Integer, default=3) # 1-5
    social = db.Column(db.Integer, default=3) # 1-5
    notes = db.Column(db.Text)

class ActivityLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("student.id"), nullable=False)
    activity_id = db.Column(db.Integer, db.ForeignKey("activity.id"), nullable=False)
    done_at = db.Column(db.Date, nullable=False, default=date.today)
    remark = db.Column(db.Text)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# -------------------- CLI seed --------------------
@app.cli.command("initdb")
def initdb():
    db.create_all()
    if not User.query.filter_by(email="admin@kidanta.local").first():
        admin = User(name="Admin", email="admin@kidanta.local", role="admin")
        admin.set_password("admin123")
        db.session.add(admin)
        db.session.commit()
    if Activity.query.count() == 0:
        seed_activities = [
            ("อ่านนิทานภาพ", "เสริมจินตนาการและการอ่าน", "ภาษา", 6, 8),
            ("เกมต่อบล็อก", "ฝึกตรรกะและมอเตอร์", "STEM", 6, 9),
            ("สะกดคำพื้นฐาน", "ฝึกภาษาไทย", "ภาษา", 7, 10),
            ("วิทย์สนุกที่บ้าน", "ทดลองง่ายๆ", "วิทยาศาสตร์", 8, 12),
            ("ฟุตบอลยิ้ม", "เล่นทีมและกติกา", "กีฬา", 9, 12),
        ]
        for t, d, c, amin, amax in seed_activities:
            db.session.add(Activity(title=t, description=d, category=c, age_min=amin, age_max=amax))
        db.session.commit()
    print("Initialized database. Admin: admin@kidanta.local / admin123")

# -------------------- Auth --------------------
@app.route("/register", methods=["GET","POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name","").strip()
        email = request.form.get("email","").strip().lower()
        password = request.form.get("password","")
        if not name or not email or not password:
            flash("กรอกข้อมูลให้ครบ", "danger")
            return redirect(url_for("register"))
        if User.query.filter_by(email=email).first():
            flash("อีเมลนี้ถูกใช้แล้ว", "warning")
            return redirect(url_for("register"))
        u = User(name=name, email=email)
        u.set_password(password)
        db.session.add(u)
        db.session.commit()
        flash("สมัครสมาชิกสำเร็จ, กรุณาเข้าสู่ระบบ", "success")
        return redirect(url_for("login"))
    return render_template("register.html")

@app.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email","").strip().lower()
        password = request.form.get("password","")
        u = User.query.filter_by(email=email).first()
        if u and u.check_password(password):
            login_user(u)
            return redirect(url_for("dashboard"))
        flash("อีเมลหรือรหัสผ่านไม่ถูกต้อง", "danger")
    return render_template("login.html")

@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"))

# -------------------- Core pages --------------------
@app.route("/")
@login_required
def dashboard():
    student_count = Student.query.count()
    activity_count = Activity.query.count()
    today = date.today()
    todays_logs = BehaviorLog.query.filter_by(log_date=today).count()
    return render_template("dashboard.html",
                           student_count=student_count,
                           activity_count=activity_count,
                           todays_logs=todays_logs)

# Students
@app.route("/students")
@login_required
def students():
    q = request.args.get("q","").strip()
    query = Student.query
    if q:
        query = query.filter(Student.full_name.ilike(f"%{q}%"))
    rows = query.order_by(Student.full_name.asc()).all()
    return render_template("students.html", rows=rows, q=q)

@app.route("/students/new", methods=["GET","POST"])
@login_required
def student_new():
    if request.method == "POST":
        full_name = request.form.get("full_name","").strip()
        age = int(request.form.get("age", "0") or 0)
        gender = request.form.get("gender","")
        notes = request.form.get("notes","")
        if not full_name or age < 6 or age > 12:
            flash("กรอกชื่อและอายุ 6-12 ปีให้ถูกต้อง", "danger")
            return redirect(url_for("student_new"))
        s = Student(full_name=full_name, age=age, gender=gender, notes=notes, created_by=current_user.id)
        db.session.add(s)
        db.session.commit()
        flash("บันทึกข้อมูลนักเรียนแล้ว", "success")
        return redirect(url_for("students"))
    return render_template("student_form.html", item=None)

@app.route("/students/<int:sid>/edit", methods=["GET","POST"])
@login_required
def student_edit(sid):
    s = Student.query.get_or_404(sid)
    if request.method == "POST":
        s.full_name = request.form.get("full_name","").strip()
        s.age = int(request.form.get("age","0") or 0)
        s.gender = request.form.get("gender","")
        s.notes = request.form.get("notes","")
        if not s.full_name or s.age < 6 or s.age > 12:
            flash("กรอกชื่อและอายุ 6-12 ปีให้ถูกต้อง", "danger")
            return redirect(url_for("student_edit", sid=sid))
        db.session.commit()
        flash("แก้ไขข้อมูลแล้ว", "success")
        return redirect(url_for("students"))
    return render_template("student_form.html", item=s)

@app.route("/students/<int:sid>/delete", methods=["POST"])
@login_required
def student_delete(sid):
    s = Student.query.get_or_404(sid)
    db.session.delete(s)
    db.session.commit()
    flash("ลบข้อมูลนักเรียนแล้ว", "info")
    return redirect(url_for("students"))

@app.route("/students/<int:sid>")
@login_required
def student_detail(sid):
    s = Student.query.get_or_404(sid)
    # for printable profile and latest logs
    logs = BehaviorLog.query.filter_by(student_id=sid).order_by(BehaviorLog.log_date.desc()).limit(30).all()
    acts = ActivityLog.query.filter_by(student_id=sid).order_by(ActivityLog.done_at.desc()).limit(30).all()
    # Recommend activities by age
    rec_acts = Activity.query.filter(Activity.age_min <= s.age, Activity.age_max >= s.age).all()
    return render_template("student_detail.html", s=s, logs=logs, acts=acts, rec_acts=rec_acts)

# Activities
@app.route("/activities")
@login_required
def activities():
    age = request.args.get("age","")
    query = Activity.query
    if age.isdigit():
        a = int(age)
        query = query.filter(Activity.age_min <= a, Activity.age_max >= a)
    rows = query.order_by(Activity.title.asc()).all()
    return render_template("activities.html", rows=rows, age=age)

@app.route("/activities/new", methods=["GET","POST"])
@login_required
def activity_new():
    if request.method == "POST":
        title = request.form.get("title","").strip()
        if not title:
            flash("กรอกชื่อกิจกรรม", "danger")
            return redirect(url_for("activity_new"))
        item = Activity(
            title=title,
            description=request.form.get("description",""),
            category=request.form.get("category",""),
            age_min=int(request.form.get("age_min","6") or 6),
            age_max=int(request.form.get("age_max","12") or 12),
            created_by=current_user.id
        )
        db.session.add(item)
        db.session.commit()
        flash("เพิ่มกิจกรรมแล้ว", "success")
        return redirect(url_for("activities"))
    return render_template("activity_form.html", item=None)

@app.route("/activities/<int:aid>/edit", methods=["GET","POST"])
@login_required
def activity_edit(aid):
    item = Activity.query.get_or_404(aid)
    if request.method == "POST":
        item.title = request.form.get("title","").strip()
        item.description = request.form.get("description","")
        item.category = request.form.get("category","")
        item.age_min = int(request.form.get("age_min","6") or 6)
        item.age_max = int(request.form.get("age_max","12") or 12)
        db.session.commit()
        flash("แก้กิจกรรมแล้ว", "success")
        return redirect(url_for("activities"))
    return render_template("activity_form.html", item=item)

@app.route("/activities/<int:aid>/delete", methods=["POST"])
@login_required
def activity_delete(aid):
    item = Activity.query.get_or_404(aid)
    db.session.delete(item)
    db.session.commit()
    flash("ลบกิจกรรมแล้ว", "info")
    return redirect(url_for("activities"))

# Logs
@app.route("/logs/behavior/new", methods=["POST"])
@login_required
def behavior_new():
    sid = int(request.form.get("student_id"))
    log = BehaviorLog(
        student_id=sid,
        log_date=datetime.strptime(request.form.get("log_date"), "%Y-%m-%d").date() if request.form.get("log_date") else date.today(),
        mood=int(request.form.get("mood","3") or 3),
        focus=int(request.form.get("focus","3") or 3),
        social=int(request.form.get("social","3") or 3),
        notes=request.form.get("notes","")
    )
    db.session.add(log)
    db.session.commit()
    flash("บันทึกพฤติกรรมแล้ว", "success")
    return redirect(url_for("student_detail", sid=sid))

@app.route("/logs/activity/new", methods=["POST"])
@login_required
def activitylog_new():
    sid = int(request.form.get("student_id"))
    aid = int(request.form.get("activity_id"))
    log = ActivityLog(
        student_id=sid,
        activity_id=aid,
        done_at=datetime.strptime(request.form.get("done_at"), "%Y-%m-%d").date() if request.form.get("done_at") else date.today(),
        remark=request.form.get("remark","")
    )
    db.session.add(log)
    db.session.commit()
    flash("บันทึกการทำกิจกรรมแล้ว", "success")
    return redirect(url_for("student_detail", sid=sid))

# Reports & chart data
@app.route("/reports")
@login_required
def reports():
    students = Student.query.order_by(Student.full_name.asc()).all()
    return render_template("reports.html", students=students)

def _aggregate_behavior(sid, period="daily"):
    q = BehaviorLog.query.filter_by(student_id=sid)
    buckets = defaultdict(lambda: {"mood":0,"focus":0,"social":0,"n":0})
    for row in q:
        if period == "daily":
            key = row.log_date.strftime("%Y-%m-%d")
        elif period == "monthly":
            key = row.log_date.strftime("%Y-%m")
        else:
            key = row.log_date.strftime("%Y")
        buckets[key]["mood"] += row.mood
        buckets[key]["focus"] += row.focus
        buckets[key]["social"] += row.social
        buckets[key]["n"] += 1
    labels = sorted(buckets.keys())
    mood = [round(buckets[k]["mood"]/buckets[k]["n"],2) for k in labels]
    focus = [round(buckets[k]["focus"]/buckets[k]["n"],2) for k in labels]
    social = [round(buckets[k]["social"]/buckets[k]["n"],2) for k in labels]
    return {"labels": labels, "mood": mood, "focus": focus, "social": social}

@app.route("/api/charts/behavior/<int:sid>")
@login_required
def api_behavior(sid):
    period = request.args.get("period","daily")
    data = _aggregate_behavior(sid, period=period)
    return jsonify(data)

# Printable
@app.route("/print/student/<int:sid>")
@login_required
def print_student(sid):
    s = Student.query.get_or_404(sid)
    logs = BehaviorLog.query.filter_by(student_id=sid).order_by(BehaviorLog.log_date.desc()).limit(30).all()
    acts = ActivityLog.query.filter_by(student_id=sid).order_by(ActivityLog.done_at.desc()).limit(30).all()
    return render_template("print_student.html", s=s, logs=logs, acts=acts)

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)
