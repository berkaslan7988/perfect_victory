import sqlite3

# Connect to database (creates it if not exists)
conn = sqlite3.connect('news.db')
c = conn.cursor()

# Create table for articles
c.execute('''CREATE TABLE IF NOT EXISTS articles
             (id INTEGER PRIMARY KEY, title TEXT, category TEXT, content TEXT)''')

# Insert some sample data (Seed data)
c.execute("INSERT INTO articles (title, category, content) VALUES ('Cyber Security Trends 2026', 'Tech', 'AI-driven attacks are increasing...')")
c.execute("INSERT INTO articles (title, category, content) VALUES ('Local Data Storage Tips', 'OpSec', 'Always keep your physical drives encrypted...')")

conn.commit()
conn.close()
print("Database created and seeded.")