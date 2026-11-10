"""Vercel FastAPI entrypoint. Streamlit remains available through app.py."""
from pathlib import Path
from fastapi.responses import FileResponse
from backend.main import app

@app.get('/', include_in_schema=False)
def dashboard():
    return FileResponse(Path(__file__).parent / 'public' / 'index.html')
