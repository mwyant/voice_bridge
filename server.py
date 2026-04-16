import os
import uuid
import json
import time
import sqlite3
from typing import Optional
from fastapi import FastAPI, UploadFile, File, BackgroundTasks, Request, Response, Depends, HTTPException, Form
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.security import APIKeyCookie

app = FastAPI()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOADS_DIR = os.path.join(BASE_DIR, "uploads")
RESPONSES_DIR = os.path.join(BASE_DIR, "responses")
STATIC_DIR = os.path.join(BASE_DIR, "static")
DB_PATH = os.path.join(BASE_DIR, "voice_chat.db")

# Security Configuration
PASSCODE = "1234"
COOKIE_NAME = "voice_session"
api_key_cookie = APIKeyCookie(name=COOKIE_NAME, auto_error=False)

# Initialize Database
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # Updated messages table to include device_id/user_id for per-device history
    c.execute('''CREATE TABLE IF NOT EXISTS messages
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  session_id TEXT,
                  device_id TEXT,
                  role TEXT,
                  content TEXT,
                  audio_url TEXT,
                  timestamp REAL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS tasks
                 (session_id TEXT PRIMARY KEY,
                  device_id TEXT,
                  audio_path TEXT,
                  status TEXT,
                  timestamp REAL)''')
    conn.commit()
    conn.close()

init_db()

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
app.mount("/responses", StaticFiles(directory=RESPONSES_DIR), name="responses")

templates = Jinja2Templates(directory=STATIC_DIR)

# Auth Helper
async def get_current_device(voice_session: Optional[str] = Depends(api_key_cookie)):
    if not voice_session:
        return None
    return voice_session

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/login")
async def login(response: Response, passcode: str = Form(...)):
    if passcode == PASSCODE:
        # Each device gets a unique ID stored in their cookie
        device_id = str(uuid.uuid4())
        response = RedirectResponse(url="/", status_code=303)
        response.set_cookie(key=COOKIE_NAME, value=device_id, httponly=True, samesite="lax", secure=True)
        return response
    return RedirectResponse(url="/login?error=1", status_code=303)

@app.get("/", response_class=HTMLResponse)
async def index(request: Request, device_id: str = Depends(get_current_device)):
    if not device_id:
        return RedirectResponse(url="/login")
    return templates.TemplateResponse("index.html", {"request": request, "device_id": device_id})

@app.post("/upload")
async def upload_audio(file: UploadFile = File(...), device_id: str = Depends(get_current_device), target_session: Optional[str] = None):
    if not device_id:
        raise HTTPException(status_code=401)
    
    session_id = str(uuid.uuid4())
    original_ext = os.path.splitext(file.filename)[1] if file.filename else ".wav"
    filename = f"{session_id}{original_ext}"
    filepath = os.path.join(UPLOADS_DIR, filename)
    
    with open(filepath, "wb") as buffer:
        buffer.write(await file.read())
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # Store the target session if provided, else 'Main'
    target = target_session or "Main"
    c.execute("INSERT INTO tasks (session_id, device_id, audio_path, status, timestamp) VALUES (?, ?, ?, ?, ?)",
              (session_id, target, filepath, "pending", time.time()))
    conn.commit()
    conn.close()
    
    return {"session_id": session_id}

# Agent Endpoints (No auth needed for the bridge running on same machine)
@app.get("/agent/next")
async def get_next_task(session_id: str = "Main"):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # Bridge only pulls tasks intended for its session_id
    c.execute("SELECT session_id, device_id, audio_path FROM tasks WHERE status = 'pending' AND device_id = ? ORDER BY timestamp ASC LIMIT 1", (session_id,))
    row = c.fetchone()
    if not row:
        conn.close()
        return {"task": None}
    
    task_id, target_id, audio_path = row
    c.execute("UPDATE tasks SET status = 'processing' WHERE session_id = ?", (task_id,))
    conn.commit()
    conn.close()
    # Note: in this context, device_id in 'tasks' is actually the target SessionID from the launcher
    return {"task": {"session_id": task_id, "device_id": target_id, "audio_path": audio_path}}


@app.post("/agent/respond/{session_id}")
async def post_response(session_id: str, data: dict):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    ts = time.time()
    device_id = data.get("device_id")
    
    c.execute("INSERT INTO messages (session_id, device_id, role, content, timestamp) VALUES (?, ?, ?, ?, ?)",
              (session_id, device_id, "user", data.get("user_text"), ts - 0.1))
    
    c.execute("INSERT INTO messages (session_id, device_id, role, content, audio_url, timestamp) VALUES (?, ?, ?, ?, ?, ?)",
              (session_id, device_id, "agent", data.get("agent_text"), data.get("audio_url"), ts))
    
    c.execute("DELETE FROM tasks WHERE session_id = ?", (session_id,))
    
    conn.commit()
    conn.close()
    return {"status": "ok"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app, 
        host="0.0.0.0", 
        port=8133,
        ssl_keyfile=os.path.join(BASE_DIR, "key.pem"),
        ssl_certfile=os.path.join(BASE_DIR, "cert.pem")
    )
