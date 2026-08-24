"""
Dexter's Library — API entry point.

Assembly only: this file wires the app together (middleware, startup,
routers) and defines nothing itself. Endpoints live in health.py and in
each feature package's routes.py.

Run it locally with:
    uvicorn main:app --reload

Then open http://127.0.0.1:8000/api/health in a browser.
"""

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import Session, text

import health
from database import engine
from video_games import igdb_routes
from video_games import routes as video_game_routes


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

# Mount each router's endpoints onto the app. Paths are defined in full on the
# routes themselves ("/api/games"), so no prefix is needed here.
app.include_router(health.router)
app.include_router(video_game_routes.router)
app.include_router(igdb_routes.router)
