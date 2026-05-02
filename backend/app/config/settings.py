"""
File purpose:
- Central configuration module for backend runtime behavior.
- Loads environment variables once and exposes typed config constants to the app.
- Keeps sensitive/environment-specific settings out of route/service code.
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
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "change-me-in-backend-env")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7"))
SMTP_HOST = os.getenv("SMTP_HOST", "").strip()
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USERNAME = os.getenv("SMTP_USERNAME", "").strip()
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_FROM_EMAIL = os.getenv("SMTP_FROM_EMAIL", SMTP_USERNAME).strip()
SMTP_FROM_NAME = os.getenv("SMTP_FROM_NAME", "RAG Workspace")
SMTP_USE_TLS = os.getenv("SMTP_USE_TLS", "true").strip().lower() in {"1", "true", "yes", "on"}


# Detailed function explanation:
# - Purpose: `_build_database_url` handles one focused step of this module's workflow.
# - Usage in flow: Called by routes/services/helpers to keep the logic modular and reusable.
# - Input/Output intent: Validates/normalizes inputs, performs its task, and returns predictable output
#   (or raises a clear exception) so downstream code can continue reliably.
def _build_database_url() -> str:
    # Build one SQLAlchemy-ready database URL from env vars.
    # Preference order:
    # 1) explicit DATABASE_URL
    # 2) compose from MYSQL_* parts
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


# Detailed function explanation:
# - Purpose: `_build_vector_store_path` handles one focused step of this module's workflow.
# - Usage in flow: Called by routes/services/helpers to keep the logic modular and reusable.
# - Input/Output intent: Validates/normalizes inputs, performs its task, and returns predictable output
#   (or raises a clear exception) so downstream code can continue reliably.
def _build_vector_store_path() -> str:
    # Resolve vector DB directory to an absolute normalized path so all modules
    # read/write the same location regardless of current working directory.
    raw_path = os.getenv(
        "VECTOR_STORE_PATH",
        os.getenv("APP_MILVUS_URI", str(BASE_DIR / "backend" / "chroma_db")),
    ).strip()
    path = Path(raw_path).expanduser()
    if not path.is_absolute():
        # Treat relative vector paths as repo-root relative (stable across launch cwd).
        path = (BASE_DIR / path).resolve()
    else:
        path = path.resolve()
    return str(path)


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
