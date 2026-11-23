# Pulchowk Project Repository

A searchable catalogue of student and faculty engineering projects at Pulchowk Campus (Institute of Engineering, Tribhuvan University).

Reports are deposited as PDFs, their metadata is extracted automatically and checked by a department reviewer, and the published record becomes findable through keyword and semantic search.
Full reports stay with the department: readers see metadata, abstracts and approved sections, and request access to the rest inside the app.

What the project is for, and the rules a change is judged against, are in [STRATEGY.md](STRATEGY.md).

## Features

- **Campus sign-in.** Google sign-in limited to `@pcampus.edu.np` accounts, followed by an institutional profile (student or faculty). Every API endpoint except sign-in requires it.
- **Browse and search.** Hybrid search that fuses PostgreSQL full-text ranking with sentence-embedding similarity, plus filters for department, level, batch, cluster, supervisor and project type.
- **Similar work check.** Describe an idea in plain language and see whether related work already exists. Results are explained by shared subject matter, never by a raw score, and never claim copying or originality.
- **Ingestion and review.** A Celery pipeline extracts title, people, sections and front matter from a report PDF. Reviewers verify every field against the PDF before anything is published.
- **Report access requests.** Readers ask for a full report; department reviewers approve or decline, and the decision unlocks the report for that reader only.
- **Notifications, bookmarks and role requests** for students, faculty and administrators.

## Tech stack

| Layer | Stack |
|---|---|
| Backend | Python 3.12, Django 6, Django REST Framework, SimpleJWT (HttpOnly cookies) |
| Database | PostgreSQL 16 with the `pgvector` extension |
| Background jobs | Celery with Redis |
| Search and similarity | sentence-transformers (`BAAI/bge-small-en-v1.5`), PostgreSQL full-text search, RapidFuzz |
| PDF extraction | PyMuPDF |
| Frontend | React, Vite, Tailwind CSS, React Router, Vitest |

## Repository layout

```
backend/
  config/          Django settings, URLs, Celery app
  accounts/        Users, Google sign-in, profiles, role requests
  organization/    Campuses, departments, research groups, department admins
  ingestion/       PDF extraction pipeline, ingestion jobs, review and publish
  repository/      Projects, search, embeddings, similarity, access requests, bookmarks
  notifications/   In-app notifications
  core/            Shared API response and error envelopes
frontend/src/
  pages/           One component per route
  components/      Shared UI
  api/client.js    API client (cookie-based auth with silent refresh)
docs/              Endpoint notes for backend and frontend
notebooks/         Pipeline debugging notebook
```

## Getting started

### Prerequisites

- Python 3.12
- Node.js 20 or newer
- PostgreSQL 16 with `pgvector` (for example `sudo apt install postgresql-16-pgvector`, or the `pgvector/pgvector:pg16` Docker image)
- Redis, for the Celery broker
- A Google OAuth client ID for web sign-in

### Backend

```bash
cd backend
python3.12 -m venv .venv
source .venv/bin/activate

# Optional, on a machine without a GPU: install the CPU build of PyTorch first
# to skip the multi-gigabyte CUDA download.
pip install torch --index-url https://download.pytorch.org/whl/cpu

pip install -r requirements.txt
cp .env.example .env    # then fill in SECRET_KEY, DB_*, GOOGLE_CLIENT_ID, CELERY_*
```

Create the database, then apply migrations (they enable the `vector` extension):

```bash
createdb pulchowk
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

In a second terminal, start the worker that runs ingestion and indexing:

```bash
cd backend && source .venv/bin/activate
celery -A config worker -l info
```

With Redis on its default port, set `CELERY_BROKER_URL=redis://localhost:6379/0` and `CELERY_RESULT_BACKEND=redis://localhost:6379/0` in `backend/.env`.
The embedding model downloads from Hugging Face on first use.

### Frontend

```bash
cd frontend
npm ci
cp .env.example .env    # set VITE_GOOGLE_CLIENT_ID and VITE_API_BASE_URL
npm run dev
```

The app runs at http://localhost:5173 and proxies `/api` and `/media` to the backend at `http://localhost:8000`.

## Configuration

Backend variables live in `backend/.env`; [`backend/.env.example`](backend/.env.example) lists them.

| Variable | Purpose |
|---|---|
| `SECRET_KEY`, `DEBUG`, `ALLOWED_HOSTS` | Standard Django settings |
| `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT` | PostgreSQL connection |
| `GOOGLE_CLIENT_ID` | Must match the frontend's `VITE_GOOGLE_CLIENT_ID` |
| `ALLOWED_LOGIN_DOMAINS` | Comma-separated email domains allowed to sign in; keep it at `pcampus.edu.np` |
| `CORS_ALLOWED_ORIGINS` | Comma-separated; defaults to the local dev servers |
| `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND` | Redis URLs for Celery |
| `EMBEDDING_MODEL_NAME`, `SEARCH_*`, `SIMILAR_*`, `CONCEPT_*` | Search and similarity tuning; defaults in `config/settings.py` are calibrated against the current corpus |

## Tests and checks

```bash
# Backend (needs PostgreSQL with pgvector; Django creates a throwaway test database)
cd backend && python manage.py test

# Frontend
cd frontend && npm test && npm run lint && npm run build
```

## Useful management commands

| Command | What it does |
|---|---|
| `python manage.py export_bundle --out <dir>` | Export published projects as a portable bundle |
| `python manage.py import_bundle --bundle <dir> [--dry-run]` | Merge an exported bundle into this database |
| `python manage.py backfill_embeddings` | Generate or refresh project embeddings |
| `python manage.py backfill_search_vectors` | Rebuild the full-text search vectors |
| `python manage.py search_eval` | Offline diagnostics for embeddings and semantic retrieval |

Run any command with `--help` for its options.

## Contributing

Work happens on short-lived branches off `main`, merged through pull requests.
Commit messages follow [Conventional Commits](https://www.conventionalcommits.org/) (`feat(scope): ...`, `fix(scope): ...`).
Before opening a pull request, run the tests and checks above, and read [STRATEGY.md](STRATEGY.md): a change should make a reviewed project record easier to find, understand or correct, without exposing report content to readers who have not been granted access.
Never commit `.env` files, report PDFs or database dumps.

## Contributors

- [@hobkb](https://github.com/hobkb)
- Nischal Ghimire ([@nischalg8](https://github.com/nischalg8))
- Siwansh Pathak
