# Workflow Desktop App

This is a starter desktop-app project for a Windows-only workflow management tool built with Python and PySide6.

## Features

- Login screen
- Dashboard
- Local SQLite database
- Basic workflow item management
- CSV export
- Ready for future Windows packaging with PyInstaller

## Quick start

1. Create a virtual environment:
   ```bash
   python -m venv .venv
   .venv\Scripts\activate
   ```
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Run the app:
   ```bash
   python main.py
   ```

## Build for Windows

From a Windows PowerShell terminal:

```powershell
cd "C:\Users\hp\OneDrive\Documents\GitHub\vercywoods\workflow_desktop_app"
./build_windows.ps1
```

Or from Command Prompt:

```cmd
cd /d "C:\Users\hp\OneDrive\Documents\GitHub\vercywoods\workflow_desktop_app"
build_windows.bat
```

This produces a single Windows executable in:

```text
workflow_desktop_app\dist\WorkflowDesktopApp.exe
```

## Project structure

```text
workflow_desktop_app/
├── app/
│   ├── db/
│   │   ├── database.py
│   │   └── schema.sql
│   ├── models/
│   │   ├── user.py
│   │   └── workflow_item.py
│   ├── services/
│   │   ├── auth_service.py
│   │   └── export_service.py
│   ├── ui/
│   │   ├── dashboard_window.py
│   │   └── login_window.py
│   ├── __init__.py
│   ├── config.py
│   ├── main.py
│   └── utils/
│       └── logger.py
├── .gitignore
├── main.py
├── README.md
├── requirements.txt
└── data/
```

## Notes

This starter is intentionally simple and production-minded without overspending on tooling. It is designed as a clean base for a real Windows desktop MVP.
