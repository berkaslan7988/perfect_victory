from fastapi import FastAPI, HTTPException
from cryptography.fernet import Fernet
import sqlite3
import uvicorn
import os
from pydantic import BaseModel

# 1. INITIALIZE WEB APPLICATION & CRYPTO KEY
app = FastAPI(title="Secure DevSecOps Password Vault API")

# In production, set VAULT_CRYPTO_KEY environment variable
# Generate a key with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

CRYPTO_KEY = os.environ.get("VAULT_CRYPTO_KEY", "").encode() or Fernet.generate_key()
if not os.environ.get("VAULT_CRYPTO_KEY"):
    print("[WARNING] No VAULT_CRYPTO_KEY env var set. Using auto-generated key (data won't persist across restarts).") 
cipher_suite = Fernet(CRYPTO_KEY)

# 2. DATABASE SETUP (SQLite)
def init_db():
    conn = sqlite3.connect("vault.db")
    cursor = conn.cursor()
    # Create a table to store credentials safely if it doesn't exist
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS credentials (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            platform TEXT NOT NULL,
            username TEXT NOT NULL,
            encrypted_password TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()

init_db()

# 3. DATA MODELS (Pydantic models for incoming JSON request bodies)
class SecretPayload(BaseModel):
    platform: str
    username: str
    password: str

# 4. API ENDPOINTS (REST Controller)

@app.get("/")

def root():
    return {"status": "online", "message": "Welcome to the Military-Grade Password Vault API"}

@app.post("/secrets/save")

def save_secret(payload: SecretPayload):
    # Encrypt the raw password string before database insertion
    encrypted_bytes = cipher_suite.encrypt(payload.password.encode())
    encrypted_string = encrypted_bytes.decode()
    
    try:
        conn = sqlite3.connect("vault.db")
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO credentials (platform, username, encrypted_password) VALUES (?, ?, ?)",
            (payload.platform, payload.username, encrypted_string)
        )
        conn.commit()
        conn.close()
        return {"status": "success", "message": f"Credential for {payload.platform} secured in DB."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@app.get("/secrets/retrieve/{platform}")

def retrieve_secret(platform: str):
    conn = sqlite3.connect("vault.db")
    cursor = conn.cursor()
    cursor.execute("SELECT username, encrypted_password FROM credentials WHERE platform = ?", (platform,))
    result = cursor.fetchone()
    conn.close()
    
    if not result:
        raise HTTPException(status_code=404, detail=f"No credentials found for platform: {platform}")
        
    saved_username, saved_encrypted_password = result
    
    # Decrypt the password back to plain text for the authenticated user request
    
    decrypted_bytes = cipher_suite.decrypt(saved_encrypted_password.encode())
    decrypted_password = decrypted_bytes.decode()
    
    return {
        "platform": platform,
        "username": saved_username,
        "decrypted_password": decrypted_password,
        "security_note": "Decrypted on-the-fly via Fernet AES-256 architecture."
    }

# 5. SERVER EXECUTION BLOCK
if __name__ == "__main__":
    print("[*] Starting production-grade Uvicorn server...")
    # Run the server locally on port 8000
    uvicorn.run("vault_api:app", host="127.0.0.1", port=8000, reload=True)