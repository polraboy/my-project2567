from flask import Flask, render_template, request, redirect, url_for, session
import mysql.connector
from contextlib import contextmanager

app = Flask(__name__)
app.secret_key = "your_secret_key"

# ฟังก์ชันสำหรับการเชื่อมต่อฐานข้อมูลและ cursor
@contextmanager
def get_db_cursor():
    db = mysql.connector.connect(
        host="localhost",
        user="root",
        password="",
        database="project"
    )
    cursor = db.cursor()
    yield db, cursor
    db.close()

# ตัวอย่างสำหรับ Flask app
@app.route("/")
def home():
    return render_template("home.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        # ใช้ context manager สำหรับ cursor
        with get_db_cursor() as (db, cursor):
            # ตรวจสอบข้อมูลล็อกอินในตาราง teacher
            query_teacher = "SELECT * FROM teacher WHERE teacher_username = %s AND teacher_password = %s"
            cursor.execute(query_teacher, (username, password))
            teacher = cursor.fetchone()

            # ถ้าไม่พบใน teacher, ตรวจสอบในตาราง admin
            if not teacher:
                query_admin = "SELECT * FROM admin WHERE admin_username = %s AND admin_password = %s"
                cursor.execute(query_admin, (username, password))
                admin = cursor.fetchone()

                if admin:
                    # ถ้าล็อกอินสำเร็จในตาราง admin, เก็บข้อมูลล็อกอินใน session
                    session["admin_id"] = admin[0]
                    session["admin_name"] = admin[1]
                    return redirect(url_for('admin_home'))  # Redirect ไปยังหน้า admin_home
                else:
                    return "Login failed. Please check your username and password."

            # ถ้าล็อกอินสำเร็จในตาราง teacher, เก็บข้อมูลล็อกอินใน session
            session["teacher_id"] = teacher[0]
            session["teacher_name"] = teacher[1]
            return redirect(url_for('teacher_home'))  # Redirect ไปยังหน้า teacher_home

    return render_template("login.html")

@app.route("/dashboard")
def dashboard():
    # เช็คว่ามี session ของ admin_id หรือ teacher_id หรือไม่
    if "admin_id" in session:
        return f"Hello, Admin {session['admin_name']}! This is your dashboard."
    elif "teacher_id" in session:
        return f"Hello, Teacher {session['teacher_name']}! This is your dashboard."
    else:
        return redirect(url_for("login"))

@app.route("/logout")
def logout():
    # ลบ session ทั้งหมด
    session.clear()
    return redirect(url_for("login"))

@app.route("/admin_home")
def admin_home():
    # ตรวจสอบว่ามี session ของ admin_id หรือไม่
    if "admin_id" in session:
        return render_template("admin_home.html")
    else:
        return redirect(url_for("login"))  # ถ้าไม่มี session ให้เด้งไปหน้า login

@app.route("/teacher_home")
def teacher_home():
    # ตรวจสอบว่ามี session ของ teacher_id หรือไม่
    if "teacher_id" in session:
        return render_template("teacher_home.html")
    else:
        return redirect(url_for("login"))  # ถ้าไม่มี session ให้เด้งไปหน้า login

if __name__ == "__main__":
    app.run(debug=True)
