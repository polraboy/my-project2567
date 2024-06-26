from flask import Flask, render_template, request, redirect, url_for, session
import mysql.connector
from contextlib import contextmanager
import base64


app = Flask(__name__)
app.secret_key = "your_secret_key"


@app.route("/home")
def index():
    return "Welcome to the Flask Google Form Integration App"


@contextmanager
def get_db_cursor():
    db = mysql.connector.connect(
        host="localhost", user="root", password="", database="project"
    )
    cursor = db.cursor()
    try:
        yield db, cursor
    finally:
        cursor.close()
        db.close()


@app.route("/")
def home():
    with get_db_cursor() as (db, cursor):
        query = "SELECT constants_headname, constants_detail, constants_image FROM constants"
        cursor.execute(query)
        constants = cursor.fetchall()
    
    constants = [(c[0], c[1], base64.b64encode(c[2]).decode('utf-8')) for c in constants]
    
    return render_template("home.html", constants=constants)

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        with get_db_cursor() as (db, cursor):
            query_teacher = "SELECT * FROM teacher WHERE teacher_username = %s AND teacher_password = %s"
            cursor.execute(query_teacher, (username, password))
            teacher = cursor.fetchone()

            if not teacher:
                query_admin = "SELECT * FROM admin WHERE admin_username = %s AND admin_password = %s"
                cursor.execute(query_admin, (username, password))
                admin = cursor.fetchone()

                if admin:
                    session["admin_id"] = admin[0]
                    session["admin_name"] = admin[1]
                    return redirect(url_for("admin_home"))
                else:
                    return "Login failed. Please check your username and password."

            session["teacher_id"] = teacher[0]
            session["teacher_name"] = teacher[1]
            return redirect(url_for("teacher_home"))

    return render_template("login.html")


@app.route("/dashboard")
def dashboard():
    if "admin_id" in session:
        return f"Hello, Admin {session['admin_name']}! This is your dashboard."
    elif "teacher_id" in session:
        return f"Hello, Teacher {session['teacher_name']}! This is your dashboard."
    else:
        return redirect(url_for("login"))


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/admin_home", methods=['GET', 'POST'])
def admin_home():
    if "admin_id" not in session:
        return redirect(url_for("login"))

    if request.method == 'POST':
        constant_headname = request.form['constant_headname']
        constant_detail = request.form['constant_detail']
        constant_image = request.files['constant_image']
        
        image_binary = constant_image.read()
        
        with get_db_cursor() as (db, cursor):
            query = "INSERT INTO constants (constants_headname, constants_detail, constants_image) VALUES (%s, %s, %s)"
            cursor.execute(query, (constant_headname, constant_detail, image_binary))
            db.commit()

    # ดึงข้อมูล constants
    with get_db_cursor() as (db, cursor):
        query = "SELECT constants_headname, constants_detail, constants_image FROM constants"
        cursor.execute(query)
        constants = cursor.fetchall()
        
    # แปลงรูปภาพเป็น base64
    constants = [(c[0], c[1], base64.b64encode(c[2]).decode('utf-8')) for c in constants]

    return render_template("admin_home.html", constants=constants)


@app.route("/approve_project", methods=["GET", "POST"])
def approve_project():
    if "admin_id" in session:
        if request.method == "POST":
            project_id = request.form.get("project_id")
            with get_db_cursor() as (db, cursor):
                query = "UPDATE project SET project_status = 2 WHERE project_id = %s"
                cursor.execute(query, (project_id,))
                db.commit()
            return redirect(url_for("approve_project"))

        projects = get_projects()
        return render_template(
            "approve_project.html", projects=projects, get_status=get_status
        )
    else:
        return redirect(url_for("login"))


@app.route("/teacher_home")
def teacher_home():
    if "teacher_id" not in session:
        return redirect(url_for("login"))

    with get_db_cursor() as (db, cursor):
        query = "SELECT constants_headname, constants_detail, constants_image FROM constants"
        cursor.execute(query)
        constants = cursor.fetchall()
    
    constants = [(c[0], c[1], base64.b64encode(c[2]).decode('utf-8')) for c in constants]
    
    return render_template("teacher_home.html", constants=constants)

def get_projects():
    with get_db_cursor() as (db, cursor):
        query = "SELECT project_id, project_name, project_status, project_statusStart FROM project"
        cursor.execute(query)
        projects = cursor.fetchall()
    return projects


