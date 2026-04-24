"""
File purpose:
- Holds backend path-based configuration values.
- Provides a single place to define upload/storage directories.
"""

from pathlib import Path
import os
from urllib.parse import quote_plus
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parents[3]
UPLOAD_DIR = BASE_DIR / "backend" / "uploads"
ENV_FILE = BASE_DIR / "backend" / ".env"

# Load values from backend/.env into process environment.
load_dotenv(dotenv_path=ENV_FILE, override=False)

# Put your keys in backend/.env as needed, for example:
# GROQ_API_KEY=your_key_here
# GROQ_MODEL=llama-3.3-70b-versatile
# GEMINI_API_KEY=your_key_here
# DATABASE_URL=mysql+pymysql://root:password@localhost:3306/ragdb
# MYSQL_HOST=localhost
# MYSQL_PORT=3306
# MYSQL_DATABASE=ragdb
# MYSQL_USER=root
# MYSQL_PASSWORD=your_password_here
# VECTOR_STORE_PATH=backend/chroma_db
# VECTOR_COLLECTION=document_chunks
# EMBEDDING_MODEL=BAAI/bge-small-en-v1.5
# VECTOR_DIMENSION=384
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
DEFAULT_INGESTION_USERNAME = os.getenv("DEFAULT_INGESTION_USERNAME", "system_uploader")
DEFAULT_INGESTION_EMAIL = os.getenv("DEFAULT_INGESTION_EMAIL", "system.uploader@gmail.com")
DEFAULT_INGESTION_PASSWORD_HASH = os.getenv("DEFAULT_INGESTION_PASSWORD_HASH", "auth-not-enabled")


def _build_database_url() -> str:
    """
    Resolve the database connection string.

    Priority:
    1. Use DATABASE_URL directly when provided.
    2. Otherwise build a MySQL URL from MYSQL_* environment variables.
    """
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        return database_url

    mysql_host = os.getenv("MYSQL_HOST", "localhost")
    mysql_port = os.getenv("MYSQL_PORT", "3306")
    mysql_database = os.getenv("MYSQL_DATABASE", "ragdb")
    mysql_user = os.getenv("MYSQL_USER", "root")
    mysql_password = quote_plus(os.getenv("MYSQL_PASSWORD", ""))
    mysql_driver = os.getenv("MYSQL_DRIVER", "pymysql")

    return (
        f"mysql+{mysql_driver}://{mysql_user}:{mysql_password}"
        f"@{mysql_host}:{mysql_port}/{mysql_database}"
    )


def _build_vector_store_path() -> str:
    raw_path = os.getenv(
        "VECTOR_STORE_PATH",
        os.getenv("APP_MILVUS_URI", str(BASE_DIR / "backend" / "chroma_db")),
    ).strip()
    return str(Path(raw_path).expanduser().resolve())


DATABASE_URL = _build_database_url()
VECTOR_STORE_PATH = _build_vector_store_path()
VECTOR_COLLECTION = os.getenv("VECTOR_COLLECTION", os.getenv("MILVUS_COLLECTION", "document_chunks"))
VECTOR_SEARCH_LIMIT = int(os.getenv("VECTOR_SEARCH_LIMIT", os.getenv("MILVUS_SEARCH_LIMIT", "5")))
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5")
VECTOR_DIMENSION = int(os.getenv("VECTOR_DIMENSION", "384"))

# Comma-separated list of allowed frontend origins for CORS.
CORS_ORIGINS = [
    origin.strip()
    for origin in os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",")
    if origin.strip()
]

MAX_UPLOAD_SIZE_MB = int(os.getenv("MAX_UPLOAD_SIZE_MB", "25"))
MAX_UPLOAD_SIZE_BYTES = MAX_UPLOAD_SIZE_MB * 1024 * 1024
