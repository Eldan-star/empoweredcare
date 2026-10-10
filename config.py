import os
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

load_dotenv(override=True)

# Application Paths
BASE_DIR = Path(__file__).parent
UPLOAD_DIR = BASE_DIR / "uploads"
LOG_DIR = BASE_DIR / "logs"

UPLOAD_DIR.mkdir(exist_ok=True)
LOG_DIR.mkdir(exist_ok=True)

def get_session_dir(session_id: str):
    session_dir = LOG_DIR / session_id
    session_dir.mkdir(exist_ok=True)
    return session_dir

# API Settings
API_HOST = "0.0.0.0"
API_PORT = 8000
API_TITLE = "Empowered Care - Multi-Agent Disease Outbreak Detection System"
API_VERSION = "1.0.0"

# Security Settings
# Environment: "development" allows a throwaway key; anything else requires SECRET_KEY.
APP_ENV = os.getenv("APP_ENV", "development")
SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    if APP_ENV != "development":
        raise RuntimeError("SECRET_KEY must be set when APP_ENV is not 'development'")
    import secrets
    # Random per process: tokens stop working on restart, which is acceptable in development.
    SECRET_KEY = secrets.token_hex(32)
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 hours
INVITE_TOKEN_EXPIRE_HOURS = 48
RESET_TOKEN_EXPIRE_HOURS = 1

# SMTP Settings
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
SMTP_FROM = os.getenv("SMTP_FROM")
SMTP_USE_TLS = os.getenv("SMTP_USE_TLS", "true").lower() == "true"

# Frontend URL (for invitation/reset links)
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:8080")

# Logging
LOG_LEVEL = "INFO"
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

# Database (PostgreSQL). Format: postgresql+psycopg://USER:PASSWORD@HOST:PORT/DATABASE
DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql+psycopg://empoweredcare:empoweredcare@localhost:5432/empoweredcare"
)

# Gemini AI Settings
# Comma-separated in .env, tried in order. Run `python list_models.py` to see what your key can use.
GEMINI_MODEL_PREFERENCES = [
    m.strip() for m in os.getenv("GEMINI_MODELS", "gemini-3.8-flash").split(",") if m.strip()
]
# Requests per minute allowed per model (0 = no pacing). Free tier: 5 for flash models.
GEMINI_RPM = int(os.getenv("GEMINI_RPM", "0"))
# Longest one AI call may take, waits included, before giving up.
GEMINI_CALL_BUDGET_SECONDS = int(os.getenv("GEMINI_CALL_BUDGET_SECONDS", "60"))

# Validation Settings
MAX_TEXT_LENGTH = int(os.getenv("MAX_TEXT_LENGTH", "20000"))
MAX_QUERY_LENGTH = 500
VALID_SYMPTOMS = [
    "fever", "cough", "headache", "vomiting", "diarrhea",
    "rash", "fatigue", "pain", "nausea", "dizziness",
    "sore throat", "runny nose", "chills", "sweating",
    "muscle pain", "joint pain", "loss of appetite"
]

# Risk Assessment
RISK_THRESHOLDS = {
    "LOW": 0.3,
    "MEDIUM": 0.6,
    "HIGH": 0.8
}

# Data Storage (for production, use a database)
MAX_STORED_REPORTS = 1000

# CORS Settings (restrict in production)
# Comma-separated list, e.g. "https://app.example.org,http://localhost:8080"
ALLOWED_ORIGINS = [
    o.strip()
    for o in os.getenv("ALLOWED_ORIGINS", "http://localhost:8080,http://127.0.0.1:8080").split(",")
    if o.strip()
]

# Web scraping in the context research agent (Google/Bing result pages) is off by default.
ENABLE_WEB_RESEARCH = os.getenv("ENABLE_WEB_RESEARCH", "false").lower() == "true"