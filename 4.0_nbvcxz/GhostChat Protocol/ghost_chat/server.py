from fastapi import FastAPI, WebSocket, WebSocketDisconnect, UploadFile, File, HTTPException
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from typing import Dict, List
import uvicorn
import hashlib
import json
import os
import shutil
import uuid
import time
import asyncio

app = FastAPI(title="GhostChat E2EE & Ephemeral Storage Server")

# --- CORS MIDDLEWARE ---
# This is CRITICAL for allowing the PC browser and Android WebView to upload files
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for local network testing
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Directory for temporary file storage
UPLOAD_DIR = "temp_ghost_files"
if not os.path.exists(UPLOAD_DIR):
    os.makedirs(UPLOAD_DIR)

# Memory storage for connections and their files
active_connections: Dict[str, dict] = {}

# --- BACKGROUND CLEANUP TASK ---
async def cleanup_expired_files():
    """Periodically checks and deletes expired files."""
    while True:
        try:
            current_time = time.time()
            for client_id, data in list(active_connections.items()):
                files = data.get("files", {})
                for file_id, expiry in list(files.items()):
                    if current_time > expiry:
                        file_path = os.path.join(UPLOAD_DIR, file_id)
                        if os.path.exists(file_path):
                            os.remove(file_path)
                            print(f"[AUTO-CLEANUP] Expired file deleted: {file_id}")
                        del files[file_id]

            # Cleanup orphaned files (older than 10 mins)
            for filename in os.listdir(UPLOAD_DIR):
                file_path = os.path.join(UPLOAD_DIR, filename)
                if os.path.getmtime(file_path) < current_time - 600:
                    os.remove(file_path)
                    print(f"[AUTO-CLEANUP] Orphaned file deleted: {filename}")
        except Exception as e:
            print(f"[CLEANUP ERROR] {e}")

        await asyncio.sleep(60)

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(cleanup_expired_files())

# --- FILE OPERATIONS ---
@app.post("/upload/{client_id}")
async def upload_file(client_id: str, file: UploadFile = File(...)):
    # Note: client_id validation is removed here for simpler local testing
    # as PC browser might have a different session if refreshed.
    
    file_id = str(uuid.uuid4())
    file_path = os.path.join(UPLOAD_DIR, file_id)

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # Files expire in 10 minutes for easier testing
    expiry_time = time.time() + 600

    if client_id in active_connections:
        active_connections[client_id]["files"][file_id] = expiry_time

    print(f"[GHOST-DRIVE] File Uploaded: {file_id} (Client: {client_id})")
    return {"file_id": file_id}

@app.get("/download/{file_id}")
async def download_file(file_id: str):
    file_path = os.path.join(UPLOAD_DIR, file_id)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found or expired")

    return FileResponse(file_path)

# --- WEBSOCKET RELAY ---
@app.websocket("/ws")
async def websocket_endpoint(web_socket: WebSocket):
    await web_socket.accept()
    client_id = None

    try:
        while True:
            data = await web_socket.receive_json()
            msg_type = data.get("type")

            if msg_type == "register":
                pub_key = data.get("pubKey")
                pub_key_str = json.dumps(pub_key, sort_keys=True)
                client_id = hashlib.sha256(pub_key_str.encode()).hexdigest()[:16]

                active_connections[client_id] = {
                    "ws": web_socket,
                    "pubKey": pub_key,
                    "files": {}
                }
                await web_socket.send_json({"type": "init", "id": client_id})
                print(f"[SERVER] Identity Registered : {client_id}")

            elif msg_type == "get_key":
                target_id = data.get("target_id")
                if target_id in active_connections:
                    target_pub = active_connections[target_id]["pubKey"]
                    await web_socket.send_json({
                        "type": "pub_key",
                        "target_id": target_id,
                        "pubKey": target_pub
                    })

            elif msg_type == "message":
                target_id = data.get("target_id")
                if target_id in active_connections:
                    target_ws = active_connections[target_id]["ws"]
                    sender_pub = active_connections[client_id]["pubKey"]

                    await target_ws.send_json({
                        "type": "message",
                        "sender_id": client_id,
                        "sender_pubKey": sender_pub,
                        "payload": data.get("payload"),
                        "iv": data.get("iv"),
                        "drive_data": data.get("drive_data")
                    })

    except WebSocketDisconnect:
        if client_id and client_id in active_connections:
            files_to_delete = active_connections[client_id]["files"]
            for f_id in files_to_delete:
                f_path = os.path.join(UPLOAD_DIR, f_id)
                if os.path.exists(f_path):
                    os.remove(f_path)

            del active_connections[client_id]
            print(f"[SERVER] Purged : {client_id}")

if __name__ == "__main__":
    print("[*] Starting GhostDrive Relay Node on port 8000...")
    uvicorn.run(app, host="0.0.0.0", port=8000)
