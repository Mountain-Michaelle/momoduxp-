# Momodu — AI-Automated Social Posting

A Django + FastAPI hybrid SaaS for AI-powered LinkedIn post scheduling, approval workflows, and background task processing.

---

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                     Production (Daphne :8000)                │
├──────────────────────────────────────────────────────────────┤
│  Django Admin        FastAPI (/api/v1/*)    WebSocket        │
│  • User mgmt         • REST endpoints       • Real-time      │
│  • Post approval     • AI processing        • Notifications  │
│  • Webhooks          • Auth & LinkedIn                       │
├──────────────────────────────────────────────────────────────┤
│                       PostgreSQL                             │
├──────────────────────────────────────────────────────────────┤
│   Redis (broker)    Celery Worker    Celery Beat             │
└──────────────────────────────────────────────────────────────┘
```

**Dev setup** runs Django on `:8000` and FastAPI on `:8001` separately.

---

## Getting Started

### Prerequisites

- Python 3.11+
- PostgreSQL 14+
- Redis 7+
- [uv](https://github.com/astral-sh/uv) (recommended) or pip

### 1. Clone & install

```bash
# Using uv (recommended)
uv venv
uv pip install -r requirements/dev.txt

# Or with pip
python -m venv .venv
source .venv/bin/activate   # Linux/Mac
.venv\Scripts\activate      # Windows
pip install -r requirements/dev.txt
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env with your values
```

Key variables:

| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | PostgreSQL async URL (`postgresql+asyncpg://...`) |
| `REDIS_URL` | Redis URL (`redis://localhost:6379/0`) |
| `SECRET_KEY` | JWT secret — change in production |
| `ENCRYPTION_KEY` | Fernet key for token encryption |
| `OPENAI_API_KEY` | Required for AI features |
| `DJANGO_SETTINGS_MODULE` | `backend.config.dev` or `backend.config.prod` |

### 3. Database setup

```bash
createdb momodu
python manage.py migrate
python manage.py createsuperuser
```

### 4. Run development servers

```bash
# Terminal 1 — Django admin
python manage.py runserver 0.0.0.0:8000

# Terminal 2 — FastAPI
python run_api.py --reload
```

- Django Admin → http://localhost:8000/admin
- FastAPI Docs → http://localhost:8001/api/docs

Or run everything through Daphne (combined):

```bash
python run_daphne.py
# Both available at http://localhost:8000
```

### 5. Celery workers

```bash
# Terminal 3 — worker
celery -A shared worker -l info

# Terminal 4 — beat scheduler
celery -A shared beat -l info
```

FastAPI-only worker (no Django):

```bash
DJANGO_REQUIRED=false celery -A shared worker -l info
```

---

## API Endpoints

### Auth
```
POST /api/v1/auth/login       # OAuth2 password flow
POST /api/v1/auth/token       # JSON login
POST /api/v1/auth/register    # Register user
GET  /api/v1/auth/me          # Current user
POST /api/v1/auth/refresh     # Refresh token
```

### Posts
```
GET    /api/v1/posts              # List (paginated)
GET    /api/v1/posts/{id}         # Get post
POST   /api/v1/posts              # Create post
PATCH  /api/v1/posts/{id}         # Update post
DELETE /api/v1/posts/{id}         # Delete post
POST   /api/v1/posts/{id}/submit  # Submit for approval
POST   /api/v1/posts/{id}/approve # Approve
POST   /api/v1/posts/{id}/reject  # Reject
```

### AI
```
POST /api/v1/ai/generate             # Generate content
POST /api/v1/ai/optimize-post        # Optimize post
POST /api/v1/ai/generate-variations  # Multiple variations
GET  /api/v1/ai/usage                # Quota info
```

### Health
```
GET /health           # Basic
GET /health/detailed  # Full status
GET /health/ready     # Readiness probe
```

---

## Development

### Code quality

```bash
uv run black .
uv run isort .
uv run ruff check .
uv run mypy .
```

### Tests

```bash
uv run pytest
uv run pytest --cov=api --cov=backend
```

### Adding a feature

1. **Django model** → `apps/<app>/models.py`
2. **Shared schema** → `shared/schemas.py`
3. **FastAPI route** → `api/routers/`
4. **Celery task** → `apps/<app>/tasks/`
5. **Register route** → `api/main.py`

---

## Production Deployment

```bash
uv pip install -r requirements/prod.txt

python manage.py collectstatic
python manage.py migrate

# ASGI server
daphne -b 0.0.0.0 -p 8000 backend.backend.asgi:application

# Workers
celery -A shared worker -l info -E
celery -A shared beat -l info
```

---

## Project Structure

```
backend/
├── api/              # FastAPI app (async)
│   ├── main.py
│   ├── config.py
│   ├── routers/      # auth, posts, ai
│   └── tasks/
├── apps/             # Django apps
│   ├── accounts/     # Users & subscriptions
│   ├── posts/        # Post scheduling
│   ├── webhooks/     # Webhook delivery
│   ├── integrations/ # LinkedIn client
│   ├── notifications/# Telegram client
│   ├── ai_models/    # OpenAI client
│   ├── scheduling/   # Celery Beat tasks
│   └── core/         # Admin site & base
├── backend/          # Django config
│   └── config/       # base / dev / prod
├── shared/           # Shared between Django & FastAPI
│   ├── database.py   # SQLAlchemy async
│   ├── models.py     # SQLAlchemy ORM
│   ├── schemas.py    # Pydantic schemas
│   └── celery.py     # Celery instance
├── requirements/
│   ├── base.txt
│   ├── dev.txt
│   └── prod.txt
├── manage.py
├── run_api.py        # Dev FastAPI runner
├── run_daphne.py     # Prod Daphne runner
└── .env.example
```

---

## Security Notes

- JWT tokens expire after 30 minutes (configurable)
- Passwords hashed with bcrypt
- CORS restricted to configured origins
- Rate limiting on AI endpoints
- Never commit `.env` — use `.env.example` as a template

---

## License

MIT
