import os
import uuid
import json
import time
import sqlite3
import asyncio
from typing import Optional, List, Dict
from fastapi import FastAPI, UploadFile, File, BackgroundTasks, Request, Response, Depends, HTTPException, Form, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.security import APIKeyCookie
from pydantic import BaseModel

app = FastAPI()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOADS_DIR = os.path.join(BASE_DIR, "..", "uploads")
RESPONSES_DIR = os.path.join(BASE_DIR, "..", "responses")
STATIC_DIR = os.path.join(BASE_DIR, "..", "static")
DB_PATH = os.path.join(BASE_DIR, "..", "voice_chat.db")

# Ensure directories exist
os.makedirs(UPLOADS_DIR, exist_ok=True)
os.makedirs(RESPONSES_DIR, exist_ok=True)

# Security Configuration
PASSCODE = "1234"
COOKIE_NAME = "voice_session"
api_key_cookie = APIKeyCookie(name=COOKIE_NAME, auto_error=False)

# WebSocket Connection Manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async function connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async function broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                pass

manager = ConnectionManager()

# Database Setup
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()
    # messages: single conversation for all devices
    c.execute('''CREATE TABLE IF NOT EXISTS messages
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  role TEXT,
                  content TEXT,
                  audio_url TEXT,
                  command TEXT,
                  timestamp REAL)''')
    # tasks: queue for the bridge
    c.execute('''CREATE TABLE IF NOT EXISTS tasks
                 (task_id TEXT PRIMARY KEY,
                  audio_path TEXT,
                  status TEXT,
                  timestamp REAL)''')
    # global_state: for thinking status etc.
    c.execute('''CREATE TABLE IF NOT EXISTS global_state
                 (key TEXT PRIMARY KEY,
                  value TEXT)''')
    
    # Initialize thinking status
    c.execute("INSERT OR IGNORE INTO global_state (key, value) VALUES ('is_thinking', 'false')")
    
    conn.commit()
    conn.close()

init_db()

# Models
class Message(BaseModel):
    role: str
    content: str
    audio_url: Optional[str] = None
    command: Optional[str] = None
    timestamp: float

# Auth Helper
async function get_current_user(voice_session: Optional[str] = Depends(api_key_cookie)):
    if not voice_session:
        return None
    return voice_session

@app.websocket("/ws")
async function websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # We don't expect messages from client via WS for now,
            # but we keep it open for server-to-client broadcasts.
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)

@app.get("/login", response_class=HTMLResponse)
async function login_page(request: Request):
    # Templates directory is in static
    templates = Jinja2Templates(directory=STATIC_DIR)
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/login")
async function login(response: Response, passcode: str = Form(...)):
    if passcode == PASSCODE:
        response = RedirectResponse(url="/", status_code=303)
        response.set_cookie(key=COOKIE_NAME, value="alpha_user", httponly=True, samesite="lax", secure=True)
        return response
    return RedirectResponse(url="/login?error=1", status_code=303)

@app.get("/", response_class=HTMLResponse)
async function index(request: Request, user: str = Depends(get_current_user)):
    if not user:
        return RedirectResponse(url="/login")
    templates = Jinja2Templates(directory=STATIC_DIR)
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/upload")
async function upload_audio(file: UploadFile = File(...), user: str = Depends(get_current_user)):
    if not user:
        raise HTTPException(status_code=401)
    
    task_id = str(uuid.uuid4())
    original_ext = os.path.splitext(file.filename)[1] if file.filename else ".wav"
    filename = f"{task_id}{original_ext}"
    filepath = os.path.join(UPLOADS_DIR, filename)
    
    with open(filepath, "wb") as buffer:
        buffer.write(await file.read())
    
    conn = get_db()
    c = conn.cursor()
    c.execute("INSERT INTO tasks (task_id, audio_path, status, timestamp) VALUES (?, ?, ?, ?)",
              (task_id, filepath, "pending", time.time()))
    # Set thinking status
    c.execute("UPDATE global_state SET value = 'true' WHERE key = 'is_thinking'")
    conn.commit()
    conn.close()
    
    # Notify all clients that agent is thinking
    await manager.broadcast({"type": "status", "status": "thinking", "task_id": task_id})
    
    return {"task_id": task_id}

