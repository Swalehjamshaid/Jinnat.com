import os
from fastapi import FastAPI
from fastapi.responses import HTMLResponse

app = FastAPI()

# This finds the folder where main.py actually lives
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

@app.get("/")
async def get():
    # This creates a reliable path to: app/templates/index.html
    template_path = os.path.join(BASE_DIR, "templates", "index.html")
    
    try:
        with open(template_path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    except FileNotFoundError:
        # If it still fails, this message will tell you exactly where it looked
        return HTMLResponse(
            content=f"Error: index.html not found. Backend searched: {template_path}", 
            status_code=404
        )
