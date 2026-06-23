import os
from flask import Flask, render_template, request, redirect, url_for, session
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', os.urandom(24))

def get_db():
    conn = sqlite3.connect('forum.db')
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/')
def home():
    db = get_db()
    
    categories = db.execute('SELECT * FROM categories').fetchall()
    
    recent_threads = db.execute('''
        SELECT t.id, t.title, t.created_at, u.username, c.name AS category_name
        FROM threads t
        JOIN users u ON t.user_id = u.id
        JOIN categories c ON t.category_id = c.id
        ORDER BY t.created_at DESC
        LIMIT 5
    ''').fetchall()
    
    return render_template('home.html', categories=categories, threads=recent_threads)

@app.route('/register', methods=('GET', 'POST'))
def register():
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password']
        
        if not username or not password:
            return "Username and password cannot be empty!"

        hashed_password = generate_password_hash(password)
        db = get_db()
        try:
            db.execute('INSERT INTO users (username, password) VALUES (?, ?)', (username, hashed_password))
            db.commit()
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            return "This username already exists!"
            
    return render_template('register.html')

@app.route('/login', methods=('GET', 'POST'))
def login():
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password']
        
        db = get_db()
        user = db.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
        
        if user and check_password_hash(user['password'], password):
            session['user_id'] = user['id']
            session['username'] = user['username']
            return redirect(url_for('home'))
            
        return "Wrong username or password!"
        
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))

@app.route('/category/<int:category_id>')
def category(category_id):
    db = get_db()
    
    category = db.execute('SELECT * FROM categories WHERE id = ?', (category_id,)).fetchone()
    
    if not category:
        return "Category not found!", 404
        
    threads = db.execute('''
        SELECT t.id, t.title, t.created_at, u.username
        FROM threads t
        JOIN users u ON t.user_id = u.id
        WHERE t.category_id = ?
        ORDER BY t.created_at DESC
    ''', (category_id,)).fetchall()
    
    return render_template('category.html', category=category, threads=threads)

@app.route('/category/<int:category_id>/new-thread', methods=('GET', 'POST'))
def new_thread(category_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    db = get_db()
    
    category = db.execute('SELECT * FROM categories WHERE id = ?', (category_id,)).fetchone()
    if not category:
        return "Category not found!", 404
        
    if request.method == 'POST':
        title = request.form['title'].strip()
        content = request.form['content'].strip()
        user_id = session['user_id'] 
        
        if not title or not content:
            return "Title and content cannot be empty!"
            
        db.execute('''
            INSERT INTO threads (title, content, category_id, user_id)
            VALUES (?, ?, ?, ?)
        ''', (title, content, category_id, user_id))
        db.commit()
        
        return redirect(url_for('category', category_id=category_id))
        
    return render_template('new_thread.html', category=category)

@app.route('/thread/<int:thread_id>', methods=('GET', 'POST'))
def thread_detail(thread_id):
    db = get_db()
    
    thread = db.execute('''
        SELECT t.*, u.username 
        FROM threads t
        JOIN users u ON t.user_id = u.id
        WHERE t.id = ?
    ''', (thread_id,)).fetchone()
    
    if not thread:
        return "Thread not found!", 404

    if request.method == 'POST':
        if 'user_id' not in session:
            return redirect(url_for('login'))
            
        content = request.form['content'].strip()
        user_id = session['user_id']
        
        if not content:
            return "Reply content cannot be empty!"
            
        db.execute('''
            INSERT INTO replies (content, thread_id, user_id)
            VALUES (?, ?, ?)
        ''', (content, thread_id, user_id))
        db.commit()
        
        return redirect(url_for('thread_detail', thread_id=thread_id))

    replies = db.execute('''
        SELECT r.*, u.username 
        FROM replies r
        JOIN users u ON r.user_id = u.id
        WHERE r.thread_id = ?
        ORDER BY r.created_at ASC
    ''', (thread_id,)).fetchall()
    
    return render_template('thread.html', thread=thread, replies=replies)

if __name__ == '__main__':
    app.run(debug=True)