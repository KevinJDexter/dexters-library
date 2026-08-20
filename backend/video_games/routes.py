"""
HTTP endpoints for video games. Moved verbatim from main.py (DL-22).

An APIRouter is a group of routes that can be defined away from the app and
mounted onto it later — main.py calls include_router(). Same decorators as
before, just on `router` instead of `app`.
"""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from database import get_session
from security import require_write_secret
from video_games.models import VideoGame, VideoGameCreate

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
