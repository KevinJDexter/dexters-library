"""
HTTP endpoints for video games. Moved verbatim from main.py (DL-22).

An APIRouter is a group of routes that can be defined away from the app and
mounted onto it later — main.py calls include_router(). Same decorators as
before, just on `router` instead of `app`.
"""

import csv
import io
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import ValidationError
from sqlmodel import Session, select

from database import get_session
from security import require_write_secret
from video_games.models import VideoGame, VideoGameCreate, VideoGameUpdate

router = APIRouter()

# The CSV column order for both export and import. One tuple drives the
# export header, the export rows, and the import's required-column check, so
# the two halves can't drift apart.
CSV_COLUMNS = ("title", "platform", "status")


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


# NOTE: this must stay ABOVE any "/api/games/{game_id}" GET route. FastAPI
# matches in registration order, so a later {game_id} route defined first
# would swallow "export" and fail trying to read it as an int.
@router.get("/api/games/export", dependencies=[Depends(require_write_secret)])
def export_games(session: Annotated[Session, Depends(get_session)]) -> StreamingResponse:
    """The whole library as a CSV download.

    Deliberately exports only the columns import accepts, so a file that
    comes out of here can go straight back in. id and created_at are left
    out because they're server-assigned — see the ticket's note that CSV is
    not the backup (that's pg_dump).
    """
    games = session.exec(select(VideoGame).order_by(VideoGame.title)).all()

    # StringIO is an in-memory text file: same read/write API as a real file,
    # no disk involved. The csv module wants something file-like to write to.
    buffer = io.StringIO()
    # DictWriter maps dict keys to columns, so row order can never drift from
    # header order — safer than writing bare lists.
    writer = csv.DictWriter(buffer, fieldnames=CSV_COLUMNS)
    writer.writeheader()
    for game in games:
        writer.writerow({column: getattr(game, column) for column in CSV_COLUMNS})

    # Rewind to the start, or the response streams from the end and sends
    # nothing — the classic in-memory-file mistake.
    buffer.seek(0)

    return StreamingResponse(
        buffer,
        media_type="text/csv",
        # Content-Disposition: attachment is what makes a browser download
        # the response instead of displaying it, and names the saved file.
        headers={"Content-Disposition": 'attachment; filename="dexters-library.csv"'},
    )


@router.post("/api/games/import", dependencies=[Depends(require_write_secret)])
async def import_games(
    file: Annotated[UploadFile, File()],
    session: Annotated[Session, Depends(get_session)],
) -> dict[str, int]:
    """Bulk-insert games from an uploaded CSV.

    All-or-nothing: if ANY row is invalid, nothing is inserted and every
    problem is reported at once. Partial inserts would be a trap here —
    there's no duplicate detection, so fixing the file and re-uploading
    would insert the good rows a second time.

    `async def` (unlike our other endpoints) because UploadFile.read() is
    awaitable — FastAPI streams uploads rather than blocking on them.
    """
    raw = await file.read()
    try:
        # utf-8-sig strips the byte-order mark Excel writes at the start of
        # its CSVs. Without it the first header becomes "﻿title" and
        # the column check below fails for a completely invisible reason.
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise HTTPException(status_code=422, detail="File must be UTF-8 text.")

    reader = csv.DictReader(io.StringIO(text))

    missing = [c for c in CSV_COLUMNS if c not in (reader.fieldnames or [])]
    if missing:
        raise HTTPException(
            status_code=422,
            detail=f"Missing required column(s): {', '.join(missing)}",
        )

    games: list[VideoGame] = []
    errors: list[dict[str, object]] = []

    # start=2 because row 1 is the header, so these numbers match what the
    # user sees in a spreadsheet.
    for line_number, row in enumerate(reader, start=2):
        try:
            # Reusing VideoGameCreate means CSV rows get exactly the same
            # validation as POSTed JSON — blank titles, length caps, and
            # whitespace stripping all come along for free.
            data = VideoGameCreate(**{c: (row.get(c) or "") for c in CSV_COLUMNS})
        except ValidationError as exc:
            # .errors() is a list of structured dicts, one per failed field,
            # rather than one blob of text — which is what makes row-level
            # reporting possible.
            for error in exc.errors():
                errors.append(
                    {
                        "row": line_number,
                        "field": error["loc"][0] if error["loc"] else "?",
                        "message": error["msg"],
                    }
                )
            continue
        games.append(VideoGame.model_validate(data))

    if errors:
        raise HTTPException(status_code=422, detail={"errors": errors})

    if not games:
        raise HTTPException(status_code=422, detail="No data rows found.")

    session.add_all(games)
    session.commit()
    return {"imported": len(games)}


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
