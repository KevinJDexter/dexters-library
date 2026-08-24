"""
HTTP endpoints for searching IGDB.

Its own router rather than joining video_games/routes.py: that file owns the
library's CRUD, this one is a read-only passthrough to somebody else's API.
Different resource path, different failure modes, different reasons to change.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from security import require_secret
from video_games.igdb import (
    IgdbAuthError,
    IgdbClient,
    IgdbError,
    IgdbGame,
    IgdbUnavailable,
    get_client,
)

router = APIRouter()


# Guarded even though it only reads. The reasoning differs from the write
# endpoints: this one spends a finite external resource (IGDB allows 4
# requests/second for the whole app), so leaving it open would let anyone
# who finds the URL exhaust the budget. Contrast /api/games/export, which
# is unguarded because it exposes data GET /api/games already serves.
@router.get("/api/igdb/search", dependencies=[Depends(require_secret)])
def search_igdb(
    title: Annotated[str, Query(min_length=1, max_length=200)],
    client: Annotated[IgdbClient, Depends(get_client)],
    limit: Annotated[int, Query(ge=1, le=25)] = 10,
) -> list[IgdbGame]:
    """Candidate IGDB matches for a title.

    Returns only what's needed to tell two results apart — IGDB catalogs
    ports and remasters separately, so "Final Fantasy VI" comes back several
    times differing only by year and cover. Full detail for the chosen one
    is fetched later, on selection.

    Taking the client via Depends rather than calling get_client() inline is
    what makes this testable: tests override the dependency with a fake and
    never touch the network.
    """
    try:
        return client.search(title, limit=limit)
    except IgdbUnavailable as exc:
        # 503: their end is down or unreachable. Retrying later may work,
        # and the frontend can say so honestly.
        raise HTTPException(
            status_code=503,
            detail="IGDB is unreachable right now. Try again shortly, or enter the game manually.",
        ) from exc
    except IgdbAuthError as exc:
        # 502: the upstream rejected us. Nothing the caller did wrong and
        # nothing they can fix — it's our credentials.
        raise HTTPException(
            status_code=502,
            detail="IGDB rejected our credentials. Check IGDB_CLIENT_ID and IGDB_CLIENT_SECRET.",
        ) from exc
    except IgdbError as exc:
        raise HTTPException(
            status_code=502, detail=f"IGDB request failed: {exc}"
        ) from exc
