# GhostChat Protocol — End-to-End Encrypted Messaging

A secure messaging app where messages are encrypted on the sender's device and
only decrypted on the recipient's — the server never sees plaintext. Built in
**web** and **mobile** and **windows** variants over a shared Python server.

## Structure

```
GhostChat Protocol/
├── ghost_chat/
-index.html
-server.py
-server.exe
-ghost_chat.exe
-GhostChat.apk

```

## Concept

- **End-to-end encryption (E2EE):** plaintext never leaves the client; the relay
  server only forwards ciphertext.
- **Thin server:** `server.py` acts as a message relay between connected clients.
- **Multiple clients:** a static web client and a mobile (`www/`) client share the
  same backend.

## Run

```bash
cd "GhostChat Protocol/ghost_chat"
python server.py
# then open ../ghost_chat/index.html in a browser
```
Or you can use server.exe to start server and open the ghost_chat.exe application

And also you can download GhostChat.apk in your android device
