"""
Database models. Each SQLModel class with `table=True` becomes one table.
"""

from datetime import datetime, timezone
from typing import Optional

from pydantic import field_validator
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


class VideoGameCreate(SQLModel):
    """What a client sends to create a game. No table=True — this is a plain
    request schema, never a table.

    It exists because the table model can't do this job:
    - VideoGame has server-assigned fields (id, created_at) a client must
      not supply.
    - SQLModel skips validation on table=True models entirely; constraints
      like min_length only run on plain models like this one. Sending bad
      data gets an automatic 422 with per-field errors before our code runs.

    Length caps are arbitrary-but-sensible guards against garbage, not
    business rules. Allowed status/platform values stay unenforced here —
    app-level enums are planned separately (see DL-7 notes).
    """

    title: str = Field(min_length=1, max_length=200)
    platform: str = Field(min_length=1, max_length=50)
    status: str = Field(min_length=1, max_length=30)

    # A validator is a decorated class method Pydantic calls mid-parse.
    # This one strips whitespace BEFORE the min_length check runs
    # (mode="before"), so "   " counts as empty and gets rejected instead
    # of sneaking past as a 3-character title.
    @field_validator("title", "platform", "status", mode="before")
    @classmethod
    def strip_whitespace(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value