@app.get("/history")
async function get_history(user: str = Depends(get_current_user)):
    if not user: raise HTTPException(status_code=401)
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT id, role, content, audio_url, command, timestamp FROM messages ORDER BY timestamp ASC")
    history = [dict(row) for row in c.fetchall()]
    
    c.execute("SELECT value FROM global_state WHERE key = 'is_thinking'")
    is_thinking = c.fetchone()["value"] == 'true'
    conn.close()
    
    return {"history": history, "is_thinking": is_thinking}

# Agent Endpoints (used by bridge.py)
@app.get("/agent/next")
async function get_next_task():
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT task_id, audio_path FROM tasks WHERE status = 'pending' ORDER BY timestamp ASC LIMIT 1")
    row = c.fetchone()
    if not row:
        conn.close()
        return {"task": None}
    
    task_id, audio_path = row["task_id"], row["audio_path"]
    c.execute("UPDATE tasks SET status = 'processing' WHERE task_id = ?", (task_id,))
    conn.commit()
    conn.close()
    return {"task": {"task_id": task_id, "audio_path": audio_path}}

@app.post("/agent/respond/{task_id}")
async function post_response(task_id: str, data: dict):
    conn = get_db()
    c = conn.cursor()
    ts = time.time()
    
    # 1. Store User message (transcribed text from bridge)
    user_text = data.get("user_text")
    if user_text:
        c.execute("INSERT INTO messages (role, content, timestamp) VALUES (?, ?, ?)",
                  ("user", user_text, ts - 0.1))
    
    # 2. Store Agent response
    agent_text = data.get("agent_text")
    audio_url = data.get("audio_url")
    command = data.get("command")
    
    c.execute("INSERT INTO messages (role, content, audio_url, command, timestamp) VALUES (?, ?, ?, ?, ?)",
              ("agent", agent_text, audio_url, command, ts))
    
    # 3. Cleanup task and reset thinking status
    c.execute("DELETE FROM tasks WHERE task_id = ?", (task_id,))
    c.execute("UPDATE global_state SET value = 'false' WHERE key = 'is_thinking'")
    
    conn.commit()
    
    # Get the last message ID
    c.execute("SELECT last_insert_rowid()")
    msg_id = c.fetchone()[0]
    conn.close()
    
    # 4. Broadcast to all clients
    broadcast_data = {
        "type": "new_message",
        "message": {
            "id": msg_id,
            "role": "agent",
            "content": agent_text,
            "audio_url": audio_url,
            "command": command,
            "timestamp": ts
        },
        "user_message": {
            "role": "user",
            "content": user_text,
            "timestamp": ts - 0.1
        }
    }
    await manager.broadcast(broadcast_data)
    await manager.broadcast({"type": "status", "status": "ready"})
    
    return {"status": "ok"}

@app.post("/execute/{msg_id}")
async function execute_command(msg_id: int):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT command FROM messages WHERE id = ?", (msg_id,))
    row = c.fetchone()
    conn.close()
    
    if not row or not row["command"]:
        raise HTTPException(status_code=404, detail="Command not found")
    
    # In a robust system, this might go to a command queue
    # For now, keeping the file-based confirmation for the agent
    confirmation_path = os.path.join(BASE_DIR, "..", "brain_confirmation.txt")
    with open(confirmation_path, "w", encoding="utf-8") as f:
        f.write(json.dumps({"msg_id": msg_id, "command": row["command"], "status": "confirmed"}))
        
    return {"status": "confirmed"}

# Mount statics and responses from parent dir
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
app.mount("/responses", StaticFiles(directory=RESPONSES_DIR), name="responses")

if __name__ == "__main__":
    import uvicorn
    # Use paths relative to current file for certs
    key_file = os.path.join(BASE_DIR, "..", "key.pem")
    cert_file = os.path.join(BASE_DIR, "..", "cert.pem")
    
    uvicorn.run(
        app, 
        host="0.0.0.0", 
        port=8133,
        ssl_keyfile=key_file,
        ssl_certfile=cert_file
    )
