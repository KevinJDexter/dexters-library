"""
Tests for the IGDB client. Nothing here touches the network.

httpx.MockTransport takes a plain function and calls it instead of opening a
socket, so we hand IgdbClient an httpx.Client wired to one. Every request the
client makes lands in our handler and we decide what comes back — including
failures that would be impossible to trigger against the real service.
"""

from datetime import date

import httpx
import pytest

from video_games.igdb import (
    IgdbAuthError,
    IgdbClient,
    IgdbError,
    IgdbGame,
    IgdbGameDetail,
    IgdbTag,
    IgdbUnavailable,
    _cover_image_id,
    _cover_url,
    _esrb_rating,
    _first_release_date,
    _player_counts,
    _release_year,
    _tags,
)

TOKEN_BODY = {"access_token": "fake-token-1", "expires_in": 5_000_000}

# 1994-03-24 UTC.
FF6_TIMESTAMP = 764467200

FF6_RAW = {
    "id": 1234,
    "name": "Final Fantasy VI",
    "first_release_date": FF6_TIMESTAMP,
    "cover": {"url": "//images.igdb.com/igdb/image/upload/t_thumb/abc123.jpg"},
}


def make_client(handler) -> IgdbClient:
    """An IgdbClient whose HTTP goes to `handler` instead of the internet."""
    return IgdbClient(
        client_id="test-id",
        client_secret="test-secret",
        http=httpx.Client(transport=httpx.MockTransport(handler)),
    )


def is_token_request(request: httpx.Request) -> bool:
    return "oauth2/token" in str(request.url)


# --- parsing helpers ------------------------------------------------------


def test_release_year_converts_unix_timestamp() -> None:
    assert _release_year(FF6_TIMESTAMP) == 1994


def test_release_year_handles_missing_date() -> None:
    # IGDB omits the field entirely for unreleased or incomplete entries.
    assert _release_year(None) is None


def test_cover_url_adds_scheme_and_upgrades_size() -> None:
    cover = {"url": "//images.igdb.com/igdb/image/upload/t_thumb/abc123.jpg"}

    assert _cover_url(cover) == (
        "https://images.igdb.com/igdb/image/upload/t_cover_big/abc123.jpg"
    )


def test_cover_url_handles_missing_cover() -> None:
    assert _cover_url(None) is None
    assert _cover_url({}) is None
    # A populated cover object that simply has no url. This one is easy to
    # miss: {} is falsy so it short-circuits, but this dict is truthy and
    # reaches the code that assumes a string.
    assert _cover_url({"id": 313106, "image_id": "co6ple"}) is None


def test_cover_url_leaves_an_unexpected_size_segment_alone() -> None:
    """Only the scheme is added when there's no t_thumb to swap."""
    assert (
        _cover_url({"url": "//images.igdb.com/igdb/image/upload/t_1080p/abc.jpg"})
        == "https://images.igdb.com/igdb/image/upload/t_1080p/abc.jpg"
    )


# --- search ---------------------------------------------------------------


def test_search_returns_parsed_games() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if is_token_request(request):
            return httpx.Response(200, json=TOKEN_BODY)
        return httpx.Response(200, json=[FF6_RAW])

    results = make_client(handler).search("final fantasy vi")

    # Comparing whole objects works because IgdbGame is a dataclass, which
    # generates __eq__ from the fields.
    assert results == [
        IgdbGame(
            igdb_id=1234,
            name="Final Fantasy VI",
            release_year=1994,
            cover_url=(
                "https://images.igdb.com/igdb/image/upload/t_cover_big/abc123.jpg"
            ),
        )
    ]


def test_search_sends_apicalypse_query_and_auth_headers() -> None:
    """The request itself is the contract — assert on what we send, not just
    on what we do with the reply."""
    sent: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(request)
        if is_token_request(request):
            return httpx.Response(200, json=TOKEN_BODY)
        return httpx.Response(200, json=[])

    make_client(handler).search("final fantasy vi", limit=5)

    search_request = sent[-1]
    body = search_request.content.decode()

    assert 'search "final fantasy vi";' in body
    assert "limit 5;" in body
    assert "fields name, first_release_date, cover.url, cover.image_id;" in body
    assert search_request.headers["Client-ID"] == "test-id"
    assert search_request.headers["Authorization"] == "Bearer fake-token-1"


def test_search_escapes_quotes_in_title() -> None:
    """An unescaped double quote would close the search string early and
    corrupt the rest of the query."""
    sent: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(request)
        if is_token_request(request):
            return httpx.Response(200, json=TOKEN_BODY)
        return httpx.Response(200, json=[])

    make_client(handler).search('say "hello"')

    assert r'search "say \"hello\"";' in sent[-1].content.decode()


def test_search_with_no_matches_returns_empty_list() -> None:
    """No results is a normal outcome, not an error."""

    def handler(request: httpx.Request) -> httpx.Response:
        if is_token_request(request):
            return httpx.Response(200, json=TOKEN_BODY)
        return httpx.Response(200, json=[])

    assert make_client(handler).search("zzzzz nonexistent") == []


