import sqlite3
import os
import sys

DB_PATH = r"C:\Users\mwyant\.opencode\tools\voice_bridge\voice_chat.db"

def get_context(limit=10):
    if not os.path.exists(DB_PATH):
        print("Database not found.")
        return

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT role, content FROM messages ORDER BY timestamp DESC LIMIT ?", (limit,))
    rows = c.fetchall()
    conn.close()

    print("\n--- CONVERSATION CONTEXT ---")
    for role, content in reversed(rows):
        print(f"[{role.upper()}]: {content}")
    print("----------------------------\n")

if __name__ == "__main__":
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else 10
    get_context(limit)
