from flask import Flask, render_template, redirect, url_for, request, flash, session, send_from_directory
from models import db, User, Submission
from flask_bcrypt import Bcrypt
from werkzeug.utils import secure_filename
import os, uuid

app = Flask(__name__)

app.config['SECRET_KEY'] = 'secretkey123'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///project_db.sqlite'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

UPLOAD_FOLDER = 'uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

ALLOWED_EXTENSIONS = {'pdf', 'doc', 'docx', 'zip', 'rar'}

db.init_app(app)
bcrypt = Bcrypt(app)


# ─── Helper ────────────────────────────────────────────────────────────────

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


# ─── Home ──────────────────────────────────────────────────────────────────

@app.route('/')
def home():
    return render_template('index.html')


# ─── Register ──────────────────────────────────────────────────────────────

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username   = request.form.get('name')
        email      = request.form.get('email')
        password   = request.form.get('password')
        role       = request.form.get('role', 'student')
        course     = request.form.get('course')
        year       = request.form.get('year')
        department = request.form.get('department')

        if not username or not email or not password:
            flash('All fields are required.', 'danger')
            return redirect(url_for('register'))

        if User.query.filter_by(email=email).first():
            flash('Email already registered. Please log in.', 'danger')
            return redirect(url_for('register'))

        hashed_pw = bcrypt.generate_password_hash(password).decode('utf-8')

        new_user = User(
            username   = username,
            email      = email,
            password   = hashed_pw,
            role       = role,
            course     = course if role == 'student' else None,
            year       = int(year) if (role == 'student' and year) else None,
            department = department if role == 'faculty' else None
        )

        db.session.add(new_user)
        db.session.commit()

        flash('Account created! Please log in.', 'success')
        return redirect(url_for('login'))

    return render_template('register.html')


# ─── Login ─────────────────────────────────────────────────────────────────

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email    = request.form.get('email')
        password = request.form.get('password')

        user = User.query.filter_by(email=email).first()

        if user and bcrypt.check_password_hash(user.password, password):
            session['user_id']  = user.id
            session['username'] = user.username
            session['role']     = user.role

            if user.role == 'admin':
                return redirect(url_for('admin_dashboard'))
            elif user.role == 'faculty':
                return redirect(url_for('faculty_dashboard'))
            else:
                return redirect(url_for('student_dashboard'))
        else:
            flash('Invalid email or password.', 'danger')

    return render_template('login.html')


# ─── Logout ────────────────────────────────────────────────────────────────

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))


# ─── Student Dashboard ─────────────────────────────────────────────────────

@app.route('/student_dashboard')
def student_dashboard():
    if session.get('role') != 'student':
        return redirect(url_for('login'))

    # ✅ FIXED: Safe faculty list with fallback name
    faculty_list = [
        {
            'faculty_id': f.id,
            'name': f.username if f.username else f.email,
            'department': f.department if f.department else 'N/A'
        }
        for f in User.query.filter_by(role='faculty').all()
    ]

    # Fetch student submissions
    raw = Submission.query.filter_by(user_id=session['user_id'])\
                          .order_by(Submission.submitted_at.desc()).all()

    projects = [
        {
            'submission_id': s.id,
            'title': s.title,
            'description': s.description,
            'submission_date': s.submitted_at.strftime('%d %b %Y, %I:%M %p'),
            'grade': s.grade,
            'comments': s.comments,
            'faculty': s.faculty.username if s.faculty and s.faculty.username else 'Not assigned'
        }
        for s in raw
    ]

    return render_template(
        'student_dashboard.html',
        faculty_list=faculty_list,
        projects=projects,
        deadline=None
    )


# ─── Faculty Dashboard ─────────────────────────────────────────────────────

@app.route('/faculty_dashboard')
def faculty_dashboard():
    if session.get('role') != 'faculty':
        return redirect(url_for('login'))

    submissions = Submission.query.filter_by(faculty_id=session['user_id'])\
                                  .order_by(Submission.submitted_at.desc()).all()

    return render_template('faculty_dashboard.html', submissions=submissions)


