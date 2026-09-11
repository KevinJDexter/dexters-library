"""
HTTP endpoints for the ownership model: platforms and copies.

Split out from routes.py, which owns the games themselves. These two
resources arrived together and describe one idea — *how* a game can be
played, as opposed to what the game is.

The rule underneath all of it: ownership is derived from copy rows. There is
no `owned` flag to set, and nothing here toggles one. A game is in the
library because it has copies, and in Watching because it doesn't.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from database import get_session
from security import require_secret
from video_games.models import (
    Copy,
    CopyCreate,
    CopyRead,
    Platform,
    PlatformCreate,
    VideoGame,
)

router = APIRouter()


@router.get("/api/platforms")
def list_platforms(
    session: Annotated[Session, Depends(get_session)],
) -> list[Platform]:
    """Every platform, alphabetically. Unguarded, like GET /api/games — it's
    reference data with nothing sensitive in it, and the add/edit form needs
    it to populate a dropdown."""
    return session.exec(select(Platform).order_by(Platform.name)).all()


@router.post(
    "/api/platforms", status_code=201, dependencies=[Depends(require_secret)]
)
def create_platform(
    data: PlatformCreate,
    session: Annotated[Session, Depends(get_session)],
) -> Platform:
    """Add a platform. Exists so a console launching doesn't mean editing code.

    A duplicate name returns 409 rather than 500: the unique index is what
    keeps "PS5" from coexisting with a second "PS5", and a client hitting it
    has made a recoverable mistake, not triggered a server fault.
    """
    platform = Platform.model_validate(data)
    session.add(platform)

    try:
        session.commit()
    except IntegrityError as exc:
        # The database rejected the write. rollback() is required before the
        # session can be used again — without it every later statement in this
        # request fails with "transaction has been rolled back".
        session.rollback()
        raise HTTPException(
            status_code=409, detail=f"Platform {data.name!r} already exists."
        ) from exc

    session.refresh(platform)
    return platform


# --- copies ---------------------------------------------------------------


def _to_read(copy: Copy) -> CopyRead:
    """Flatten a Copy plus its platform into the API shape.

    copy.platform is a relationship, so touching .name issues a SELECT if it
    hasn't been loaded — fine at this scale, and it keeps the endpoints free
    of eager-loading machinery for a list that is almost always 1-3 rows.
    """
    return CopyRead(
        id=copy.id,
        video_game_id=copy.video_game_id,
        platform_id=copy.platform_id,
        platform_name=copy.platform.name,
        format=copy.format,
        access=copy.access,
        borrowed_from=copy.borrowed_from,
    )


def _get_game_or_404(session: Session, game_id: int) -> VideoGame:
    game = session.get(VideoGame, game_id)
    if game is None:
        raise HTTPException(status_code=404, detail="Game not found")
    return game


@router.get("/api/games/{game_id}/copies")
def list_copies(
    game_id: int,
    session: Annotated[Session, Depends(get_session)],
) -> list[CopyRead]:
    """Every way this game can be played. An empty list is meaningful, not an
    error: it means the game is tracked but not owned."""
    game = _get_game_or_404(session, game_id)
    return [_to_read(copy) for copy in game.copies]


@router.post(
    "/api/games/{game_id}/copies",
    status_code=201,
    dependencies=[Depends(require_secret)],
)
def add_copy(
    game_id: int,
    data: CopyCreate,
    session: Annotated[Session, Depends(get_session)],
) -> CopyRead:
    """Record a way of playing a game.

    Deliberately permits duplicates: owning a game physically AND digitally
    on the same platform is two rows, and there is no rule that says the
    combination has to be unique.
    """
    _get_game_or_404(session, game_id)

    # Checked explicitly so a bad platform_id is a 404 naming the problem,
    # rather than a foreign-key violation surfacing as a 500.
    if session.get(Platform, data.platform_id) is None:
        raise HTTPException(
            status_code=404, detail=f"No platform with id {data.platform_id}."
        )

    copy = Copy(
        video_game_id=game_id,
        platform_id=data.platform_id,
        # .value because the column is a plain string; the enum exists to
        # validate the request, not to define the storage type.
        format=data.format.value if data.format else None,
        access=data.access.value,
        borrowed_from=data.borrowed_from,
    )
    session.add(copy)
    session.commit()
    session.refresh(copy)
    return _to_read(copy)


@router.delete(
    "/api/copies/{copy_id}", status_code=204, dependencies=[Depends(require_secret)]
)
def delete_copy(
    copy_id: int,
    session: Annotated[Session, Depends(get_session)],
) -> None:
    """Remove one way of playing a game.

    Top-level path rather than nested under the game: a copy id is unique on
    its own, so requiring the game id too would add a value the caller has to
    look up and that the server would only have to verify.

    Deleting the last copy is allowed and meaningful — the game moves from
    Library to Watching. Nothing needs to be toggled for that to happen.
    """
    copy = session.get(Copy, copy_id)
    if copy is None:
        raise HTTPException(status_code=404, detail="Copy not found")

    session.delete(copy)
    session.commit()
