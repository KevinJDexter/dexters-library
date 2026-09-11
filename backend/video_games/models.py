"""
Database models. Each SQLModel class with `table=True` becomes one table.
"""

from datetime import date, datetime, timezone
from enum import Enum
from typing import List, Optional

from pydantic import field_validator, model_validator
from sqlmodel import Field, Relationship, SQLModel


class CopyFormat(str, Enum):
    """How a copy is held. Inheriting from `str` as well as Enum means these
    compare equal to their plain strings and serialize to JSON as strings —
    so the database column stays a plain varchar while the API still validates.
    """

    PHYSICAL = "physical"
    DIGITAL = "digital"


class CopyAccess(str, Enum):
    """What keeps a copy playable.

    The question this answers is "does this vanish if I stop paying?" —
    Subscription does, Owned doesn't, Borrowed vanishes when it goes back.
    """

    OWNED = "owned"
    SUBSCRIPTION = "subscription"
    BORROWED = "borrowed"


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


class Platform(SQLModel, table=True):
    """Somewhere a game can be played: PS5, Steam, Wii Virtual Console, GOG.

    A table rather than an enum, by the project's own heuristic: adding a
    platform requires no code change anywhere, it's just another row in a
    dropdown. Status stays a plain string because adding one WOULD mean code
    changes — the UI treats Playing differently from Dropped.

    The foreign key from `copy` also makes "PS5" vs "Playstation 5" typos
    impossible, which a free-text column could never guarantee.
    """

    __tablename__ = "platform"

    id: Optional[int] = Field(default=None, primary_key=True)
    # unique so the same platform can't be entered twice under one spelling.
    name: str = Field(unique=True, index=True)

    copies: List["Copy"] = Relationship(back_populates="platform")


class Copy(SQLModel, table=True):
    """One way Dexter can play a game. Owning something on three platforms is
    three rows; owning it physically AND digitally is two.

    Ownership is derived from these rows, never stored as a flag: a game is
    in the library if it has at least one copy, and Watching if it has none.
    A boolean could disagree with reality; a row count can't.
    """

    __tablename__ = "copy"

    id: Optional[int] = Field(default=None, primary_key=True)

    # ondelete="CASCADE" pushes the cleanup into the database: deleting a game
    # removes its copies automatically. Without it, DELETE /api/games/{id}
    # would fail with a foreign-key violation the moment a game has copies.
    video_game_id: int = Field(
        foreign_key="video_game.id", index=True, ondelete="CASCADE"
    )

    # Deliberately NO ondelete here. Deleting a platform that copies still
    # point at should fail loudly rather than silently destroying them.
    platform_id: int = Field(foreign_key="platform.id", index=True)

    # Plain strings, validated by the enums above at the API boundary rather
    # than by a database constraint — same approach as `status`. A native
    # Postgres ENUM type would need an ALTER TYPE migration every time a value
    # is added, which is a lot of ceremony for a dropdown.
    #
    # format is nullable because it's genuinely unknown for rows migrated from
    # the old single-platform column: we knew the platform, never the medium.
    # Guessing would put data in the database that nobody should trust.
    format: Optional[str] = Field(default=None)
    access: str = Field(default=CopyAccess.OWNED.value)

    # A real column rather than free text, because "what do I still need to
    # give back" is a question worth being able to answer.
    borrowed_from: Optional[str] = Field(default=None)

    video_game: Optional["VideoGame"] = Relationship(back_populates="copies")
    platform: Optional[Platform] = Relationship(back_populates="copies")


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

    # Every way this game can be played. An empty list is meaningful: it means
    # "tracking but don't have it", which is what the Watching view shows.
    copies: List["Copy"] = Relationship(
        back_populates="video_game", cascade_delete=True
    )


class CopyCreate(SQLModel):
    """What a client sends to add a copy.

    format and access are typed as the enums rather than plain str, so an
    invalid value is a 422 with a list of what's allowed — Pydantic does that
    for free. The database columns stay varchar; this is validation at the
    boundary, not a constraint in the schema.
    """

    platform_id: int
    format: Optional[CopyFormat] = None
    access: CopyAccess = CopyAccess.OWNED
    borrowed_from: Optional[str] = Field(default=None, max_length=100)

    @field_validator("borrowed_from", mode="before")
    @classmethod
    def strip_whitespace(cls, value: object) -> object:
        if isinstance(value, str):
            stripped = value.strip()
            return stripped or None
        return value

    # A model_validator runs AFTER every field is parsed, so it can compare
    # fields against each other — a field_validator only ever sees one value.
    # That's the distinction: cross-field rules need this one.
    @model_validator(mode="after")
    def borrowed_from_requires_borrowed_access(self) -> "CopyCreate":
        if self.borrowed_from and self.access != CopyAccess.BORROWED:
            raise ValueError(
                "borrowed_from only applies when access is 'borrowed'."
            )
        return self


class CopyRead(SQLModel):
    """A copy as the API returns it.

    Carries platform_name alongside platform_id so a card can render its
    platform badges without a second request or a client-side join against
    /api/platforms.
    """

    id: int
    video_game_id: int
    platform_id: int
    platform_name: str
    format: Optional[str]
    access: str
    borrowed_from: Optional[str]


class PlatformCreate(SQLModel):
    """What a client sends to add a platform. The whole point of platform
    being a table is that a new console needs no code change — just a row."""

    name: str = Field(min_length=1, max_length=60)

    @field_validator("name", mode="before")
    @classmethod
    def strip_whitespace(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value


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
