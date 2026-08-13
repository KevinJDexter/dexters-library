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

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import Session, text

from database import engine


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


@app.get("/api/health")
def health() -> dict[str, str]:
    """Confirms the API is alive. The frontend calls this on page load."""
    return {"status": "ok", "message": "Hello from Python"}
