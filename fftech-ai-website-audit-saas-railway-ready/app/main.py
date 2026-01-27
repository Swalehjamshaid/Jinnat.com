import os
from fastapi import FastAPI, WebSocket
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

app = FastAPI()

# Force Python to find the EXACT directory where main.py is running
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Ensure the 'static' folder exists to prevent background crashes
static_path = os.path.join(BASE_DIR, "static")
os.makedirs(static_path, exist_ok=True)
app.mount("/static", StaticFiles(directory=static_path), name="static")

@app.get("/", response_class=HTMLResponse)
async def get_index():
    # Force search in the same directory as main.py
    index_path = os.path.join(BASE_DIR, "index.html")
    
    if os.path.exists(index_path):
        with open(index_path, "r", encoding="utf-8") as f:
            return f.read()
    
    # This error message will help us verify the path in your browser
    return f"Deployment Error: index.html not found at {index_path}"

# WebSocket logic follows...
