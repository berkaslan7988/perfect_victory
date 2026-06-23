from flask import Flask, render_template, request, redirect, url_for
import sqlite3

app = Flask(__name__)

def get_db_connection():
    conn = sqlite3.connect('news.db')
    conn.row_factory = sqlite3.Row
    return conn

# Main News Feed
@app.route('/')
def home():
    conn = get_db_connection()
    articles = conn.execute('SELECT * FROM articles ORDER BY id DESC').fetchall()
    conn.close()
    return render_template('index.html', articles=articles)

# Editor's Dashboard (News Creation)
@app.route('/add-news', methods=('GET', 'POST'))
def add_news():
    if request.method == 'POST':
        title = request.form['title']
        category = request.form['category']
        content = request.form['content']

        conn = get_db_connection()
        # Using placeholders '?' to prevent SQL Injection
        conn.execute('INSERT INTO articles (title, category, content) VALUES (?, ?, ?)',
                     (title, category, content))
        conn.commit()
        conn.close()
        return redirect(url_for('home'))

    return render_template('add_news.html')

if __name__ == '__main__':
    app.run(debug=True)