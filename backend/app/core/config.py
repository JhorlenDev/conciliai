import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[3] / ".env")

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+psycopg2://postgres:postgres@localhost:5432/conciliacao_bancaria")
UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", "storage/uploads"))
DEFAULT_CORS_ORIGINS = {
    "http://192.168.1.99:3009",
    "http://localhost:3009",
    "http://127.0.0.1:3009",
}
configured_origins = {origin.strip() for origin in os.getenv("BACKEND_CORS_ORIGINS", "").split(",") if origin.strip()}
CORS_ORIGINS = sorted(DEFAULT_CORS_ORIGINS | configured_origins)
CORS_ORIGIN_REGEX = os.getenv("BACKEND_CORS_ORIGIN_REGEX", r"^https?://(localhost|127\.0\.0\.1|\[::1\])(:\d+)?$")
