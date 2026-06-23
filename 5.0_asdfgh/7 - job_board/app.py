import os
from flask import Flask, render_template, request, redirect, url_for, session
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import sqlite3

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', os.urandom(24))

UPLOAD_FOLDER = 'static/uploads/cvs'
ALLOWED_EXTENSIONS = {'pdf', 'doc', 'docx'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def get_db():
    conn = sqlite3.connect('jobs.db')
    conn.row_factory = sqlite3.Row
    return conn

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/')
def home():
    db = get_db()
    jobs = db.execute('SELECT * FROM jobs').fetchall()
    return render_template('home.html', jobs=jobs)

@app.route('/register', methods=('GET', 'POST'))
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = generate_password_hash(request.form['password'])
        role = request.form['role'] 
        cv_filename = None

        if role == 'seeker' and 'cv' in request.files:
            file = request.files['cv']
            if file and file.filename != '' and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                unique_filename = f"{username}_{filename}"
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], unique_filename))
                cv_filename = unique_filename

        db = get_db()
        try:
            db.execute('INSERT INTO users (username, password, role, cv_filename) VALUES (?, ?, ?, ?)',
                       (username, password, role, cv_filename))
            db.commit()
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            return "This username is already taken!"
            
    return render_template('register.html')

@app.route('/login', methods=('GET', 'POST'))
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        db = get_db()
        user = db.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
        
        if user and check_password_hash(user['password'], password):
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['role'] = user['role']
            return redirect(url_for('home'))
        return "Wrong username or password!"
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))

@app.route('/apply/<int:job_id>')
def apply(job_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    if session.get('role') != 'seeker':
        return "Only job seekers can apply to jobs!"

    db = get_db()
    seeker_id = session['user_id']

    existing_app = db.execute('SELECT * FROM applications WHERE job_id = ? AND seeker_id = ?', 
                              (job_id, seeker_id)).fetchone()
    
    if existing_app:
        return "You have already applied to this job!"

    db.execute('INSERT INTO applications (job_id, seeker_id) VALUES (?, ?)', (job_id, seeker_id))
    db.commit()
    
    return "Application successful! Your CV has been sent to the employer."

@app.route('/post-job', methods=('GET', 'POST'))
def post_job():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    if session.get('role') != 'employer':
        return "Access Denied: Only employers can post jobs!"

    if request.method == 'POST':
        title = request.form['title']
        company = request.form['company']
        location = request.form['location']
        description = request.form['description']
        employer_id = session['user_id'] 

        db = get_db()
        db.execute(
            'INSERT INTO jobs (title, company, location, description, employer_id) VALUES (?, ?, ?, ?, ?)',
            (title, company, location, description, employer_id)
        )
        db.commit()
        
        return redirect(url_for('home'))

    return render_template('post_job.html')

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    if session.get('role') != 'employer':
        return "Access Denied: Only employers can view the dashboard!"
    
    db = get_db()
    employer_id = session['user_id']
    

    applications = db.execute('''
        SELECT apps.id, jobs.title AS job_title, users.username AS seeker_name, users.cv_filename
        FROM applications apps
        JOIN jobs ON apps.job_id = jobs.id
        JOIN users ON apps.seeker_id = users.id
        WHERE jobs.employer_id = ?
    ''', (employer_id,)).fetchall()
    
    return render_template('dashboard.html', applications=applications)


if __name__ == '__main__':
    app.run(debug=True)