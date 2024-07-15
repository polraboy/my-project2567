from flask import ( Flask, render_template,request, redirect, url_for,session,flash,send_from_directory,send_file)
import mysql.connector, base64, os
from contextlib import contextmanager
from fpdf import FPDF
from io import BytesIO
from functools import wraps

from PIL import Image
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = "your_secret_key"

class ThaiPDF(FPDF):
    def __init__(self):
        super().__init__()
        self.add_thai_font()

    def add_thai_font(self):
        font_path = os.path.join(os.path.dirname(__file__), 'THSarabunNew.ttf')
        if os.path.exists(font_path):
            self.add_font("THSarabunNew", "", font_path, uni=True)
        else:
            raise FileNotFoundError(f"ไม่พบไฟล์ฟอนต์ที่ {font_path}")

    def header(self):
        self.set_font('THSarabunNew', '', 16)
        self.cell(0, 10, 'รายละเอียดโครงการ', 0, 1, 'C')
        
@app.route("/home")
def index():
    return "Welcome to the Flask Google Form Integration App"

def login_required(user_type):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if "user_type" not in session or session["user_type"] != user_type:
                flash("คุณไม่มีสิทธิ์เข้าถึงหน้านี้", "error")
                return redirect(url_for("login"))
            return f(*args, **kwargs)
        return decorated_function
    return decorator

@contextmanager
def get_db_cursor():
    db = mysql.connector.connect(
        host="localhost",
        user="root",
        password="",
        database="project",
        connection_timeout=60,  # เพิ่มเวลา timeout
    )
    try:
        cursor = db.cursor(buffered=True)  # ใช้ buffered cursor
        yield db, cursor
    finally:
        cursor.close()
        db.close()

def get_db_connection():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="",
        database="project"
         )

@app.route("/")
def home():
    with get_db_cursor() as (db, cursor):
        query = "SELECT constants_headname, constants_detail, constants_image FROM constants"
        cursor.execute(query)
        constants = cursor.fetchall()

    constants = [
        (c[0], c[1], base64.b64encode(c[2]).decode("utf-8")) for c in constants
    ]

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

            if teacher:
                session.clear()  # Clear any existing session data
                session["teacher_id"] = teacher[0]
                session["teacher_name"] = teacher[1]
                session["user_type"] = "teacher"
                return redirect(url_for("teacher_home"))
            else:
                query_admin = "SELECT * FROM admin WHERE admin_username = %s AND admin_password = %s"
                cursor.execute(query_admin, (username, password))
                admin = cursor.fetchone()

                if admin:
                    session.clear()  # Clear any existing session data
                    session["admin_id"] = admin[0]
                    session["admin_name"] = admin[1]
                    session["user_type"] = "admin"
                    return redirect(url_for("admin_home"))
                else:
                    flash("Login failed. Please check your username and password.", "error")

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


@app.route("/admin_home")
@login_required("admin")
def admin_home():
    if "user_type" not in session or session["user_type"] != "admin":
        return redirect(url_for("login"))
    if request.method == "POST":
        if "constant_headname" in request.form:
            constant_headname = request.form["constant_headname"]
            constant_detail = request.form["constant_detail"]
            constant_image = request.files["constant_image"]

            # ปรับขนาดรูปภาพและแปลงเป็น RGB
            img = Image.open(constant_image)
            img = img.convert("RGB")  # แปลง RGBA เป็น RGB
            img.thumbnail((800, 600))  # ปรับขนาดให้พอดีกับ 800x600 โดยรักษาสัดส่วน

            # แปลงรูปภาพเป็น binary
            img_io = BytesIO()
            img.save(img_io, "JPEG", quality=85)
            image_binary = img_io.getvalue()

            # บันทึกลงฐานข้อมูล
            try:
                with get_db_cursor() as (db, cursor):
                    query = "INSERT INTO constants (constants_headname, constants_detail, constants_image) VALUES (%s, %s, %s)"
                    cursor.execute(
                        query, (constant_headname, constant_detail, image_binary)
                    )
                    db.commit()

                flash("Constant added successfully!", "success")
            except mysql.connector.Error as err:
                flash(f"Error: {err}", "danger")

            return redirect(url_for("admin_home"))

        elif "delete_constant_headname" in request.form:
            constant_headname = request.form["delete_constant_headname"]
            try:
                with get_db_cursor() as (db, cursor):
                    query = "DELETE FROM constants WHERE constants_headname = %s"
                    cursor.execute(query, (constant_headname,))
                    db.commit()

                flash("Constant deleted successfully!", "success")
            except mysql.connector.Error as err:
                flash(f"Error: {err}", "danger")

            return redirect(url_for("admin_home"))

    # ดึงข้อมูล constants
    try:
        with get_db_cursor() as (db, cursor):
            query = "SELECT constants_headname, constants_detail, constants_image FROM constants"
            cursor.execute(query)
            constants = cursor.fetchall()

        # แปลงรูปภาพเป็น base64
        constants = [
            (c[0], c[1], base64.b64encode(c[2]).decode("utf-8")) for c in constants
        ]
    except mysql.connector.Error as err:
        flash(f"Error: {err}", "danger")
        constants = []

    return render_template("admin_home.html", constants=constants)


