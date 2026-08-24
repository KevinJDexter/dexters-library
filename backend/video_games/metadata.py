"""
Applying IGDB metadata onto a game.

One rule governs everything here: **fill blanks, never overwrite**. A value
already on the record is Dexter's, whatever IGDB says about it. Without that,
every re-sync silently undoes curation — and silently is the problem, because
nobody notices until the taxonomy they built is gone.
"""

from typing import Sequence

from sqlmodel import Session, select

from video_games.igdb import IgdbGameDetail, IgdbTag
from video_games.models import Tag, VideoGame

# Scalar columns IGDB can supply, mapped to the attribute on IgdbGameDetail
# holding the incoming value. Adding a column later is one line.
_SCALAR_FIELDS: tuple[tuple[str, str], ...] = (
    ("summary", "summary"),
    ("first_release_date", "first_release_date"),
    ("cover_image_id", "cover_image_id"),
    ("esrb_rating", "esrb_rating"),
    ("max_local_players", "max_local_players"),
    ("max_online_players", "max_online_players"),
)


def get_or_create_tags(session: Session, incoming: Sequence[IgdbTag]) -> list[Tag]:
    """Turn IGDB's (kind, name) pairs into Tag rows, reusing existing ones.

    Matching is on kind AND name together: "Action" as a genre and "Action"
    as a theme are different tags, and IGDB returns both.

    Reuse is what makes the taxonomy Dexter's rather than IGDB's. Once a row
    exists it's ordinary data — renaming "Role-playing (RPG)" to "RPG" keeps
    every game attached to it, and the next import matching that IGDB name
    will simply... not match, and create a fresh row. That's the accepted
    cost of curation; merging is a manual step by design.
    """
    tags: list[Tag] = []

    for item in incoming:
        existing = session.exec(
            select(Tag).where(Tag.kind == item.kind, Tag.name == item.name)
        ).first()

        if existing is None:
            existing = Tag(kind=item.kind, name=item.name)
            session.add(existing)
            # flush sends the INSERT so the row gets its id and is findable by
            # the query above on the next loop iteration — without it, a
            # detail listing the same tag twice would create two rows.
            session.flush()

        tags.append(existing)

    return tags


def apply_igdb_detail(
    session: Session, game: VideoGame, detail: IgdbGameDetail
) -> VideoGame:
    """Fill this game's empty fields from an IGDB record. Never overwrites.

    Returns the same game object, modified in place. Does not commit — the
    caller owns the transaction, so a failure later rolls this back too.
    """
    # igdb_id is the exception to fill-blanks in spirit but not in rule: it
    # still only fills when empty. Re-pointing a game at a different IGDB
    # record is a deliberate act, not something a re-sync should do quietly.
    if game.igdb_id is None:
        game.igdb_id = detail.igdb_id

    for column, source in _SCALAR_FIELDS:
        # getattr/setattr because the field names are data here, not code.
        # `is None` rather than falsiness on purpose: 0 players and an empty
        # summary are values someone chose, and must not be treated as blank.
        if getattr(game, column) is None:
            setattr(game, column, getattr(detail, source))

    # Tags are additive. Existing attachments are never removed — if Dexter
    # tagged something Musou and IGDB says Action, the game ends up with both
    # rather than IGDB winning.
    existing_pairs = {(tag.kind, tag.name) for tag in game.tags}
    for tag in get_or_create_tags(session, detail.tags):
        if (tag.kind, tag.name) not in existing_pairs:
            game.tags.append(tag)
            existing_pairs.add((tag.kind, tag.name))

    session.add(game)
    return game
