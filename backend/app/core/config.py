import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[3] / ".env")

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+psycopg2://postgres:postgres@localhost:5432/conciliacao_bancaria")
UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", "storage/uploads"))
CORS_ORIGINS = os.getenv("BACKEND_CORS_ORIGINS", "http://localhost:3000").split(",")
