import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[3] / ".env")

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+psycopg2://postgres:postgres@localhost:5432/conciliacao_bancaria")
UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", "storage/uploads"))
DEFAULT_CORS_ORIGINS = {
    "http://191.252.181.8:3009",
    "http://localhost:3009",
    "http://127.0.0.1:3009",
}
configured_origins = {origin.strip() for origin in os.getenv("BACKEND_CORS_ORIGINS", "").split(",") if origin.strip()}
CORS_ORIGINS = sorted(DEFAULT_CORS_ORIGINS | configured_origins)
