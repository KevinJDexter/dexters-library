"""
Dexter's Library — API entry point.

This is the whole backend right now: one endpoint that says hello.
The point is to prove the plumbing works end to end before we build features.

Run it locally with:
    uvicorn main:app --reload

Then open http://127.0.0.1:8000/api/health in a browser.
"""

import os
from contextlib import asynccontextmanager

from typing import Annotated

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import Session, SQLModel, select, text

from database import engine, get_session
from models import VideoGame, VideoGameCreate
from security import require_write_secret


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Runs once when the server starts, before it accepts any requests.
    # `SELECT 1` is a trivial query that succeeds only if the database is
    # reachable and the credentials are good — a quick real connection test.
    try:
        with Session(engine) as session:
            session.exec(text("SELECT 1"))
        print("Database connection: OK")
    except Exception as exc:
        print(f"Database connection: FAILED — {exc}")
        raise
    # Creates every table registered on SQLModel.metadata that doesn't already
    # exist. Existing tables are left alone — even if the model has changed,
    # which is why a column change means drop-and-reseed (see backend/CLAUDE.md).
    SQLModel.metadata.create_all(engine)
    print("Tables created (if missing).")
    yield
    # Nothing to clean up on shutdown yet.


# `app` is the application object. Uvicorn looks for this exact variable when you
# run `uvicorn main:app` — "main" is this file, "app" is this name.
app = FastAPI(title="Dexter's Library API", lifespan=lifespan)


# Which websites are allowed to call this API. Without this, your browser refuses to
# let the frontend talk to the backend, because they're on different addresses and it
# treats that as a different site.
#
# `os.environ.get(name, default)` reads an environment variable, falling back to the
# default when it isn't set. So: locally nothing is set and we get the dev servers;
# on Render we'll set ALLOWED_ORIGINS to the deployed frontend's URL. Same code,
# different behaviour per environment, and no URLs baked into git.
ALLOWED_ORIGINS = os.environ.get(
    "ALLOWED_ORIGINS",
    "http://localhost:4200,http://127.0.0.1:4200",
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict[str, str]:
    """Confirms the API is alive and can reach the database."""
    try:
        with Session(engine) as session:
            session.exec(text("SELECT 1"))
        database_status = "ok"
        message = "Hello from Python and Postgres"
    except Exception:
        database_status = "unreachable"
        message = "Hello from Python"

    return {
        "status": "ok",
        "message": message,
        "database": database_status,
    }


@app.get("/api/games")
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
@app.post("/api/games", status_code=201, dependencies=[Depends(require_write_secret)])
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
