"""
HTTP endpoints for video games. Moved verbatim from main.py (DL-22).

An APIRouter is a group of routes that can be defined away from the app and
mounted onto it later — main.py calls include_router(). Same decorators as
before, just on `router` instead of `app`.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from database import get_session
from security import require_write_secret
from video_games.models import VideoGame, VideoGameCreate, VideoGameUpdate

router = APIRouter()


@router.get("/api/games")
def list_games(session: Annotated[Session, Depends(get_session)]) -> list[VideoGame]:
    """All games in the library, unfiltered and unpaginated (fine at ~10 rows).

    Annotated[Session, Depends(get_session)] is FastAPI's dependency
    injection: the parameter IS a Session (that's what type checkers see);
    the Depends metadata tells FastAPI to call get_session() before this
    function and pass the result in, then close it after the response goes
    out. The route never manages connection lifecycle itself.
    """
    # .all() runs the SELECT and returns a list of VideoGame objects. FastAPI
    # then serializes them to JSON using the model's fields — the same class
    # is the table definition AND the response schema (the SQLModel payoff).
    return session.exec(select(VideoGame)).all()


# dependencies=[...] (vs a parameter) runs the guard without handing its
# return value to the route — we only care about the 401 it can raise.
@router.post("/api/games", status_code=201, dependencies=[Depends(require_write_secret)])
def create_game(
    data: VideoGameCreate,
    session: Annotated[Session, Depends(get_session)],
) -> VideoGame:
    """Add one game. 201 (Created) instead of the default 200.

    Because `data` is typed as a Pydantic model (not a dependency), FastAPI
    treats it as the JSON request body: parse it, validate it, 422 on
    failure — all before this function is called. By the time we're here,
    `data` is guaranteed clean.
    """
    # Copy the validated fields onto a fresh table-model instance. id and
    # created_at aren't on VideoGameCreate, so they fall back to their
    # defaults (None -> Postgres assigns; default_factory stamps the time).
    game = VideoGame.model_validate(data)

    session.add(game)
    session.commit()
    # commit() expires the in-memory object; refresh() re-reads the row so
    # the response includes the database-assigned id.
    session.refresh(game)
    return game


@router.patch(
    "/api/games/{game_id}", dependencies=[Depends(require_write_secret)]
)
def update_game(
    game_id: int,
    data: VideoGameUpdate,
    session: Annotated[Session, Depends(get_session)],
) -> VideoGame:
    """Partially update a game. PATCH, not PUT: send only what changes.

    `game_id` is declared in the path ("/api/games/{game_id}") and as a
    parameter, so FastAPI pulls it from the URL and converts it to int —
    a non-numeric id 422s before this runs.
    """
    # session.get() looks a row up by primary key, returning None when it
    # doesn't exist. Raising HTTPException is how a route reports a failure:
    # FastAPI turns it into a real HTTP response instead of a 500.
    game = session.get(VideoGame, game_id)
    if game is None:
        raise HTTPException(status_code=404, detail="Game not found")

    # exclude_unset is the heart of PATCH. It returns ONLY the fields the
    # client actually sent — so an omitted field is left alone, which is
    # different from a field explicitly sent as null. Without it, every
    # unsent field would come back as None and wipe the stored value.
    changes = data.model_dump(exclude_unset=True)
    for field, value in changes.items():
        # setattr(obj, "title", x) is obj.title = x with the name as a
        # variable — the standard way to assign a field you only know by name.
        setattr(game, field, value)

    session.add(game)
    session.commit()
    session.refresh(game)
    return game


@router.delete(
    "/api/games/{game_id}",
    status_code=204,
    dependencies=[Depends(require_write_secret)],
)
def delete_game(
    game_id: int,
    session: Annotated[Session, Depends(get_session)],
) -> None:
    """Remove a game. 204 No Content: success, and deliberately no body."""
    game = session.get(VideoGame, game_id)
    if game is None:
        raise HTTPException(status_code=404, detail="Game not found")

    session.delete(game)
    session.commit()
