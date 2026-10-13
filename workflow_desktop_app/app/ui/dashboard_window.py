from __future__ import annotations

from datetime import datetime

from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.db.database import Database
from app.models.user import User
from app.services.export_service import ExportService


class WorkflowItemDialog(QDialog):
    def __init__(self, parent=None, item_data=None):
        super().__init__(parent)
        self.item_data = item_data or {}
        self.setWindowTitle("Workflow Item")
        self.resize(420, 320)

        self.title_input = QLineEdit(self.item_data.get("title", ""))
        self.status_input = QComboBox()
        self.status_input.addItems(["Open", "In Progress", "Review", "Completed"])
        if self.item_data.get("status"):
            self.status_input.setCurrentText(self.item_data["status"])

        self.owner_input = QLineEdit(self.item_data.get("owner", ""))
        self.notes_input = QTextEdit(self.item_data.get("notes", ""))

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Title"))
        layout.addWidget(self.title_input)
        layout.addWidget(QLabel("Status"))
        layout.addWidget(self.status_input)
        layout.addWidget(QLabel("Owner"))
        layout.addWidget(self.owner_input)
        layout.addWidget(QLabel("Notes"))
        layout.addWidget(self.notes_input)

        actions = QHBoxLayout()
        save_button = QPushButton("Save")
        save_button.clicked.connect(self.accept)
        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self.reject)
        actions.addWidget(save_button)
        actions.addWidget(cancel_button)
        layout.addLayout(actions)

    def get_values(self):
        title = self.title_input.text().strip()
        if not title:
            raise ValueError("Title is required.")

        return {
            "title": title,
            "status": self.status_input.currentText(),
            "owner": self.owner_input.text().strip() or "Unassigned",
            "notes": self.notes_input.toPlainText().strip(),
        }