def get_status(status_code):
    if status_code == 0:
        return "ยังไม่ยื่นอนุมัติ"
    elif status_code == 1:
        return "รออนุมัติ"
    elif status_code == 2:
        return "อนุมัติแล้ว"
    else:
        return "ไม่มีข้อมูล"


@app.route("/add_project", methods=["GET", "POST"])
def add_project():
    if request.method == "POST":
        project_budgettype = request.form["project_budgettype"]
        project_year = request.form["project_year"]
        project_name = request.form["project_name"]
        project_style = request.form["project_style"]
        project_address = request.form["project_address"]
        project_dotime = request.form["project_dotime"]
        project_endtime = request.form["project_endtime"]
        project_target = request.form["project_target"]
        project_budget = request.form["project_budget"]
        project_status = 0
        teacher_id = request.form["teacher_id"]

        with get_db_cursor() as (db, cursor):
            query = """INSERT INTO project (project_budgettype, project_year, project_name, project_style, 
                       project_address, project_dotime, project_endtime, project_target, project_budget, 
                       project_status, teacher_id) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"""
            cursor.execute(
                query,
                (
                    project_budgettype,
                    project_year,
                    project_name,
                    project_style,
                    project_address,
                    project_dotime,
                    project_endtime,
                    project_target,
                    project_budget,
                    project_status,
                    teacher_id,
                ),
            )
            db.commit()

            # Get the last inserted project ID
            project_id = cursor.lastrowid

    teachers = get_teachers()
    return render_template("add_project.html", teachers=teachers)


def get_teachers(teacher_id=None):
    with get_db_cursor() as (db, cursor):
        if teacher_id:
            query = """SELECT teacher_id, teacher_name, teacher_username, teacher_password, teacher_phone, 
                       teacher_email, branch_name FROM teacher JOIN branch ON teacher.branch_id = branch.branch_id 
                       WHERE teacher_id = %s"""
            cursor.execute(query, (teacher_id,))
        else:
            query = """SELECT teacher_id, teacher_name, teacher_username, teacher_password, teacher_phone, 
                       teacher_email, branch_name FROM teacher JOIN branch ON teacher.branch_id = branch.branch_id"""
            cursor.execute(query)
        teachers = cursor.fetchall()
    return teachers


@app.route("/edit_basic_info", methods=["GET", "POST"])
def edit_basic_info():
    if request.method == "POST":
        branch_id = request.form["branch_id"]
        teacher_name = request.form["teacher_name"]
        teacher_username = request.form["teacher_username"]
        teacher_password = request.form["teacher_password"]
        teacher_phone = request.form["teacher_phone"]
        teacher_email = request.form["teacher_email"]

        if "admin_id" in session:
            return redirect(url_for("admin_home"))

    if "admin_id" in session:
        branches = get_branches_from_database()
        teachers = get_teachers()
        return render_template(
            "edit_basic_info.html", teachers=teachers, branches=branches
        )
    else:
        return redirect(url_for("login"))


def get_teacher_by_id(teacher_id):
    with get_db_cursor() as (db, cursor):
        query = """SELECT t.teacher_id, t.teacher_name, t.teacher_username, t.teacher_password, 
                          t.teacher_phone, t.teacher_email, b.branch_name 
                   FROM teacher t 
                   JOIN branch b ON t.branch_id = b.branch_id 
                   WHERE t.teacher_id = %s"""
        cursor.execute(query, (teacher_id,))
        teacher = cursor.fetchone()
    return teacher


def update_teacher(
    teacher_id,
    branch_id,
    teacher_name,
    teacher_username,
    teacher_password,
    teacher_phone,
    teacher_email,
):
    with get_db_cursor() as (db, cursor):
        query = """UPDATE teacher SET branch_id = %s, teacher_name = %s, teacher_username = %s, 
                   teacher_password = %s, teacher_phone = %s, teacher_email = %s WHERE teacher_id = %s"""
        cursor.execute(
            query,
            (
                branch_id,
                teacher_name,
                teacher_username,
                teacher_password,
                teacher_phone,
                teacher_email,
                teacher_id,
            ),
        )
        db.commit()


