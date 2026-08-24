"""
IGDB client: authentication and title search.

No database, no FastAPI, no endpoints — this module only fetches and parses.

Every HTTP call goes through an httpx.Client held on the instance, and that
client can be supplied from outside. That one choice is what lets the tests
run with no network at all: they hand in a client wired to a fake transport.
"""

import os
import time
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any, Optional, Tuple

import httpx
from dotenv import load_dotenv

load_dotenv()

CLIENT_ID = os.environ.get("IGDB_CLIENT_ID")
CLIENT_SECRET = os.environ.get("IGDB_CLIENT_SECRET")

# Same fail-loud policy as DATABASE_URL and WRITE_SECRET: missing config
# stops the process rather than surfacing later as a confusing 401.
if not CLIENT_ID or not CLIENT_SECRET:
    raise RuntimeError(
        "IGDB_CLIENT_ID and IGDB_CLIENT_SECRET must be set. Register a "
        "Twitch developer application at https://dev.twitch.tv/console/apps "
        "and put both values in backend/.env (and Render's dashboard)."
    )

TOKEN_URL = "https://id.twitch.tv/oauth2/token"
GAMES_URL = "https://api.igdb.com/v4/games"

# Treat the token as expired this many seconds early, so a request can't set
# off holding a token that dies while it's in flight.
TOKEN_EXPIRY_MARGIN_SECONDS = 60

DEFAULT_TIMEOUT_SECONDS = 10.0


class IgdbError(Exception):
    """Base class for every failure this module raises.

    Callers that don't care about the distinction can catch this one; DL-25
    will catch the subclasses to choose an HTTP status.
    """


class IgdbUnavailable(IgdbError):
    """Couldn't reach IGDB/Twitch, or they returned a server error.

    Retrying later might work. Nothing is wrong with our request.
    """


class IgdbAuthError(IgdbError):
    """Credentials were rejected. Retrying will not help — fix the config."""


@dataclass(frozen=True)
class IgdbGame:
    """One search result, parsed down to what we actually use.

    @dataclass writes __init__, __repr__ and __eq__ from the annotations
    below, so tests can compare whole objects with ==. frozen=True makes
    instances immutable, which is what you want for a parsed API response:
    nothing downstream should be quietly editing it.
    """

    igdb_id: int
    name: str
    release_year: Optional[int]
    cover_url: Optional[str]


@dataclass(frozen=True)
class IgdbTag:
    """One label from IGDB, flattened to (kind, name).

    IGDB returns genres, themes, game_modes, player_perspectives, franchises
    and collections as six separate lists of the same shape. They collapse
    to this one type because the `tag` table stores them all with a `kind`
    column rather than in six parallel tables.
    """

    kind: str
    name: str


@dataclass(frozen=True)
class IgdbGameDetail:
    """Everything we store about a game, fetched once a match is chosen.

    Separate from IgdbGame because search runs on every keystroke and this
    doesn't. Requesting all of these fields for ten search results would
    burn the rate limit for information nobody looked at.
    """

    igdb_id: int
    name: str
    summary: Optional[str]
    first_release_date: Optional[date]
    cover_image_id: Optional[str]
    esrb_rating: Optional[str]
    max_local_players: Optional[int]
    max_online_players: Optional[int]
    tags: Tuple[IgdbTag, ...]


# Which IGDB list maps to which tag kind. Adding another IGDB list later
# (keywords, say) is one line here plus one in the query.
TAG_SOURCES: Tuple[Tuple[str, str], ...] = (
    ("genres", "genre"),
    ("themes", "theme"),
    ("game_modes", "game_mode"),
    ("player_perspectives", "player_perspective"),
    ("franchises", "franchise"),
    ("collections", "collection"),
)


def _release_year(timestamp: Optional[int]) -> Optional[int]:
    if not timestamp:
        return None
    return datetime.fromtimestamp(timestamp, tz=timezone.utc).year


def _cover_url(cover: Optional[dict[str, Any]]) -> Optional[str]:
    url = cover.get("url") if cover else None
    if not url:
        return None
    # The cover url lacks the protocol (https:) and is a thumbnail size.
    # We replace the size with t_cover_big to get a larger image.
    url = url.replace("/t_thumb/", "/t_cover_big/")
    if url.startswith("//"):
        return f"https:{url}"
    return url


def _first_release_date(timestamp: Optional[int]) -> Optional[date]:
    """Full release date, where _release_year keeps only the year.

    Same Unix timestamp, same UTC requirement — a launch late on Dec 31 UTC
    lands in the previous year if converted in a westward local timezone.
    """
    if not timestamp:
        return None
    return datetime.fromtimestamp(timestamp, tz=timezone.utc).date()


