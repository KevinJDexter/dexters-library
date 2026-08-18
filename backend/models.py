"""
Database models. Each SQLModel class with `table=True` becomes one table.
"""

from datetime import datetime, timezone
from typing import Optional

from sqlmodel import Field, SQLModel


class VideoGame(SQLModel, table=True):
    """One video game in the library. Board games get their own model later.

    Without __tablename__, SQLModel would name the table `videogame` (just
    the class name lowercased) — setting it explicitly gets the underscore.
    """

    __tablename__ = "video_game"

    # Optional[int] = "int or None". It's None before the row is saved;
    # Postgres assigns the real id on INSERT because this is the primary key.
    id: Optional[int] = Field(default=None, primary_key=True)

    # A bare annotation like `title: str` becomes a NOT NULL text column.
    # No Field() needed unless we're overriding something.
    title: str

    # Plain strings by design — validation of allowed values will live in
    # app code (Python/TS enums), not as database constraints.
    platform: str
    status: str

    # default_factory takes a function to call per-row at insert time.
    # A plain `default=datetime.now(...)` would run ONCE at import and stamp
    # every row with the same moment — same footgun as JS default params
    # evaluated at definition time, and a classic Python gotcha.
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
