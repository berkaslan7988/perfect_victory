import sqlite3
from werkzeug.security import generate_password_hash

def init_forum_db():
    conn = sqlite3.connect('forum.db')
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            description TEXT
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS threads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            category_id INTEGER,
            user_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (category_id) REFERENCES categories (id),
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS replies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            content TEXT NOT NULL,
            thread_id INTEGER,
            user_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (thread_id) REFERENCES threads (id),
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')

    hashed_pw = generate_password_hash('123456')
    users = [('coder_neo', hashed_pw), ('gamer_girl', hashed_pw), ('tech_guru', hashed_pw)]
    cursor.executemany('INSERT OR IGNORE INTO users (username, password) VALUES (?, ?)', users)

    categories = [
        ('Software Development', 'Discuss programming languages, frameworks, and tools.'),
        ('Gaming', 'Talk about PC, console, and mobile games.'),
        ('General Chat', 'Anything else that doesn\'t fit elsewhere.')
    ]
    cursor.executemany('INSERT OR IGNORE INTO categories (name, description) VALUES (?, ?)', categories)


    threads = [
        ('Is Flask better than Django for small projects?', 'I am planning to build a small API. Which one should I choose?', 1, 1),
        ('Cyberpunk 2077 in 2026: Is it worth playing now?', 'I heard they fixed all the bugs. Should I buy it?', 2, 2)
    ]
    cursor.executemany('INSERT INTO threads (title, content, category_id, user_id) VALUES (?, ?, ?, ?)', threads)


    replies = [
        ('Definitely go with Flask! It is lightweight and perfect for small APIs.', 1, 3),
        ('Yes! The game is absolutely amazing right now. Highly recommended.', 2, 1)
    ]
    cursor.executemany('INSERT INTO replies (content, thread_id, user_id) VALUES (?, ?, ?)', replies)

    conn.commit()
    conn.close()
    print("Success!")

if __name__ == '__main__':
    init_forum_db()