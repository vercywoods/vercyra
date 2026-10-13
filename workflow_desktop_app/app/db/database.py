import sqlite3
from pathlib import Path

from app.config import DB_PATH, DATA_DIR, SCHEMA_PATH


class Database:
    def __init__(self, database_path: Path | str = DB_PATH):
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)

    def get_connection(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        return connection


def init_database() -> Database:
    database = Database()
    if not database.database_path.exists():
        database.database_path.touch()

    schema_sql = SCHEMA_PATH.read_text(encoding="utf-8")
    connection = database.get_connection()
    try:
        connection.executescript(schema_sql)
        connection.commit()
    finally:
        connection.close()

    return database
