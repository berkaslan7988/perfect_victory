import sqlite3
from werkzeug.security import generate_password_hash

def init_database():
    conn = sqlite3.connect('jobs.db')
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL,
            cv_filename TEXT 
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            company TEXT NOT NULL,
            location TEXT NOT NULL,
            description TEXT NOT NULL,
            employer_id INTEGER,
            FOREIGN KEY (employer_id) REFERENCES users (id)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS applications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id INTEGER,
            seeker_id INTEGER,
            FOREIGN KEY (job_id) REFERENCES jobs (id),
            FOREIGN KEY (seeker_id) REFERENCES users (id)
        )
    ''')

    
    hashed_pw = generate_password_hash('123456')
    
    users_data = [
        ('tech_corp', hashed_pw, 'employer', None),
        ('startup_inc', hashed_pw, 'employer', None),
        ('johndoe', hashed_pw, 'seeker', 'john_cv_sample.pdf'),
        ('janedoe', hashed_pw, 'seeker', 'jane_cv_sample.pdf')
    ]
    cursor.executemany('INSERT OR IGNORE INTO users (username, password, role, cv_filename) VALUES (?, ?, ?, ?)', users_data)

    jobs_data = [
        ('Python Backend Developer', 'Tech Corp', 'Remote', 'Looking for a Flask expert.', 1),
        ('Frontend Engineer', 'Tech Corp', 'Istanbul', 'React and CSS master needed.', 1),
        ('Data Analyst', 'Startup Inc', 'Ankara', 'SQL and Python data analysis.', 2),
        ('System Administrator', 'Startup Inc', 'Remote', 'Linux server management.', 2)
    ]
    cursor.executemany('INSERT INTO jobs (title, company, location, description, employer_id) VALUES (?, ?, ?, ?, ?)', jobs_data)

    conn.commit()
    conn.close()
    print("Veritabanı oluşturuldu ve örnek veriler başarıyla eklendi!")

if __name__ == '__main__':
    init_database()