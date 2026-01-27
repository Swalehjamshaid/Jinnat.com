import os
from fastapi import FastAPI, WebSocket
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

app = FastAPI()

# 1. This identifies the EXACT folder where main.py lives
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# 2. Ensure static folder exists to prevent 'Directory not found' errors
static_path = os.path.join(BASE_DIR, "static")
os.makedirs(static_path, exist_ok=True)
app.mount("/static", StaticFiles(directory=static_path), name="static")

@app.get("/", response_class=HTMLResponse)
async def get_index():
    # 3. Force the server to look for index.html in the same folder as this script
    index_path = os.path.join(BASE_DIR, "index.html")
    
    if os.path.exists(index_path):
        with open(index_path, "r", encoding="utf-8") as f:
            return f.read()
    
    # This debug message will appear in your browser if the path is still wrong
    return f"Deployment Error: index.html not found at {index_path}"

# Rest of your WebSocket code...
