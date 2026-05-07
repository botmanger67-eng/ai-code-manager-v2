import os
import sys
from dotenv import load_dotenv

# Load environment variables from .env file if present
load_dotenv()

# Configuration keys and defaults
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
MODEL_NAME = os.getenv("MODEL_NAME", "deepseek-v4-flash")
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///sessions.db")
PORT = int(os.getenv("PORT", "5000"))

# Print status of key load on import
def _print_status():
    """Print loading status for critical environment variables."""
    def _check(key, value):
        if value:
            return f"✅ {key} loaded"
        else:
            return f"❌ {key} not set (application may not function correctly)"

    print("===== Configuration Load Status =====")
    print(_check("DEEPSEEK_API_KEY", DEEPSEEK_API_KEY))
    print(_check("GITHUB_TOKEN", GITHUB_TOKEN))
    print(f"ℹ️  MODEL_NAME = {MODEL_NAME}")
    print(f"ℹ️  DATABASE_URL = {DATABASE_URL}")
    print(f"ℹ️  PORT = {PORT}")
    print("=====================================")

    # Warn if critical keys are missing
    if not DEEPSEEK_API_KEY:
        print("WARNING: DEEPSEEK_API_KEY is missing. AI features will be unavailable.", file=sys.stderr)
    if not GITHUB_TOKEN:
        print("WARNING: GITHUB_TOKEN is missing. GitHub push functionality will be disabled.", file=sys.stderr)

_print_status()