def _cover_image_id(cover: Optional[dict[str, Any]]) -> Optional[str]:
    """The bare image id (e.g. "co6ple"), not a URL.

    We store the id so the frontend can build whatever size it needs at
    render time; storing IGDB's `url` would pin us to a thumbnail forever.
    """
    if not cover:
        return None
    return cover.get("image_id")


def _esrb_rating(age_ratings: Optional[list]) -> Optional[str]:
    """The ESRB value, out of the several boards IGDB returns.

    Each entry looks like:
        {"organization": {"name": "ESRB"},
         "rating_category": {"rating": "M"}}

    Everything else (PEGI, CERO, CLASS_IND...) is discarded. Returns None
    when there's no ESRB entry, which is normal for Japan-only and pre-1994
    titles.
    """
    for entry in age_ratings or []:
        organization = (entry.get("organization") or {}).get("name")
        if organization == "ESRB":
            rating = (entry.get("rating_category") or {}).get("rating")
            if rating:
                return rating
    return None


def _player_counts(
    multiplayer_modes: Optional[list],
) -> Tuple[Optional[int], Optional[int]]:
    """(max_local, max_online), collapsed from IGDB's per-platform entries.

    multiplayer_modes is a list with one entry PER PLATFORM, and the entries
    disagree — Baldur's Gate 3 reports offlinecoopmax 2 on one platform and 1
    on another. We take the max across every entry, because "can two people
    play this on the couch" is a property of the game, not of which console
    happens to be in the room.

    Returns (None, None) when the list is absent entirely, which is common —
    most single-player games have no multiplayer_modes at all.
    """
    local: list[int] = []
    online: list[int] = []

    for mode in multiplayer_modes or []:
        for key in ("offlinemax", "offlinecoopmax"):
            value = mode.get(key)
            if isinstance(value, int) and value > 0:
                local.append(value)
        for key in ("onlinemax", "onlinecoopmax"):
            value = mode.get(key)
            if isinstance(value, int) and value > 0:
                online.append(value)

    return (max(local) if local else None, max(online) if online else None)


def _tags(raw: dict[str, Any]) -> Tuple[IgdbTag, ...]:
    """Flatten IGDB's six name-lists into (kind, name) pairs.

    Order is preserved and duplicates are dropped, so a name appearing under
    two kinds stays as two tags while a repeat within one kind collapses.
    """
    seen: set = set()
    tags: list[IgdbTag] = []

    for field, kind in TAG_SOURCES:
        for entry in raw.get(field) or []:
            name = (entry or {}).get("name")
            if not name:
                continue
            key = (kind, name)
            if key in seen:
                continue
            seen.add(key)
            tags.append(IgdbTag(kind=kind, name=name))

    return tuple(tags)


def _parse_game_detail(raw: dict[str, Any]) -> IgdbGameDetail:
    """Map one fully-expanded IGDB record onto IgdbGameDetail."""
    local, online = _player_counts(raw.get("multiplayer_modes"))
    return IgdbGameDetail(
        igdb_id=raw["id"],
        name=raw.get("name", ""),
        summary=raw.get("summary"),
        first_release_date=_first_release_date(raw.get("first_release_date")),
        cover_image_id=_cover_image_id(raw.get("cover")),
        esrb_rating=_esrb_rating(raw.get("age_ratings")),
        max_local_players=local,
        max_online_players=online,
        tags=_tags(raw),
    )


def _parse_game(raw: dict[str, Any]) -> IgdbGame:
    if not raw:
        raise ValueError("Empty game record")
    return IgdbGame(
        igdb_id=raw["id"],
        name=raw.get("name", ""),
        release_year=_release_year(raw.get("first_release_date")),
        cover_url=_cover_url(raw.get("cover")),
    )


