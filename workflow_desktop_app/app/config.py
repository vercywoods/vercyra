from pathlib import Path

APP_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = APP_ROOT / "data"
DB_PATH = DATA_DIR / "workflow_app.db"
SCHEMA_PATH = APP_ROOT / "app" / "db" / "schema.sql"
LOG_PATH = APP_ROOT / "data" / "workflow_app.log"