@app.route("/approve_project", methods=["GET", "POST"])
@login_required("admin")
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
@login_required("teacher")
def teacher_home():
    if "user_type" not in session or session["user_type"] != "teacher":
        return redirect(url_for("login"))

    with get_db_cursor() as (db, cursor):
        query = "SELECT constants_headname, constants_detail, constants_image FROM constants"
        cursor.execute(query)
        constants = cursor.fetchall()

    constants = [
        (c[0], c[1], base64.b64encode(c[2]).decode("utf-8")) for c in constants
    ]

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


@app.route('/project/<int:project_id>/join', methods=['GET', 'POST'])
def join_project(project_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    cursor.execute("SELECT project_name, project_target FROM project WHERE project_id = %s", (project_id,))
    project = cursor.fetchone()
    
    if not project:
        flash('โครงการไม่พบ', 'error')
        return redirect(url_for('active_projects'))
    
    cursor.execute("SELECT COUNT(*) as current_count FROM `join` WHERE project_id = %s", (project_id,))
    result = cursor.fetchone()
    current_count = result['current_count']
    
    if current_count >= project['project_target']:
        flash('ขออภัย โครงการนี้มีผู้เข้าร่วมเต็มแล้ว', 'error')
        return redirect(url_for('project_detail', project_id=project_id))
    
    if request.method == 'POST':
        join_name = request.form['join_name']
        join_telephone = request.form['join_telephone']
        join_email = request.form['join_email']
        
        try:
            cursor.execute("""
                INSERT INTO `join` (join_name, join_telephone, join_email, project_id, join_status)
                VALUES (%s, %s, %s, %s, 0)
            """, (join_name, join_telephone, join_email, project_id))
            conn.commit()
            flash('คุณได้ลงทะเบียนเข้าร่วมโครงการเรียบร้อยแล้ว โปรดรอการอนุมัติ', 'success')
        except mysql.connector.Error as err:
            flash(f'เกิดข้อผิดพลาดในการลงทะเบียน: {err}', 'error')
        
        return redirect(url_for('project_detail', project_id=project_id))
    
    cursor.close()
    conn.close()
    return render_template('join_project.html', project=project, project_id=project_id, current_count=current_count)

@app.route("/project/<int:project_id>/participants")
def project_participants(project_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute(
        """
        SELECT join_id, join_name, join_email, join_telephone, join_status
        FROM `join`
        WHERE project_id = %s
        ORDER BY join_id
    """,
        (project_id,)
    )
    participants = cursor.fetchall()

    cursor.close()
    conn.close()

    is_logged_in = 'teacher_id' in session

    return render_template(
        "project_participants.html", 
        project_id=project_id, 
        participants=participants,
        is_logged_in=is_logged_in
    )

@app.route("/add_project", methods=["GET", "POST"])
@login_required("teacher")
def add_project():
    if "teacher_id" not in session:
        return redirect(url_for("login"))

    teacher_id = session["teacher_id"]

    # ดึงข้อมูลอาจารย์และสาขา
    with get_db_cursor() as (db, cursor):
        query = """SELECT teacher.teacher_name, branch.branch_name 
                   FROM teacher 
                   JOIN branch ON teacher.branch_id = branch.branch_id 
                   WHERE teacher.teacher_id = %s"""
        cursor.execute(query, (teacher_id,))
        teacher_info = cursor.fetchone()

    if request.method == "POST":
        project_budgettype = request.form["project_budgettype"]
        project_year = request.form["project_year"]
        project_name = request.form["project_name"]
        project_style = request.form["project_style"]
        project_address = request.form["project_address"]
        project_dotime = request.form["project_dotime"]
        project_endtime = request.form["project_endtime"]
        project_target = request.form["project_target"]
        project_target = int(project_target) if project_target else 0
        project_budget = request.form["project_budget"]
        project_status = 0

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
            project_id = cursor.lastrowid

        # สร้าง PDF
        pdf = ThaiPDF()
        pdf.add_page()

        # เพิ่มฟอนต์ THSarabunNew
        font_path = os.path.join(os.path.dirname(__file__), 'THSarabunNew.ttf')
        if os.path.exists(font_path):
            pdf.add_font("THSarabunNew", "", font_path, uni=True)
            pdf.add_font("THSarabunNew", "B", font_path, uni=True)
        else:
            raise FileNotFoundError(f"ไม่พบไฟล์ฟอนต์ที่ {font_path}")

        pdf.set_font("THSarabunNew", size=14)

        # เพิ่มข้อมูลโครงการ
        pdf.cell(0, 10, f"โครงการ: {project_name}", 0, 1)
        pdf.cell(0, 10, f"ประเภทงบประมาณ: {project_budgettype}", 0, 1)
        pdf.cell(0, 10, f"ปีงบประมาณ: {project_year}", 0, 1)
        pdf.cell(0, 10, f"ลักษณะโครงการ: {project_style}", 0, 1)
        pdf.cell(0, 10, f"สถานที่ดำเนินการ: {project_address}", 0, 1)
        pdf.cell(0, 10, f"วันที่เริ่มโครงการ: {project_dotime}", 0, 1)
        pdf.cell(0, 10, f"วันที่สิ้นสุดโครงการ: {project_endtime}", 0, 1)
        pdf.cell(0, 10, f"กลุ่มเป้าหมาย: {project_target}", 0, 1)
        pdf.cell(0, 10, f"งบประมาณ: {project_budget}", 0, 1)

        pdf_output = BytesIO()
        pdf.output(pdf_output)
        pdf_output.seek(0)

        return send_file(
            pdf_output,
            as_attachment=True,
            download_name=f'project_{project_id}.pdf',
            mimetype='application/pdf'
        )
        
        

       
        

    return render_template("add_project.html", teacher_info=teacher_info)


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
@login_required("admin")
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
    teacher_name,
    teacher_username,
    teacher_password,
    teacher_phone,
    teacher_email,
):
    with get_db_cursor() as (db, cursor):
        query = """UPDATE teacher SET teacher_name = %s, teacher_username = %s, 
                   teacher_password = %s, teacher_phone = %s, teacher_email = %s WHERE teacher_id = %s"""
        cursor.execute(
            query,
            (
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
@login_required("admin")
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

        return redirect(url_for("edit_basic_info"))


def delete_teacher(teacher_id):
    with get_db_cursor() as (db, cursor):
        query = "DELETE FROM teacher WHERE teacher_id = %s"
        cursor.execute(query, (teacher_id,))
        db.commit()


@app.route("/delete_teacher/<int:teacher_id>", methods=["POST"])
def delete_teacher_route(teacher_id):
    delete_teacher(teacher_id)
    return redirect(url_for("teacher_home"))


def get_branches_from_database():
    branches = []
    with get_db_cursor() as (db, cursor):
        query = "SELECT branch_id, branch_name FROM branch"
        cursor.execute(query)
        branches = cursor.fetchall()
    return branches


@app.route("/add_teacher", methods=["GET", "POST"])
@login_required("admin")
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
@login_required("admin")
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
@login_required("teacher")
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
@login_required("teacher")
def request_approval():
    project_id = request.form.get("project_id")
    with get_db_cursor() as (db, cursor):
        query = "UPDATE project SET project_status = 1 WHERE project_id = %s"
        cursor.execute(query, (project_id,))
        db.commit()
    return redirect(url_for("teacher_projects"))


@app.route("/project/<int:project_id>")
@login_required("teacher")
def project_detail(project_id):
    with get_db_cursor() as (db, cursor):
        query = """SELECT project.project_id, project.project_name, project.project_year, project.project_style, 
                          project.project_address, DATE(project.project_dotime) as project_dotime, 
                          DATE(project.project_endtime) as project_endtime, 
                          project.project_target, teacher.teacher_name, project.project_statusStart
                   FROM project
                   JOIN teacher ON project.teacher_id = teacher.teacher_id
                   WHERE project.project_id = %s"""
        cursor.execute(query, (project_id,))
        project = cursor.fetchone()

        if not project:
            flash('โครงการไม่พบ', 'error')
            return redirect(url_for('active_projects'))

        cursor.execute("SELECT COUNT(*) as current_participants FROM `join` WHERE project_id = %s", (project_id,))
        result = cursor.fetchone()
        current_count = result[0] if result else 0

        project_dict = {
            'project_id': project[0],
            'project_name': project[1],
            'project_year': project[2],
            'project_style': project[3],
            'project_address': project[4],
            'project_dotime': project[5],
            'project_endtime': project[6],
            'project_target': int(project[7]) if project[7] is not None else 0,
            'teacher_name': project[8],
            'project_statusStart': project[9]
        }

    is_logged_in = 'teacher_id' in session
    return render_template(
        "project_detail.html", project=project_dict, current_count=current_count, is_logged_in=is_logged_in
    )

@app.route("/update_project_statusStart", methods=["POST"])
@login_required("admin")
def update_project_statusStart():
    if "teacher_id" not in session:
        return redirect(url_for("login"))

    project_id = request.form.get("project_id")
    project_status = request.form.get("projectStatus")

    if project_status is not None and project_status != '':
        try:
            project_status = int(project_status)
            with get_db_cursor() as (db, cursor):
                query = "UPDATE project SET project_statusStart = %s WHERE project_id = %s"
                cursor.execute(query, (project_status, project_id))
                db.commit()
            flash('อัพเดทสถานะโครงการเรียบร้อยแล้ว', 'success')
        except ValueError:
            flash('สถานะโครงการไม่ถูกต้อง', 'error')
    else:
        flash('กรุณาเลือกสถานะโครงการ', 'error')

    return redirect(url_for("project_detail", project_id=project_id))
@app.route("/active_projects")
@login_required("teacher")
def active_projects():
    with get_db_cursor() as (db, cursor):
        query = """
        SELECT project_id, project_name, project_dotime, project_endtime
        FROM project
        WHERE project_statusStart = 1
        ORDER BY project_dotime DESC
        """
        cursor.execute(query)
        active_projects = cursor.fetchall()

    return render_template("active_projects.html", projects=active_projects)
@app.route('/update_join_status/<int:join_id>', methods=['POST'])
@login_required("teacher")
def update_join_status(join_id):
    if 'teacher_id' not in session:
        flash('คุณไม่มีสิทธิ์ในการดำเนินการนี้', 'error')
        return redirect(url_for('home'))

    new_status = request.form.get('join_status')
    
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("UPDATE `join` SET join_status = %s WHERE join_id = %s", (new_status, join_id))
        conn.commit()
        flash('อัพเดทสถานะการเข้าร่วมเรียบร้อยแล้ว', 'success')
    except mysql.connector.Error as err:
        flash(f'เกิดข้อผิดพลาดในการอัพเดทสถานะ: {err}', 'error')
    
    cursor.close()
    conn.close()

    return redirect(request.referrer)

@app.route('/project/<int:project_id>/approve_participants')
@login_required("teacher")
def approve_participants(project_id):
    if 'teacher_id' not in session:
        flash('คุณไม่มีสิทธิ์ในการดำเนินการนี้', 'error')
        return redirect(url_for('home'))

    with get_db_cursor() as (db, cursor):
        cursor.execute("SELECT teacher_id FROM project WHERE project_id = %s", (project_id,))
        project = cursor.fetchone()
        if not project or project[0] != session['teacher_id']:
            flash('คุณไม่มีสิทธิ์อนุมัติผู้เข้าร่วมโครงการนี้', 'error')
            return redirect(url_for('project_detail', project_id=project_id))

        cursor.execute("""
            SELECT join_id, join_name, join_email, join_telephone, join_status
            FROM `join`
            WHERE project_id = %s
        """, (project_id,))
        participants = cursor.fetchall()

        # แปลง tuple เป็น dictionary
        participants = [
            {
                'join_id': p[0],
                'join_name': p[1],
                'join_email': p[2],
                'join_telephone': p[3],
                'join_status': p[4]
            } for p in participants
        ]

    return render_template('approve_participants.html', project_id=project_id, participants=participants)
# ตรวจสอบข้อมูลใหม่ทุกๆ 5 นาที
if __name__ == "__main__":
    app.run(debug=True, port=5000)
