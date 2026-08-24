"""
Database models. Each SQLModel class with `table=True` becomes one table.
"""

from datetime import date, datetime, timezone
from typing import List, Optional

from pydantic import field_validator
from sqlmodel import Field, Relationship, SQLModel


class VideoGameTagLink(SQLModel, table=True):
    """Join table for the many-to-many between video_game and tag.

    Nothing but two foreign keys. Both are marked primary_key, which makes
    the PAIR the primary key — so the same tag can't be attached to the same
    game twice, enforced by the database rather than by our code.
    """

    __tablename__ = "video_game_tag"

    video_game_id: Optional[int] = Field(
        default=None, foreign_key="video_game.id", primary_key=True
    )
    tag_id: Optional[int] = Field(
        default=None, foreign_key="tag.id", primary_key=True
    )


class Tag(SQLModel, table=True):
    """One label of some kind, attachable to games.

    Deliberately ONE table rather than six near-identical ones. `kind`
    distinguishes genre from theme from game_mode etc. IGDB's genres, themes,
    game_modes, player_perspectives, franchises and collections are all the
    same shape — [{id, name}] — so six tables plus six join tables would be
    twelve structures doing one job. Adding keywords later costs nothing.

    Rows are ordinary data once created: rename one, merge two, or add a
    genre IGDB has never heard of. The taxonomy is Dexter's; IGDB names are
    just inputs to it.
    """

    __tablename__ = "tag"

    id: Optional[int] = Field(default=None, primary_key=True)

    # "genre" | "theme" | "game_mode" | "player_perspective" | "franchise"
    # | "collection". A plain string, not an enum — same reasoning as status
    # and platform: adding a kind shouldn't require a schema change.
    kind: str = Field(index=True)

    name: str

    # `games` is not a column. Relationship tells SQLModel how to fetch the
    # related rows through the link table; it's a Python-side convenience,
    # and Alembic generates nothing for it.
    games: List["VideoGame"] = Relationship(
        back_populates="tags", link_model=VideoGameTagLink
    )


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

    # --- IGDB metadata (DL-24) ---------------------------------------------
    # Every one of these is nullable and manually editable. IGDB is a source,
    # not a system of record: nothing here may be populate-only-by-API, or the
    # field breaks the day IGDB is down or has never heard of the game.

    # Which IGDB record this came from. Not unique: today one row means "a
    # game on a platform", so owning a game on three platforms is three rows
    # sharing an igdb_id. DL-20's copy table is what changes that.
    igdb_id: Optional[int] = Field(default=None)

    # The image id (e.g. "co6ple"), NOT a URL. IGDB's url field points at a
    # thumbnail; storing the id lets the frontend build any size it wants at
    # render time by swapping the token: t_cover_big, t_720p, t_1080p.
    cover_image_id: Optional[str] = Field(default=None)

    # Displayable ESRB value: "E", "E10+", "T", "M", "AO", "RP". Null for
    # Japan-only or pre-1994 titles with no ESRB entry.
    esrb_rating: Optional[str] = Field(default=None)

    summary: Optional[str] = Field(default=None)

    # A date, not a datetime — IGDB sends a Unix timestamp but the time of
    # day is meaningless here. Used for ordering within a collection.
    first_release_date: Optional[date] = Field(default=None)

    # Collapsed from IGDB's per-platform multiplayer_modes array by taking
    # the max across every entry. Approximate on purpose: the question is
    # "can I play this on the couch / with someone remote", which tolerates it.
    max_local_players: Optional[int] = Field(default=None)
    max_online_players: Optional[int] = Field(default=None)

    # The other half of Tag.games. back_populates on both sides is what keeps
    # them in sync: appending to one updates the other in the same session.
    # Not a column, and not part of the JSON this model serializes to —
    # relationships are excluded from the API response unless a response
    # model explicitly asks for them.
    tags: List["Tag"] = Relationship(
        back_populates="games", link_model=VideoGameTagLink
    )


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

    # Optional: when supplied, the server fetches that IGDB record and fills
    # the metadata columns from it. Omitted for manual entry and CSV import,
    # both of which must keep working with no IGDB involvement at all.
    igdb_id: Optional[int] = Field(default=None)

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


class VideoGameUpdate(SQLModel):
    """What a client sends to edit a game (PATCH). Every field is optional:
    sending only {"status": "beaten"} is a valid request.

    Same constraints as VideoGameCreate, so a field that IS sent still can't
    be blank or absurdly long. The difference is only which fields are
    required — none of them.
    """

    title: Optional[str] = Field(default=None, min_length=1, max_length=200)
    platform: Optional[str] = Field(default=None, min_length=1, max_length=50)
    status: Optional[str] = Field(default=None, min_length=1, max_length=30)

    @field_validator("title", "platform", "status", mode="before")
    @classmethod
    def strip_whitespace(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value
