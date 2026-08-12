"""
Dexter's Library — API entry point.

This is the whole backend right now: one endpoint that says hello.
The point is to prove the plumbing works end to end before we build features.

Run it locally with:
    uvicorn main:app --reload

Then open http://127.0.0.1:8000/api/health in a browser.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# `app` is the application object. Uvicorn looks for this exact variable when you
# run `uvicorn main:app` — "main" is this file, "app" is this name.
app = FastAPI(title="Dexter's Library API")


# The Angular dev server runs on port 4200. Without this block, your browser will
# refuse to let the frontend talk to the backend, because they're on different
# ports and the browser treats that as a different site.
ALLOWED_ORIGINS = [
    "http://localhost:4200",
    "http://127.0.0.1:4200",
]

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
