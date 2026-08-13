"""
Database connection setup.

Reads DATABASE_URL from the environment and creates the SQLAlchemy engine
that the rest of the app will use to talk to Postgres. No models or tables
live here yet — this is just the wiring.
"""

import os

from dotenv import load_dotenv
from sqlmodel import Session, create_engine

# Reads backend/.env (if one exists) and copies its lines into the process's
# environment variables. On Render there's no .env file — the platform sets
# environment variables directly — so this line does nothing there and only
# matters when running locally.
load_dotenv()

DATABASE_URL = os.environ.get("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL is not set. Create backend/.env with a DATABASE_URL "
        "line pointing at your Neon database, or set the environment "
        "variable directly."
    )

# The engine manages the pool of connections to Postgres. Creating it doesn't
# open a connection yet — that happens lazily, the first time it's used.
engine = create_engine(DATABASE_URL)


def get_session():
    """FastAPI dependency that hands a route a database session.

    Routes will use this later like:
        def some_route(session: Session = Depends(get_session)):

    `yield` (instead of `return`) makes this a generator: FastAPI runs
    everything before the yield, hands the caller `session`, and only runs
    what's after the yield (nothing here, but closing happens via the `with`)
    once the request is done. That's what guarantees the session closes even
    if the route raises an exception.
    """
    with Session(engine) as session:
        yield session
