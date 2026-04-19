"""
File purpose:
- Holds backend path-based configuration values.
- Provides a single place to define upload/storage directories.
"""

from pathlib import Path
import os
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parents[3]
UPLOAD_DIR = BASE_DIR / "backend" / "uploads"
ENV_FILE = BASE_DIR / "backend" / ".env"

# Load values from backend/.env into process environment.
load_dotenv(dotenv_path=ENV_FILE, override=False)

# Put your key in backend/.env as: GEMINI_API_KEY=your_key_here
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# Comma-separated list of allowed frontend origins for CORS.
CORS_ORIGINS = [
    origin.strip()
    for origin in os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",")
    if origin.strip()
]
