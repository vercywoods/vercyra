import csv
from datetime import datetime
from pathlib import Path

from app.db.database import Database


class ExportService:
    def __init__(self, database: Database | None = None):
        self.database = database or Database()

    def export_workflow_items(self, file_path: str | Path | None = None) -> Path:
        export_dir = Path(file_path) if file_path is not None else Path.home() / "Desktop" / "workflow_export.csv"
        export_dir.parent.mkdir(parents=True, exist_ok=True)

        connection = self.database.get_connection()
        rows = connection.execute(
            "SELECT id, title, status, owner, notes, created_at, updated_at FROM workflow_items ORDER BY id"
        ).fetchall()
        connection.close()

        with export_dir.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(["id", "title", "status", "owner", "notes", "created_at", "updated_at"])
            for row in rows:
                writer.writerow([
                    row["id"],
                    row["title"],
                    row["status"],
                    row["owner"],
                    row["notes"],
                    row["created_at"],
                    row["updated_at"],
                ])

        return export_dir
