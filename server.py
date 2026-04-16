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

# Initialize Database (Simplified for Alpha)
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS messages
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  session_id TEXT,
                  role TEXT,
                  content TEXT,
                  audio_url TEXT,
                  command TEXT,
                  timestamp REAL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS tasks
                 (session_id TEXT PRIMARY KEY,
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
async def get_current_user(voice_session: Optional[str] = Depends(api_key_cookie)):
    # Simply check if the cookie exists
    return voice_session

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/login")
async def login(response: Response, passcode: str = Form(...)):
    if passcode == PASSCODE:
        response = RedirectResponse(url="/", status_code=303)
        # Use a fixed session for everyone in the alpha
        response.set_cookie(key=COOKIE_NAME, value="alpha_user", httponly=True, samesite="lax", secure=True)
        return response
    return RedirectResponse(url="/login?error=1", status_code=303)

@app.get("/", response_class=HTMLResponse)
async def index(request: Request, user: str = Depends(get_current_user)):
    if not user:
        return RedirectResponse(url="/login")
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/upload")
async def upload_audio(file: UploadFile = File(...), user: str = Depends(get_current_user)):
    if not user:
        raise HTTPException(status_code=401)
    
    session_id = str(uuid.uuid4())
    original_ext = os.path.splitext(file.filename)[1] if file.filename else ".wav"
    filename = f"{session_id}{original_ext}"
    filepath = os.path.join(UPLOADS_DIR, filename)
    
    with open(filepath, "wb") as buffer:
        buffer.write(await file.read())
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO tasks (session_id, audio_path, status, timestamp) VALUES (?, ?, ?, ?)",
              (session_id, filepath, "pending", time.time()))
    conn.commit()
    conn.close()
    
    return {"session_id": session_id}

@app.get("/status/{session_id}")
async def get_status(session_id: str, user: str = Depends(get_current_user)):
    if not user: raise HTTPException(status_code=401)
        
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT content, audio_url FROM messages WHERE session_id = ? AND role = 'agent'", (session_id,))
    row = c.fetchone()
    if row:
        conn.close()
        return {"status": "completed", "text": row[0], "audio_url": row[1]}
    
    c.execute("SELECT status FROM tasks WHERE session_id = ?", (session_id,))
    row = c.fetchone()
    conn.close()
    if row: return {"status": row[0]}
    return {"status": "not_found"}

@app.get("/history")
async def get_history(user: str = Depends(get_current_user)):
    if not user: raise HTTPException(status_code=401)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT role, content, audio_url, command, timestamp FROM messages ORDER BY timestamp ASC")
    history = [{"role": r, "content": c, "audio_url": a, "command": cmd, "timestamp": t} for r, c, a, cmd, t in c.fetchall()]
    conn.close()
    return history

# Agent Endpoints
@app.get("/agent/next")
async def get_next_task():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT session_id, audio_path FROM tasks WHERE status = 'pending' ORDER BY timestamp ASC LIMIT 1")
    row = c.fetchone()
    if not row:
        conn.close()
        return {"task": None}
    
    session_id, audio_path = row
    c.execute("UPDATE tasks SET status = 'processing' WHERE session_id = ?", (session_id,))
    conn.commit()
    conn.close()
    return {"task": {"session_id": session_id, "audio_path": audio_path}}

@app.post("/execute/{msg_id}")
async def execute_command(msg_id: int):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT command FROM messages WHERE id = ?", (msg_id,))
    row = c.fetchone()
    conn.close()
    
    if not row or not row[0]:
        raise HTTPException(status_code=404, detail="Command not found")
    
    # Write confirmation file for the agent to pick up
    with open(os.path.join(BASE_DIR, "brain_confirmation.txt"), "w", encoding="utf-8") as f:
        f.write(json.dumps({"msg_id": msg_id, "command": row[0], "status": "confirmed"}))
        
    return {"status": "confirmed"}

@app.post("/agent/respond/{session_id}")
async def post_response(session_id: str, data: dict):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    ts = time.time()
    c.execute("INSERT INTO messages (session_id, role, content, timestamp) VALUES (?, ?, ?, ?)",
              (session_id, "user", data.get("user_text"), ts - 0.1))
    
    # Store command if present
    c.execute("INSERT INTO messages (session_id, role, content, audio_url, command, timestamp) VALUES (?, ?, ?, ?, ?, ?)",
              (session_id, "agent", data.get("agent_text"), data.get("audio_url"), data.get("command"), ts))
    
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
