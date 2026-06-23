from flask import Flask, request, jsonify
from flask_cors import CORS
import sqlite3

app = Flask(__name__)
CORS(app)

def init_db():
    conn = sqlite3.connect('waitlist.db')
    c = conn.cursor()
    c.execute(''' CREATE TABLE IF NOT EXISTS users
              (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, email TEXT)''')
    conn.commit()
    conn.close()

init_db()


@app.route('/api/join', methods=['POST', 'OPTIONS'])
def join_waitlist():
    if request.method == 'OPTIONS':
        return '', 200
        
    try:
        data = request.get_json()
        name = data.get('name')
        email = data.get('email')

        conn = sqlite3.connect('waitlist.db')
        c = conn.cursor()
        c.execute("INSERT INTO users (name, email) VALUES (?, ?)", (name, email))
        conn.commit()
        conn.close()

        print(f"[+] New entry saved: {name} - {email}")
        return jsonify({"status": "success", "message": "Successfully added!"}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
    
if __name__ == "__main__":
    print("--- Web Backend Server Running on Port 5000 ---\n")
    app.run(port = 5000)