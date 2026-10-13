from dataclasses import dataclass


@dataclass
class User:
    id: int | None = None
    username: str = ""
    email: str | None = None