class IgdbClient:
    """Talks to IGDB, holding one cached access token.

    Meant to be long-lived — see get_client(). A fresh instance per request
    would re-authenticate every time and waste the cache entirely.
    """

    def __init__(
        self,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        http: Optional[httpx.Client] = None,
    ) -> None:
        self._client_id = client_id or CLIENT_ID
        self._client_secret = client_secret or CLIENT_SECRET
        # Accepting the http client is dependency injection, same idea as
        # get_session in the routes: production passes nothing and gets a
        # real one, tests pass a fake and no packet ever leaves the process.
        self._http = http or httpx.Client(timeout=DEFAULT_TIMEOUT_SECONDS)

        self._token: Optional[str] = None
        # monotonic() counts seconds from an arbitrary start and never jumps
        # backwards. time.time() can, if the system clock is corrected — and
        # a backwards jump would make an expired token look valid again.
        self._token_expires_at = 0.0

    # --- auth ------------------------------------------------------------

    def _fetch_token(self) -> str:
        """Twitch OAuth client-credentials grant.

        No user and no redirect: the app authenticates as itself. The token
        is good for weeks, which is exactly why caching it matters.
        """
        try:
            response = self._http.post(
                TOKEN_URL,
                params={
                    "client_id": self._client_id,
                    "client_secret": self._client_secret,
                    "grant_type": "client_credentials",
                },
            )
        except httpx.RequestError as exc:
            # RequestError covers DNS failures, refused connections and
            # timeouts — everything where no HTTP response came back at all.
            raise IgdbUnavailable(f"Could not reach Twitch: {exc}") from exc

        if response.status_code in (400, 401, 403):
            raise IgdbAuthError("IGDB credentials were rejected by Twitch.")
        if response.status_code >= 500:
            raise IgdbUnavailable(f"Twitch returned {response.status_code}.")
        if response.status_code >= 400:
            raise IgdbError(f"Unexpected token response: {response.status_code}")

        payload = response.json()
        self._token = payload["access_token"]
        self._token_expires_at = (
            time.monotonic() + payload["expires_in"] - TOKEN_EXPIRY_MARGIN_SECONDS
        )
        return self._token

    def _current_token(self) -> str:
        """The cached token, or a freshly fetched one if it's gone stale."""
        if self._token and time.monotonic() < self._token_expires_at:
            return self._token
        return self._fetch_token()

    # --- search ----------------------------------------------------------

    def search(self, title: str, limit: int = 10) -> list[IgdbGame]:
        """Search IGDB by title. Returns [] when nothing matches.

        No results is a normal outcome, not an error — an obscure import or
        a typo simply has no match, and the caller decides what to do.
        """
        title = title.strip()
        if not title:
            return []

        # A double quote in the title would terminate the search string and
        # corrupt the query, so escape it.
        safe_title = title.replace('"', '\\"')

        # Apicalypse: IGDB's own query language, sent as a plain-text POST
        # body — not JSON, not query params. Every clause ends in a
        # semicolon; dotted paths like cover.url expand a related record.
        # cover.url and cover.image_id are both requested: url is ready-made
        # but arrives protocol-relative and thumbnail-sized, image_id lets you
        # build any size from scratch. The parser picks one.
        query = (
            "fields name, first_release_date, cover.url, cover.image_id; "
            f'search "{safe_title}"; '
            f"limit {int(limit)};"
        )

        raw_results = self._post_query(query)
        return [_parse_game(item) for item in raw_results]

    # --- detail ----------------------------------------------------------

    def get_details(self, igdb_id: int) -> Optional[IgdbGameDetail]:
        """Everything we store about one game. None if IGDB has no such id.

        `where id = N` instead of `search`: this is a lookup, not a query, so
        it returns at most one record.
        """
        query = (
            "fields name, summary, first_release_date, cover.image_id, "
            "age_ratings.organization.name, age_ratings.rating_category.rating, "
            "multiplayer_modes.*, "
            "genres.name, themes.name, game_modes.name, "
            "player_perspectives.name, franchises.name, collections.name; "
            f"where id = {int(igdb_id)}; "
            "limit 1;"
        )

        results = self._post_query(query)
        if not results:
            return None
        return _parse_game_detail(results[0])

    def _post_query(self, query: str, allow_retry: bool = True) -> list[dict[str, Any]]:
        """POST an Apicalypse query, refreshing the token once on a 401."""
        try:
            response = self._http.post(
                GAMES_URL,
                headers={
                    "Client-ID": self._client_id or "",
                    "Authorization": f"Bearer {self._current_token()}",
                    "Accept": "application/json",
                },
                content=query,
            )
        except httpx.RequestError as exc:
            raise IgdbUnavailable(f"Could not reach IGDB: {exc}") from exc

        if response.status_code == 401 and allow_retry:
            # The token was rejected even though we thought it was valid —
            # revoked, or expired sooner than advertised. Drop it and try
            # exactly once more. allow_retry=False stops this recursing
            # forever when the credentials are genuinely bad.
            self._token = None
            return self._post_query(query, allow_retry=False)

        if response.status_code in (401, 403):
            raise IgdbAuthError("IGDB rejected the access token.")
        if response.status_code >= 500:
            raise IgdbUnavailable(f"IGDB returned {response.status_code}.")
        if response.status_code >= 400:
            raise IgdbError(f"IGDB rejected the query ({response.status_code}).")

        return response.json()


_default_client: Optional[IgdbClient] = None


def get_client() -> IgdbClient:
    """The shared client, created on first use.

    One instance means one cached token across all requests. Built lazily
    rather than at import time so merely importing this module doesn't open
    a connection pool — which also keeps test collection fast.

    `global` is needed because assigning to a module-level name inside a
    function would otherwise create a new local variable instead.
    """
    global _default_client
    if _default_client is None:
        _default_client = IgdbClient()
    return _default_client
