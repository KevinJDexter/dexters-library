# Dexter's Library

A tracker for my own game collection and achievements.

A learning project: Angular frontend, Python (FastAPI) backend, PostgreSQL, deployed so
it works on desktop and phone.

## Layout

```
dexters-library/
├── frontend/     Angular app          (created by the Angular CLI — see setup)
├── backend/      Python FastAPI API
└── CLAUDE.md     Project instructions for AI tooling
```

One repository, two folders. Everything versions together, one deploy story to learn.

## Setup

### Backend

```bash
cd backend
python3 -m venv .venv          # create an isolated Python environment
source .venv/bin/activate      # switch into it (do this every new terminal)
pip install -r requirements.txt
uvicorn main:app --reload      # runs on http://127.0.0.1:8000
```

Check it: open <http://127.0.0.1:8000/api/health> — you should see
`{"status":"ok","message":"Hello from Python"}`.

Bonus: <http://127.0.0.1:8000/docs> gives you interactive API documentation that
FastAPI generates for free from the code.

### Frontend

Not created yet. From the repo root:

```bash
npx @angular/cli@latest new frontend --style=css --ssr=false --skip-git
cd frontend
npm start                      # runs on http://localhost:4200
```

The `--skip-git` matters — this repo already has git, and we don't want a second one
nested inside it.

## Running both

Two terminals. Backend on `:8000`, frontend on `:4200`. The frontend calls the backend;
CORS is already configured in `backend/main.py` to allow it.
