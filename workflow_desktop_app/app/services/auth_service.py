import hashlib
from datetime import datetime

from app.db.database import Database
from app.models.user import User


class AuthService:
    def __init__(self, database: Database | None = None):
        self.database = database or Database()

    @staticmethod
    def hash_password(password: str) -> str:
        return hashlib.sha256(password.strip().encode("utf-8")).hexdigest()

    def authenticate(self, username: str, password: str) -> User | None:
        username = username.strip()
        if not username or not password:
            return None

        connection = self.database.get_connection()
        try:
            row = connection.execute(
                "SELECT id, username, email FROM users WHERE username = ? AND password_hash = ?",
                (username, self.hash_password(password)),
            ).fetchone()
        finally:
            connection.close()

        if row is None:
            return None

        return User(
            id=row["id"],
            username=row["username"],
            email=row["email"],
        )

    def register_user(self, username: str, password: str, email: str | None = None) -> User | None:
        username = username.strip()
        if not username or not password:
            return None

        connection = self.database.get_connection()
        try:
            existing = connection.execute(
                "SELECT id FROM users WHERE username = ?",
                (username,),
            ).fetchone()
            if existing is not None:
                return None

            cursor = connection.execute(
                "INSERT INTO users (username, password_hash, email, created_at) VALUES (?, ?, ?, ?)",
                (username, self.hash_password(password), email, datetime.utcnow().isoformat(timespec="seconds")),
            )
            connection.commit()
            user_id = cursor.lastrowid
        finally:
            connection.close()

        return User(id=user_id, username=username, email=email)


def create_default_user() -> User | None:
    service = AuthService()
    if service.authenticate("admin", "admin123") is not None:
        return service.authenticate("admin", "admin123")

    return service.register_user("admin", "admin123", "admin@local.app")
