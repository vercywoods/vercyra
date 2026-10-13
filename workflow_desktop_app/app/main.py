from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication, QDialog

from app.db.database import init_database
from app.services.auth_service import create_default_user
from app.ui.dashboard_window import DashboardWindow
from app.ui.login_window import LoginWindow


def main() -> None:
    init_database()
    create_default_user()

    app = QApplication(sys.argv)
    login_window = LoginWindow()

    if login_window.exec() != QDialog.Accepted:
        sys.exit(0)

    dashboard = DashboardWindow(login_window.user)
    dashboard.show()
    sys.exit(app.exec())