class DashboardWindow(QMainWindow):
    def __init__(self, user: User):
        super().__init__()
        self.user = user
        self.database = Database()
        self.export_service = ExportService(self.database)

        self.setWindowTitle(f"Workflow Dashboard - {user.username}")
        self.resize(1100, 650)

        container = QWidget()
        main_layout = QVBoxLayout(container)

        button_row = QHBoxLayout()

        add_button = QPushButton("Add item")
        add_button.clicked.connect(self.add_item)
        button_row.addWidget(add_button)

        edit_button = QPushButton("Edit selected")
        edit_button.clicked.connect(self.edit_selected)
        button_row.addWidget(edit_button)

        delete_button = QPushButton("Delete selected")
        delete_button.clicked.connect(self.delete_selected)
        button_row.addWidget(delete_button)

        export_button = QPushButton("Export CSV")
        export_button.clicked.connect(self.export_csv)
        button_row.addWidget(export_button)

        main_layout.addLayout(button_row)

        filter_row = QHBoxLayout()
        filter_label = QLabel("Search:")
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Filter by title or owner")
        self.search_input.returnPressed.connect(self.apply_filters)

        self.status_filter = QComboBox()
        self.status_filter.addItems(["All statuses", "Open", "In Progress", "Review", "Completed"])

        apply_filter_button = QPushButton("Apply")
        apply_filter_button.clicked.connect(self.apply_filters)

        clear_filter_button = QPushButton("Clear")
        clear_filter_button.clicked.connect(self.clear_filters)

        filter_row.addWidget(filter_label)
        filter_row.addWidget(self.search_input)
        filter_row.addWidget(self.status_filter)
        filter_row.addWidget(apply_filter_button)
        filter_row.addWidget(clear_filter_button)
        main_layout.addLayout(filter_row)

        self.summary_label = QLabel("Showing 0 items")
        main_layout.addWidget(self.summary_label)

        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(["ID", "Title", "Status", "Owner", "Notes", "Updated"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.resizeColumnsToContents()
        main_layout.addWidget(self.table)

        self.setCentralWidget(container)
        self.load_items()

    def load_items(self):
        query = "SELECT id, title, status, owner, notes, updated_at FROM workflow_items"
        params = []
        conditions = []

        search_value = self.search_input.text().strip() if hasattr(self, "search_input") else ""
        status_value = self.status_filter.currentText() if hasattr(self, "status_filter") else "All statuses"

        if search_value:
            conditions.append("(title LIKE ? OR owner LIKE ?)")
            pattern = f"%{search_value}%"
            params.extend([pattern, pattern])

        if status_value and status_value != "All statuses":
            conditions.append("status = ?")
            params.append(status_value)

        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        query += " ORDER BY id DESC"

        connection = self.database.get_connection()
        rows = connection.execute(query, params).fetchall()
        connection.close()

        self.table.setRowCount(len(rows))
        for index, row in enumerate(rows):
            self.table.setItem(index, 0, QTableWidgetItem(str(row["id"])))
            self.table.setItem(index, 1, QTableWidgetItem(row["title"]))
            self.table.setItem(index, 2, QTableWidgetItem(row["status"]))
            self.table.setItem(index, 3, QTableWidgetItem(row["owner"]))
            self.table.setItem(index, 4, QTableWidgetItem(row["notes"] or ""))
            self.table.setItem(index, 5, QTableWidgetItem(str(row["updated_at"])))

        self.summary_label.setText(f"Showing {len(rows)} item(s)")

    def apply_filters(self):
        self.load_items()

    def clear_filters(self):
        self.search_input.clear()
        self.status_filter.setCurrentIndex(0)
        self.load_items()

    def add_item(self):
        dialog = WorkflowItemDialog(self)
        if dialog.exec() != QDialog.Accepted:
            return

        try:
            values = dialog.get_values()
        except ValueError as exc:
            QMessageBox.warning(self, "Validation error", str(exc))
            return

        values["created_at"] = datetime.utcnow().isoformat(timespec="seconds")
        values["updated_at"] = values["created_at"]

        connection = self.database.get_connection()
        try:
            connection.execute(
                "INSERT INTO workflow_items (title, status, owner, notes, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
                (
                    values["title"],
                    values["status"],
                    values["owner"],
                    values["notes"],
                    values["created_at"],
                    values["updated_at"],
                ),
            )
            connection.commit()
        finally:
            connection.close()

        self.load_items()

    def edit_selected(self):
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "No selection", "Please select a workflow item first.")
            return

        item_id = self.table.item(row, 0).text()
        connection = self.database.get_connection()
        row_data = connection.execute(
            "SELECT id, title, status, owner, notes FROM workflow_items WHERE id = ?",
            (int(item_id),),
        ).fetchone()
        connection.close()

        if row_data is None:
            return

        dialog = WorkflowItemDialog(self, {
            "title": row_data["title"],
            "status": row_data["status"],
            "owner": row_data["owner"],
            "notes": row_data["notes"],
        })
        if dialog.exec() != QDialog.Accepted:
            return

        try:
            values = dialog.get_values()
        except ValueError as exc:
            QMessageBox.warning(self, "Validation error", str(exc))
            return

        values["updated_at"] = datetime.utcnow().isoformat(timespec="seconds")

        connection = self.database.get_connection()
        try:
            connection.execute(
                "UPDATE workflow_items SET title = ?, status = ?, owner = ?, notes = ?, updated_at = ? WHERE id = ?",
                (
                    values["title"],
                    values["status"],
                    values["owner"],
                    values["notes"],
                    values["updated_at"],
                    int(item_id),
                ),
            )
            connection.commit()
        finally:
            connection.close()

        self.load_items()

    def delete_selected(self):
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "No selection", "Please select a workflow item first.")
            return

        item_id = self.table.item(row, 0).text()
        confirm = QMessageBox.question(
            self,
            "Delete item",
            f"Delete workflow item #{item_id}?",
        )
        if confirm != QMessageBox.Yes:
            return

        connection = self.database.get_connection()
        try:
            connection.execute("DELETE FROM workflow_items WHERE id = ?", (int(item_id),))
            connection.commit()
        finally:
            connection.close()

        self.load_items()

    def export_csv(self):
        export_path = self.export_service.export_workflow_items()
        QMessageBox.information(self, "Export complete", f"CSV exported to:\n{export_path}")
