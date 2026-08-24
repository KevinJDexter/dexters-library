"""
Tests for the IGDB client. Nothing here touches the network.

httpx.MockTransport takes a plain function and calls it instead of opening a
socket, so we hand IgdbClient an httpx.Client wired to one. Every request the
client makes lands in our handler and we decide what comes back — including
failures that would be impossible to trigger against the real service.
"""

import httpx
import pytest

from video_games.igdb import (
    IgdbAuthError,
    IgdbClient,
    IgdbError,
    IgdbGame,
    IgdbUnavailable,
    _cover_url,
    _release_year,
)

TOKEN_BODY = {"access_token": "fake-token-1", "expires_in": 5_000_000}

# 1994-03-23, comfortably inside FF6's release year.
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
