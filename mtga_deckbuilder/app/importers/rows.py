from dataclasses import dataclass


@dataclass
class ImportRow:
    name: str
    quantity: int = 1
    set_code: str = ""
    collector_number: str = ""
    arena_id: int | None = None
    section: str = "deck"  # deck / sideboard / commander / companion
    line_no: int = 0
    raw: str = ""