# ─── Admin Dashboard ───────────────────────────────────────────────────────

@app.route('/admin_dashboard')
def admin_dashboard():
    if session.get('role') != 'admin':
        return redirect(url_for('login'))

    users = User.query.all()
    submissions = Submission.query.all()

    return render_template('admin_dashboard.html', users=users, submissions=submissions)


# ─── Upload Project ────────────────────────────────────────────────────────

@app.route('/upload', methods=['POST'])
def upload():
    if session.get('role') != 'student':
        return redirect(url_for('login'))

    title       = request.form.get('title')
    description = request.form.get('description')
    faculty_id  = request.form.get('faculty_id')
    file        = request.files.get('file')

    # ─── VALIDATIONS ─────────────────────

    if not title:
        flash('Please provide a project title.', 'danger')
        return redirect(url_for('student_dashboard'))

    if not faculty_id:
        flash('Please select a faculty.', 'danger')
        return redirect(url_for('student_dashboard'))

    if not file or file.filename == '':
        flash('Please select a file.', 'danger')
        return redirect(url_for('student_dashboard'))

    if not allowed_file(file.filename):
        flash('Invalid file type.', 'danger')
        return redirect(url_for('student_dashboard'))

    # ─── DUPLICATE CHECK (🔥 FIXED POSITION) ─────────────────────

    existing_project = Submission.query.filter(
        db.func.lower(Submission.title) == title.lower()
    ).first()

    if existing_project:
        flash('This project topic is already taken. Please choose a different topic.', 'danger')
        return redirect(url_for('student_dashboard'))

    # ─── SAVE FILE ─────────────────────

    original_filename = secure_filename(file.filename)
    unique_filename   = f"{uuid.uuid4().hex}_{original_filename}"

    file.save(os.path.join(app.config['UPLOAD_FOLDER'], unique_filename))

    # ─── SAVE TO DATABASE ─────────────────────

    submission = Submission(
        title=title,
        description=description,
        filename=unique_filename,
        original_filename=original_filename,
        user_id=session['user_id'],
        faculty_id=int(faculty_id)
    )

    db.session.add(submission)
    db.session.commit()

    flash('Project submitted successfully!', 'success')
    return redirect(url_for('student_dashboard'))

# ─── Download File ──────────────────────────────────────────

@app.route('/download/<int:submission_id>')
def download_file(submission_id):
    if not session.get('user_id'):
        return redirect(url_for('login'))

    submission = Submission.query.get_or_404(submission_id)

    # 🔐 Security: student can only download their own file
    if session.get('role') == 'student' and submission.user_id != session['user_id']:
        flash('Access denied.', 'danger')
        return redirect(url_for('student_dashboard'))

    return send_from_directory(
        app.config['UPLOAD_FOLDER'],
        submission.filename,
        as_attachment=True,
        download_name=submission.original_filename
    )

# ─── Grade Submission ─────────────────────────────────────────────

@app.route('/grade', methods=['POST'])
def grade():
    if session.get('role') != 'faculty':
        return redirect(url_for('login'))

    submission_id = request.form.get('submission_id')
    grade_value   = request.form.get('grade')
    comments      = request.form.get('comments')

    submission = Submission.query.get(submission_id)

    if not submission:
        flash('Submission not found.', 'danger')
        return redirect(url_for('faculty_dashboard'))

    # Update submission
    submission.grade = grade_value
    submission.comments = comments

    db.session.commit()

    flash('Evaluation submitted successfully!', 'success')
    return redirect(url_for('faculty_dashboard'))

# ─── Run ───────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    if not os.path.exists(UPLOAD_FOLDER):
        os.makedirs(UPLOAD_FOLDER)

    with app.app_context():
        db.create_all()

    app.run(debug=True)