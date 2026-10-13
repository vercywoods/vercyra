from dataclasses import dataclass


@dataclass
class WorkflowItem:
    id: int | None = None
    title: str = ""
    status: str = "Open"
    owner: str = "Unassigned"
    notes: str = ""
    created_at: str = ""
    updated_at: str = ""