def test_blank_title_makes_no_http_call_at_all() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("should not have made a request")

    assert make_client(handler).search("   ") == []


def test_game_without_cover_or_date_parses() -> None:
    """IGDB omits fields it has no data for rather than sending null."""

    def handler(request: httpx.Request) -> httpx.Response:
        if is_token_request(request):
            return httpx.Response(200, json=TOKEN_BODY)
        return httpx.Response(200, json=[{"id": 7, "name": "Obscure Import"}])

    results = make_client(handler).search("obscure")

    assert results == [
        IgdbGame(igdb_id=7, name="Obscure Import", release_year=None, cover_url=None)
    ]


# --- token caching --------------------------------------------------------


def test_token_is_fetched_once_and_reused() -> None:
    token_calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        # `nonlocal` lets this inner function reassign a variable from the
        # enclosing function. Without it, `token_calls = ...` would create a
        # new local and the outer counter would stay at 0.
        nonlocal token_calls
        if is_token_request(request):
            token_calls += 1
            return httpx.Response(200, json=TOKEN_BODY)
        return httpx.Response(200, json=[])

    client = make_client(handler)
    client.search("one")
    client.search("two")

    assert token_calls == 1


def test_expired_token_is_refetched() -> None:
    token_calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal token_calls
        if is_token_request(request):
            token_calls += 1
            return httpx.Response(200, json=TOKEN_BODY)
        return httpx.Response(200, json=[])

    client = make_client(handler)
    client.search("one")

    # Reaching into a private attribute, deliberately: forcing expiry is the
    # only way to exercise this without making the test sleep for weeks.
    client._token_expires_at = 0.0
    client.search("two")

    assert token_calls == 2


def test_rejected_token_is_refreshed_once_then_succeeds() -> None:
    """IGDB can reject a token we still believe is valid (revoked, or expired
    early). One retry with a fresh token should recover."""
    search_attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal search_attempts
        if is_token_request(request):
            return httpx.Response(200, json=TOKEN_BODY)

        search_attempts += 1
        if search_attempts == 1:
            return httpx.Response(401)
        # Empty body on purpose: this test is about the retry, so it stays
        # independent of how parsing behaves.
        return httpx.Response(200, json=[])

    results = make_client(handler).search("final fantasy vi")

    assert search_attempts == 2
    assert results == []


def test_persistent_401_raises_auth_error_without_looping() -> None:
    search_attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal search_attempts
        if is_token_request(request):
            return httpx.Response(200, json=TOKEN_BODY)
        search_attempts += 1
        return httpx.Response(401)

    with pytest.raises(IgdbAuthError):
        make_client(handler).search("anything")

    # Exactly one retry — proof the recursion can't run away.
    assert search_attempts == 2


# --- failure modes --------------------------------------------------------


def test_bad_credentials_raise_auth_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, json={"message": "invalid client"})

    with pytest.raises(IgdbAuthError):
        make_client(handler).search("anything")


def test_network_failure_raises_unavailable() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("name resolution failed")

    with pytest.raises(IgdbUnavailable):
        make_client(handler).search("anything")


def test_igdb_server_error_raises_unavailable() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if is_token_request(request):
            return httpx.Response(200, json=TOKEN_BODY)
        return httpx.Response(503)

    with pytest.raises(IgdbUnavailable):
        make_client(handler).search("anything")


def test_bad_query_raises_generic_igdb_error() -> None:
    """A 400 is our bug, not an outage — it maps to the base error so a
    caller retrying on IgdbUnavailable doesn't retry it forever."""

    def handler(request: httpx.Request) -> httpx.Response:
        if is_token_request(request):
            return httpx.Response(200, json=TOKEN_BODY)
        return httpx.Response(400, text="syntax error")

    with pytest.raises(IgdbError) as caught:
        make_client(handler).search("anything")

    assert not isinstance(caught.value, (IgdbUnavailable, IgdbAuthError))


# --- detail parsing -------------------------------------------------------


def test_first_release_date_returns_a_date() -> None:
    assert _first_release_date(FF6_TIMESTAMP) == date(1994, 3, 24)


def test_first_release_date_handles_missing() -> None:
    assert _first_release_date(None) is None


def test_cover_image_id_is_the_bare_id() -> None:
    assert _cover_image_id({"image_id": "co6ple", "url": "//x/t_thumb/y.jpg"}) == "co6ple"
    assert _cover_image_id(None) is None
    assert _cover_image_id({}) is None


def test_esrb_rating_picks_esrb_out_of_several_boards() -> None:
    age_ratings = [
        {"organization": {"name": "CERO"}, "rating_category": {"rating": "Z"}},
        {"organization": {"name": "PEGI"}, "rating_category": {"rating": "18"}},
        {"organization": {"name": "ESRB"}, "rating_category": {"rating": "M"}},
    ]

    assert _esrb_rating(age_ratings) == "M"


