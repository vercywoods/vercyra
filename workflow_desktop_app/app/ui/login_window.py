from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.services.auth_service import AuthService


class LoginWindow(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Workflow Desktop App - Login")
        self.resize(420, 220)
        self.auth_service = AuthService()
        self.user = None

        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("Username")

        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("Password")
        self.password_input.setEchoMode(QLineEdit.Password)

        login_button = QPushButton("Login")
        login_button.clicked.connect(self.handle_login)

        create_button = QPushButton("Create account")
        create_button.clicked.connect(self.handle_create_account)

        form_layout = QFormLayout()
        form_layout.addRow("Username", self.username_input)
        form_layout.addRow("Password", self.password_input)

        action_row = QHBoxLayout()
        action_row.addWidget(login_button)
        action_row.addWidget(create_button)

        container = QWidget()
        container_layout = QVBoxLayout(container)
        container_layout.addLayout(form_layout)
        container_layout.addLayout(action_row)

        label = QLabel("Use admin/admin123 to sign in by default.")
        label.setStyleSheet("color: #666; margin-top: 8px;")
        container_layout.addWidget(label)

        self.setLayout(QVBoxLayout())
        self.layout().addWidget(container)

    def handle_login(self):
        username = self.username_input.text().strip()
        password = self.password_input.text()
        user = self.auth_service.authenticate(username, password)

        if user is None:
            QMessageBox.warning(self, "Login failed", "Invalid username or password.")
            return

        self.user = user
        self.accept()

    def handle_create_account(self):
        username = self.username_input.text().strip()
        password = self.password_input.text()

        if not username or not password:
            QMessageBox.warning(self, "Missing details", "Username and password are required.")
            return

        user = self.auth_service.register_user(username, password)
        if user is None:
            QMessageBox.warning(self, "Unable to create account", "That username already exists.")
            return

        self.user = user
        QMessageBox.information(self, "Account created", f"User '{username}' created successfully.")
        self.accept()