@app.route("/edit_teacher/<int:teacher_id>", methods=["GET", "POST"])
def edit_teacher(teacher_id):
    if request.method == "GET":
        teacher = get_teacher_by_id(teacher_id)
        if teacher:
            return render_template("edit_teacher.html", teacher=teacher)
        else:
            return "Teacher not found"
    elif request.method == "POST":
        teacher_name = request.form["teacher_name"]
        teacher_username = request.form["teacher_username"]
        teacher_password = request.form["teacher_password"]
        teacher_phone = request.form["teacher_phone"]
        teacher_email = request.form["teacher_email"]

        update_teacher(
            teacher_id,
            teacher_name,
            teacher_username,
            teacher_password,
            teacher_phone,
            teacher_email,
        )

        return redirect(url_for("teacher_home"))


def get_branches_from_database():
    branches = []
    with get_db_cursor() as (db, cursor):
        query = "SELECT branch_id, branch_name FROM branch"
        cursor.execute(query)
        branches = cursor.fetchall()
    return branches


@app.route("/add_teacher", methods=["GET", "POST"])
def add_teacher():
    if request.method == "GET":
        branches = get_branches_from_database()
        return render_template("add_teacher.html", branches=branches)
    elif request.method == "POST":
        teacher_name = request.form["teacher_name"]
        teacher_username = request.form["teacher_username"]
        teacher_password = request.form["teacher_password"]
        teacher_phone = request.form["teacher_phone"]
        teacher_email = request.form["teacher_email"]
        branch_id = request.form["branch_id"]

        with get_db_cursor() as (db, cursor):
            query = """INSERT INTO teacher (teacher_name, teacher_username, teacher_password, 
                                            teacher_phone, teacher_email, branch_id) VALUES (%s, %s, %s, %s, %s, %s)"""
            cursor.execute(
                query,
                (
                    teacher_name,
                    teacher_username,
                    teacher_password,
                    teacher_phone,
                    teacher_email,
                    branch_id,
                ),
            )
            db.commit()

        return redirect(url_for("edit_basic_info"))


@app.route("/add_branch", methods=["GET", "POST"])
def add_branch():
    if request.method == "POST":
        branch_name = request.form["branch_name"]

        with get_db_cursor() as (db, cursor):
            query = "INSERT INTO branch (branch_name) VALUES (%s)"
            cursor.execute(query, (branch_name,))
            db.commit()

        return redirect(url_for("edit_basic_info"))

    return render_template("add_branch.html")


@app.route("/teacher_projects")
def teacher_projects():
    if "teacher_id" not in session:
        return redirect(url_for("login"))

    teacher_id = session["teacher_id"]

    with get_db_cursor() as (db, cursor):
        query = "SELECT project_id, project_name, project_status, project_statusStart FROM project WHERE teacher_id = %s"
        cursor.execute(query, (teacher_id,))
        projects = cursor.fetchall()

    return render_template("teacher_projects.html", projects=projects)


@app.route("/request_approval", methods=["POST"])
def request_approval():
    project_id = request.form.get("project_id")
    with get_db_cursor() as (db, cursor):
        query = "UPDATE project SET project_status = 1 WHERE project_id = %s"
        cursor.execute(query, (project_id,))
        db.commit()
    return redirect(url_for("teacher_projects"))


@app.route("/project/<int:project_id>")
def project_detail(project_id):
    if "teacher_id" not in session:
        return redirect(url_for("login"))

    with get_db_cursor() as (db, cursor):
        query = """SELECT project.project_name, project.project_year, project.project_style, 
                          project.project_address, DATE(project.project_dotime), DATE(project.project_endtime), 
                          project.project_target, teacher.teacher_name, project.project_statusStart
                   FROM project
                   JOIN teacher ON project.teacher_id = teacher.teacher_id
                   WHERE project.project_id = %s"""
        cursor.execute(query, (project_id,))
        project = cursor.fetchone()

    return render_template(
        "project_detail.html", project=project, project_id=project_id
    )


@app.route("/update_project_statusStart", methods=["POST"])
def update_project_statusStart():
    if "teacher_id" not in session:
        return redirect(url_for("login"))

    project_id = request.form.get("project_id")
    project_status = request.form.get("projectStatus")

    with get_db_cursor() as (db, cursor):
        query = "UPDATE project SET project_statusStart = %s WHERE project_id = %s"
        cursor.execute(query, (project_status, project_id))
        db.commit()

    return redirect(url_for("project_detail", project_id=project_id))


# ตรวจสอบข้อมูลใหม่ทุกๆ 5 นาที
if __name__ == "__main__":
    app.run(debug=True, port=5000)
    