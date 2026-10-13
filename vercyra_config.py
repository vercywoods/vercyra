import os
from pathlib import Path

from dotenv import dotenv_values


def local_config_path():
    local_app_data = Path(
        os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")
    )
    return local_app_data / "Vercyra" / ".env"


def load_environment(project_path=None, local_path=None):
    """Load local secrets first, without overriding explicit process variables."""
    project_path = Path(project_path or Path(__file__).with_name(".env"))
    local_path = Path(local_path or local_config_path())
    values = {}

    for config_path in (project_path, local_path):
        if config_path.is_file():
            values.update(
                (key, value)
                for key, value in dotenv_values(config_path).items()
                if value is not None and value.strip()
            )

    for key, value in values.items():
        os.environ.setdefault(key, value)

    return local_path