def test_esrb_rating_is_none_when_no_esrb_entry() -> None:
    # Normal for Japan-only and pre-1994 titles.
    assert _esrb_rating([{"organization": {"name": "CERO"}, "rating_category": {"rating": "Z"}}]) is None
    assert _esrb_rating([]) is None
    assert _esrb_rating(None) is None


def test_player_counts_take_the_max_across_conflicting_entries() -> None:
    """multiplayer_modes has one entry PER PLATFORM and they disagree — this
    is the real Baldur's Gate 3 data."""
    modes = [
        {"offlinemax": 1, "offlinecoopmax": 2, "onlinemax": 4, "onlinecoopmax": 4},
        {"offlinemax": 1, "offlinecoopmax": 1, "onlinemax": 4, "onlinecoopmax": 4},
    ]

    assert _player_counts(modes) == (2, 4)


def test_player_counts_are_none_without_multiplayer_modes() -> None:
    # The common case: most single-player games have no entry at all.
    assert _player_counts(None) == (None, None)
    assert _player_counts([]) == (None, None)


def test_player_counts_ignore_missing_and_zero_values() -> None:
    modes = [{"offlinecoopmax": 0, "onlinemax": 8}]

    assert _player_counts(modes) == (None, 8)


def test_tags_flatten_all_six_sources() -> None:
    raw = {
        "genres": [{"name": "Role-playing (RPG)"}],
        "themes": [{"name": "Fantasy"}],
        "game_modes": [{"name": "Single player"}],
        "player_perspectives": [{"name": "Side view"}],
        "franchises": [{"name": "Dungeons & Dragons"}],
        "collections": [{"name": "Baldur's Gate"}],
    }

    assert _tags(raw) == (
        IgdbTag("genre", "Role-playing (RPG)"),
        IgdbTag("theme", "Fantasy"),
        IgdbTag("game_mode", "Single player"),
        IgdbTag("player_perspective", "Side view"),
        IgdbTag("franchise", "Dungeons & Dragons"),
        IgdbTag("collection", "Baldur's Gate"),
    )


def test_tags_keep_the_same_name_under_different_kinds() -> None:
    """'Action' is both a genre and a theme in IGDB — they're distinct tags."""
    raw = {"genres": [{"name": "Action"}], "themes": [{"name": "Action"}]}

    assert _tags(raw) == (IgdbTag("genre", "Action"), IgdbTag("theme", "Action"))


def test_tags_drop_duplicates_within_a_kind_and_skip_nameless_entries() -> None:
    raw = {"genres": [{"name": "Indie"}, {"name": "Indie"}, {}, {"name": None}]}

    assert _tags(raw) == (IgdbTag("genre", "Indie"),)


def test_tags_on_a_game_with_no_lists_is_empty() -> None:
    assert _tags({"id": 1, "name": "Bare"}) == ()


# --- get_details ----------------------------------------------------------


def test_get_details_returns_parsed_detail() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if is_token_request(request):
            return httpx.Response(200, json=TOKEN_BODY)
        return httpx.Response(
            200,
            json=[
                {
                    "id": 119171,
                    "name": "Baldur's Gate III",
                    "summary": "An ancient evil has returned.",
                    "first_release_date": 1691020800,
                    "cover": {"image_id": "co670h"},
                    "age_ratings": [
                        {"organization": {"name": "PEGI"}, "rating_category": {"rating": "18"}},
                        {"organization": {"name": "ESRB"}, "rating_category": {"rating": "M"}},
                    ],
                    "multiplayer_modes": [
                        {"offlinecoopmax": 2, "onlinecoopmax": 4},
                        {"offlinecoopmax": 1, "onlinecoopmax": 4},
                    ],
                    "genres": [{"name": "Role-playing (RPG)"}],
                    "collections": [{"name": "Baldur's Gate"}],
                }
            ],
        )

    detail = make_client(handler).get_details(119171)

    assert detail == IgdbGameDetail(
        igdb_id=119171,
        name="Baldur's Gate III",
        summary="An ancient evil has returned.",
        first_release_date=date(2023, 8, 3),
        cover_image_id="co670h",
        esrb_rating="M",
        max_local_players=2,
        max_online_players=4,
        tags=(
            IgdbTag("genre", "Role-playing (RPG)"),
            IgdbTag("collection", "Baldur's Gate"),
        ),
    )


def test_get_details_uses_a_where_clause_not_search() -> None:
    sent: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(request)
        if is_token_request(request):
            return httpx.Response(200, json=TOKEN_BODY)
        return httpx.Response(200, json=[])

    make_client(handler).get_details(119171)

    body = sent[-1].content.decode()
    assert "where id = 119171;" in body
    assert "search" not in body


def test_get_details_returns_none_for_unknown_id() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if is_token_request(request):
            return httpx.Response(200, json=TOKEN_BODY)
        return httpx.Response(200, json=[])

    assert make_client(handler).get_details(999999999) is None
