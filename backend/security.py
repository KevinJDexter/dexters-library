"""
Shared-secret guard for protected endpoints.

One fixed value both frontend and backend know, sent as the X-Write-Secret
header. Requests without it get 401.

Guards every write, plus reads that spend something scarce — the IGDB search
burns a shared rate limit, so it's protected too. Plain reads of our own data
stay open.

Deliberately not real auth. It closes the door on drive-by requests to a
public URL, nothing more.
"""

import os
import secrets
from typing import Annotated, Optional

from dotenv import load_dotenv
from fastapi import Header, HTTPException

# Idempotent — database.py already ran this, but depending on import order
# elsewhere is fragile. Calling it again costs nothing.
load_dotenv()

WRITE_SECRET = os.environ.get("WRITE_SECRET")

# Same fail-loud policy as DATABASE_URL: a missing secret should stop the
# server from booting, not silently leave every write endpoint open (or
# silently reject everything with a confusing 401).
if not WRITE_SECRET:
    raise RuntimeError(
        "WRITE_SECRET is not set. Add it to backend/.env (any long random "
        "string; `python -c 'import secrets; print(secrets.token_urlsafe(32))'` "
        "generates a good one) and set the same value on Render."
    )


def require_secret(
    x_write_secret: Annotated[Optional[str], Header()] = None,
) -> None:
    """FastAPI dependency: 401 unless the correct X-Write-Secret header is sent.

    FastAPI derives the header name from the parameter name: x_write_secret
    becomes X-Write-Secret (underscores to hyphens, case-insensitive like all
    HTTP headers). The header keeps the "write" wording even though it now
    guards a read as well — renaming it would break the deployed frontend,
    which sends that exact string.

    The default of None makes the header optional to *parse* — so a missing
    header reaches the check below and 401s, instead of FastAPI auto-rejecting
    it as a 422 validation error, which would leak which part was wrong.
    """
    # compare_digest takes constant time regardless of where the strings
    # differ, closing off timing attacks that char-by-char == would allow.
    # Overkill for this app, but it's the idiom worth knowing.
    if x_write_secret is None or not secrets.compare_digest(
        x_write_secret, WRITE_SECRET
    ):
        raise HTTPException(status_code=401, detail="Missing or invalid secret")
