# Momodu - AI-Automated LinkedIn Posting SaaS

A Django 4.2+ SaaS application for AI-automated LinkedIn posting, featuring a hybrid Django + FastAPI architecture for maximum speed and scalability.

## 🏗️ Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           Production Server (Daphne)                          │
│                           (port 8000 - All-in-One)                           │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────────┐    ┌─────────────────────┐    ┌────────────────┐   │
│  │    Django Admin     │    │      FastAPI         │    │  WebSocket     │   │
│  │   (Custom Theme)     │    │   (High-throughput)   │    │  (Channels)    │   │
│  │                     │    │                      │    │                │   │
│  │  • User Management  │    │  • REST API          │    │  • Real-time   │   │
│  │  • Post Approval    │    │  • AI Processing     │    │  • Notifications│   │
│  │  • Webhooks Config  │    │  • Auth Endpoints    │    │                │   │
│  │  • Dashboard        │    │  • LinkedIn API      │    │                │   │
│  │  • Analytics        │    │  • Telegram Bot      │    │                │   │
│  └─────────────────────┘    └─────────────────────┘    └────────────────┘   │
│           │                         │                          │              │
│           │                         │                          │              │
│           └─────────────────────────┼──────────────────────────┘              │
│                                     ▼                                         │
│                          ┌─────────────────┐                                  │
│                          │   PostgreSQL    │                                  │
│                          │   (Primary DB)  │                                  │
│                          └─────────────────┘                                  │
│                                     │                                         │
│            ┌────────────────────────┼────────────────────────┐                  │
│            ▼                        ▼                        ▼                  │
│    ┌───────────────┐      ┌─────────────────┐      ┌──────────────┐          │
│    │    Redis      │      │  Celery Worker  │      │ Celery Beat │          │
│    │ (Broker/Cache)│      │  (Background)   │      │ (Scheduler) │          │
│    └───────────────┘      └─────────────────┘      └──────────────┘          │
│                                                                              │
│                    External Services:                                        │
│    ┌─────────────┐    ┌─────────────┐    ┌─────────────────┐                │
│    │  LinkedIn   │    │   OpenAI    │    │    Telegram     │                │
│    │     API     │    │    API      │    │      Bot        │                │
│    └─────────────┘    └─────────────┘    └─────────────────┘                │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘

Development Setup (Separate Ports):
┌─────────────────────┐  ┌─────────────────────┐  ┌─────────────────────────────┐
│  Django Admin       │  │    FastAPI          │  │      Celery Workers         │
│  localhost:8000     │  │  localhost:8001      │  │  localhost:6379 (Redis)     │
│  /admin             │  │  /api/docs           │  │  - Worker: task processing  │
│                     │  │                      │  │  - Beat: task scheduling   │
└─────────────────────┘  └─────────────────────┘  └─────────────────────────────┘
```

## 📦 Application Components

```
momodu/
├── 🚀 api/                          # FastAPI Application (Async)
│   ├── main.py                      # FastAPI entry point + lifespan
│   ├── config.py                    # Pydantic settings
│   ├── dependencies.py              # Auth dependencies
│   ├── routers/
│   │   ├── auth.py                  # /api/v1/auth/*
│   │   ├── posts.py                 # /api/v1/posts/*
│   │   └── ai.py                    # /api/v1/ai/*
│   └── tasks/
│       └── post_task.py            # Celery tasks for posts
│
├── 🗄️ apps/                         # Django Applications
│   ├── accounts/                    # User & Subscription Management
│   │   ├── admin.py                 # UserAdmin, SocialPlatformAccountAdmin
│   │   ├── models.py                # User, SocialPlatformAccount, UsageQuota
│   │   └── services.py              # User business logic
│   │
│   ├── posts/                       # Post Scheduling & Management
│   │   ├── admin.py                 # ScheduledPostAdmin
│   │   ├── models.py                # ScheduledPost, PostStatus
│   │   ├── services.py              # Post publishing logic
│   │   ├── tasks/
│   │   │   ├── tasks.py             # Celery tasks
│   │   │   └── decorators.py        # Task decorators
│   │   └── views.py                 # Django views
│   │
│   ├── webhooks/                    # Webhook Endpoints
│   │   ├── admin.py                 # WebhookEndpointAdmin
│   │   ├── models.py                # WebhookEndpoint, WebhookDelivery
│   │   ├── service.py               # Webhook dispatch logic
│   │   └── tasks.py                 # Async webhook tasks
│   │
│   ├── integrations/               # Platform Integrations
│   │   ├── linkedin/
│   │   │   ├── client.py            # LinkedIn API client
│   │   │   └── schemas.py
│   │   └── mixins.py
│   │
│   ├── notifications/               # Notification Services
│   │   ├── telegram/
│   │   │   └── client.py           # Telegram bot client
│   │   └── services.py
│   │
│   ├── ai_models/                   # AI Integration
│   │   ├── openai/
│   │   │   └── client.py           # OpenAI GPT client
│   │   └── base.py
│   │
│   ├── scheduling/                 # Celery Beat Tasks
│   │   ├── admin.py
│   │   ├── models.py
│   │   └── celery.py
│   │
│   └── core/                        # Core Functionality
│       ├── admin_site.py            # Custom MomoduAdminSite
│       ├── models.py
│       └── views.py
│
├── 🔧 backend/                      # Django Configuration
│   ├── config/
│   │   ├── base.py                 # Base settings
│   │   ├── dev.py                  # Development settings
│   │   └── prod.py                 # Production settings
│   ├── asgi.py                     # Combined ASGI (Django + FastAPI)
│   ├── urls.py                     # Django URLs
│   └── celery.py                   # Celery configuration
│
├── 📦 shared/                       # Shared Code (Django + FastAPI)
│   ├── database.py                 # SQLAlchemy async DB
│   ├── models.py                  # SQLAlchemy ORM models
│   ├── schemas.py                 # Pydantic schemas
│   ├── celery.py                  # Shared Celery (Django-optional)
│   ├── utils.py                   # Utilities
│   └── exceptions.py              # Custom exceptions
│
└── 📁 requirements/                 # Dependencies
    ├── base.txt
    ├── dev.txt
    └── prod.txt
```

## 🔄 Request Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              Request Flow                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  1. FastAPI Request (High-Throughput API)                                   │
│  ─────────────────────────────────────────                                  │
│  Client → FastAPI (/api/v1/*) → SQLAlchemy → PostgreSQL                    │
│         → Celery (async tasks) → LinkedIn/Telegram APIs                    │
│                                                                              │
│  2. Django Admin Request (Management)                                        │
│  ───────────────────────────────────────                                    │
│  Admin → Django Admin → Django ORM → PostgreSQL                             │
│              → Celery (scheduled tasks) → User Notifications              │
│                                                                              │
│  3. Celery Background Tasks                                                 │
│  ─────────────────────────────                                              │
│  Beat Scheduler → Worker → Post Publishing → LinkedIn API                   │
│                    → Webhook Delivery → Telegram Notifications             │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

## 🔐 Authentication Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         Authentication Flow                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  POST /api/v1/auth/login                                                    │
│  ───────────────────────────                                                │
│  Request: { "username": "user", "password": "pass" }                      │
│  ↓                                                                         │
│  FastAPI validates credentials                                              │
│  ↓                                                                         │
│  Django ORM checks User model (hashed passwords)                            │
│  ↓                                                                         │
│  Response: { "access_token": "jwt_token", "token_type": "bearer" }      │
│                                                                              │
│  Subsequent Requests:                                                        │
│  Headers: { "Authorization": "Bearer <token>" }                            │
│  ↓                                                                         │
│  FastAPI dependency: get_current_user()                                      │
│  ↓                                                                         │
│  Returns: User object for endpoint use                                     │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

## 📊 Celery Task Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         Celery Task Flow                                     │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────────┐ │
│  │                         Celery Beat (Scheduler)                         │ │
│  │  • approval-deadline-watcher (every 1 min)                              │ │
│  │  • cleanup-failed-posts (hourly)                                        │ │
│  │  • reset-monthly-quotas (1st of month)                                 │ │
│  │  • cleanup-expired-tokens (daily)                                      │ │
│  │  • check-subscription-expiry (weekly)                                  │ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
│                                    ↓                                         │
│  ┌─────────────────────────────────────────────────────────────────────────┐ │
│  │                       Celery Worker (Tasks)                             │ │
│  │                                                                         │ │
│  │  📝 Post Tasks:                                                         │ │
│  │  • publish_scheduled_posts     - Publish approved posts                │ │
│  │  • check_approval_deadlines     - Alert on overdue approvals           │ │
│  │  • retry_failed_posts           - Retry failed post publishing         │ │
│  │                                                                         │ │
│  │  🔔 Notification Tasks:                                                  │ │
│  │  • send_telegram_notification  - Send Telegram alerts                   │ │
│  │                                                                         │ │
│  │  🔗 Webhook Tasks:                                                       │ │
│  │  • dispatch_webhook            - Send webhook payloads                   │ │
│  │                                                                         │ │
│  │  📈 Maintenance Tasks:                                                    │ │
│  │  • cleanup_expired_tokens       - Clean expired OAuth tokens            │ │
│  │  • reset_user_quotas            - Reset monthly usage quotas            │ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

## 📁 Project Structure

```
backend/
├── api/                           # FastAPI application (async)
│   ├── __init__.py
│   ├── main.py                    # FastAPI entry point with lifespan
│   ├── config.py                  # FastAPI settings (pydantic-settings)
│   ├── dependencies.py            # Auth dependencies (async)
│   ├── exceptions.py              # Custom exceptions
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── auth.py                # Authentication endpoints
│   │   ├── posts.py               # Posts CRUD endpoints
│   │   └── ai.py                  # AI processing endpoints
│   └── tasks/
│       └── post_task.py           # Celery tasks (FastAPI)
│
├── shared/                        # Shared code between Django & FastAPI
│   ├── __init__.py
│   ├── database.py               # SQLAlchemy async DB connection
│   ├── models.py                 # SQLAlchemy ORM models
│   ├── schemas.py                 # Pydantic schemas (DRY)
│   ├── celery.py                 # Celery instance (Django-optional)
│   ├── utils.py                  # Shared utilities
│   └── exceptions.py             # Custom exceptions
│
├── backend/                       # Django application
│   ├── config/
│   │   ├── __init__.py
│   │   ├── base.py              # Base Django settings
│   │   ├── dev.py               # Development settings
│   │   └── prod.py              # Production settings
│   ├── asgi.py                  # Combined ASGI (Django + FastAPI)
│   ├── urls.py                  # Django URLs
│   └── celery.py                # Celery configuration
│
├── apps/                         # Django apps
│   ├── accounts/                # User management
│   │   ├── models.py            # User, SocialPlatformAccount, UsageQuota
│   │   ├── services.py          # User business logic
│   │   ├── admin.py             # Custom admin classes
│   │   ├── apps.py             # AppConfig with ready() method
│   │   └── migrations/
│   │
│   ├── posts/                   # Post scheduling
│   │   ├── models.py            # ScheduledPost, PostStatus
│   │   ├── services.py         # Post business logic
│   │   ├── admin.py            # Custom admin classes
│   │   ├── apps.py             # AppConfig with ready() method
│   │   ├── tasks/
│   │   │   ├── __init__.py
│   │   │   ├── tasks.py        # Celery tasks
│   │   │   └── decorators.py   # Task decorators
│   │   └── migrations/
│   │
│   ├── webhooks/                # Webhook management
│   │   ├── models.py           # WebhookEndpoint, WebhookDelivery
│   │   ├── admin.py           # Webhook admin classes
│   │   ├── apps.py            # AppConfig with ready() method
│   │   ├── service.py         # Webhook dispatch logic
│   │   └── tasks.py           # Async webhook tasks
│   │
│   ├── integrations/           # Platform integrations
│   │   ├── __init__.py
│   │   ├── linkedin/
│   │   │   ├── client.py       # LinkedIn API client (async)
│   │   │   └── schemas.py      # LinkedIn-specific schemas
│   │   └── mixins.py
│   │
│   ├── notifications/          # Notifications
│   │   ├── telegram/
│   │   │   └── client.py      # Telegram client (async)
│   │   ├── services.py
│   │   └── apps.py
│   │
│   ├── ai_models/              # AI integrations
│   │   ├── openai/
│   │   │   └── client.py      # OpenAI client (async)
│   │   └── base.py            # Base AI client interface
│   │
│   ├── scheduling/             # Celery Beat tasks
│   │   ├── admin.py
│   │   ├── models.py
│   │   ├── celery.py
│   │   └── apps.py
│   │
│   └── core/                   # Core functionality
│       ├── admin_site.py       # Custom MomoduAdminSite (Dark Indigo theme)
│       ├── models.py
│       ├── views.py
│       └── apps.py
│
├── requirements/
│   ├── base.txt                 # Core dependencies
│   ├── dev.txt                  # Development dependencies
│   └── prod.txt                 # Production dependencies
│
├── migrations/                  # Django migrations (auto-generated)
├── tests/                       # Tests
├── run_api.py                   # Run FastAPI (dev)
├── run_daphne.py               # Run Daphne (prod)
├── manage.py                    # Django management
├── .env.example                # Environment template
└── .env                        # Environment variables
```

## 🎯 Early Startup Recommendations

### Features to Add Later (Low Priority for MVP)

| Feature | Add When | Effort |
|---------|----------|--------|
| Email Notifications | 50+ users | Low |
| Usage Quotas | 100+ users | Low-Medium |
| Webhooks | Integration needs | Medium |
| Team Collaboration | 20+ users/team | Medium |
| Multi-Tenancy | 100+ customers | HIGH |
| Billing/Stripe | Ready to monetize | Medium |

### Features to Add Now (Quick Wins)

#### 1. Token Encryption (10 min)

```python
# shared/utils.py
from cryptography.fernet import Fernet
from django.conf import settings
import base64
import os

# Generate key once and store in env
ENCRYPTION_KEY = settings.ENCRYPTION_KEY.encode()
fernet = Fernet(ENCRYPTION_KEY)

def encrypt_token(token: str) -> str:
    """Encrypt sensitive tokens."""
    return fernet.encrypt(token.encode()).decode()

def decrypt_token(encrypted: str) -> str:
    """Decrypt tokens."""
    return fernet.decrypt(encrypted.encode()).decode()
```

#### 2. Usage Quotas (30 min)

```python
# apps/accounts/models.py (Django)
class UsageQuota(BaseModel):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    posts_this_month = models.IntegerField(default=0)
    ai_generations_this_month = models.IntegerField(default=0)
    last_reset = models.DateTimeField(auto_now_add=True)

    PLAN_LIMITS = {
        'free': {'posts': 10, 'ai_generations': 5},
        'pro': {'posts': 100, 'ai_generations': 50},
        'enterprise': {'posts': -1, 'ai_generations': -1},  # unlimited
    }

    def can_create_post(self) -> bool:
        limit = self.PLAN_LIMITS.get(self.user.subscription_plan, {})
        posts_used = self.posts_this_month
        return limit.get('posts', 0) == -1 or posts_used < limit.get('posts', 0)
```

#### 3. Async Rate Limiting (15 min)

```python
# api/dependencies.py (FastAPI)
from slowapi import Limiter
from slowapi.util import get_remote_address
from fastapi import Request, HTTPException, status

limiter = Limiter(key_func=get_remote_address)

async def rate_limit(request: Request):
    """Rate limiting dependency for async endpoints."""
    limiter = request.state.limiter
    if limiter.limitExceeded.name == "default":
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded"
        )
```

### Multi-Tenancy (Plan for Future)

```python
# Pattern for future migration
class TenantMixin:
    tenant_id = models.UUIDField()

    @classmethod
    def for_tenant(cls, tenant_id):
        return cls.objects.filter(tenant_id=tenant_id)
```

## 🔄 Async Architecture Patterns

### DRY: Shared Database Connection

```python
# shared/database.py
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from api.config import api_settings

engine = create_async_engine(api_settings.DATABASE_URL, echo=True)
async_session = sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)

async def get_db() -> AsyncSession:
    """FastAPI dependency for async DB session."""
    async with async_session() as session:
        try:
            yield session
        finally:
            await session.close()
```

### DRY: Pydantic Schemas

```python
# shared/schemas.py
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional
from enum import Enum

class PostStatus(str, Enum):
    DRAFT = "draft"
    SENT_FOR_APPROVAL = "sent_for_approval"
    APPROVED = "approved"
    PUBLISHED = "published"
    FAILED = "failed"

class PostBase(BaseModel):
    content: str = Field(..., min_length=1, max_length=3000)
    scheduled_for: datetime

class PostCreate(PostBase):
    approval_deadline: Optional[datetime] = None

class PostResponse(PostBase):
    id: str
    status: PostStatus
    author_id: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
```

### DRY: Celery Task Base

```python
# apps/posts/tasks/decorators.py
from celery import shared_task
from celery.exceptions import Reject
import logging

logger = logging.getLogger(__name__)

def base_task(name=None, bind=True, max_retries=3):
    """DRY decorator for common task patterns."""
    def decorator(func):
        task = shared_task(
            bind=bind,
            name=name,
            autoretry_for=(Exception,),
            retry_backoff=True,
            retry_backoff_max=600,
            retry_kwargs={'max_retries': max_retries},
            reject_on_worker_lost=True,
        )(func)
        return task
    return decorator
```

### Async HTTP Client Pattern

```python
# apps/integrations/linkedin/client.py
import httpx
from api.config import api_settings

class LinkedinClient:
    base_url = api_settings.LINKEDIN_BASE_URL

    def __init__(self, access_token: str):
        self.headers = {
            "Authorization": f"Bearer {access_token}",
            "X-Restli-Protocol-Version": "2.0.0"
        }

    async def post_text(self, author_urn: str, text: str) -> str:
        payload = {
            "author": author_urn,
            "lifecycleState": "PUBLISHED",
            "specificContent": {
                "com.linkedin.ugc.ShareContent": {
                    "shareCommentary": {"text": text},
                    "shareMediaCategory": "NONE",
                }
            },
            "visibility": {
                "com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"
            }
        }

        async with httpx.AsyncClient(timeout=30) as client:
            res = await client.post(
                f"{self.base_url}/ugcPosts",
                json=payload,
                headers=self.headers
            )
            res.raise_for_status()
            return res.headers.get("x-restli-id")
```

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- PostgreSQL 14+
- Redis 7+
- Git

### 1. Clone and Install Dependencies

```bash
cd backend
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or
.\venv\Scripts\activate   # Windows

pip install -r requirements/dev.txt
```

### 2. Configure Environment

```bash
# Copy example env
cp .env.example .env

# Edit .env file with your configuration
nano .env

# Key settings:
# POSTGRES_DB=momodu
# POSTGRES_USER=postgres
# POSTGRES_PASSWORD=postgres
# POSTGRES_HOST=localhost
# POSTGRES_PORT=5432
# REDIS_URL=redis://localhost:6379/0
# OPENAI_API_KEY=your-key
# ENCRYPTION_KEY=generate-with-python-cryptography
```

### 3. Setup Database

```bash
# Create PostgreSQL database
createdb momodu

# Run migrations
python manage.py migrate

# Create initial data
python manage.py createsuperuser
```

### 4. Run Development Servers

**Option A: Run Both Separately (Recommended for Development)**

```bash
# Terminal 1: Run Django
python manage.py runserver 0.0.0.0:8000

# Terminal 2: Run FastAPI
python run_api.py --reload

# Access:
# - Django Admin: http://localhost:8000/admin
# - FastAPI Docs: http://localhost:8001/api/docs
```

**Option B: Run Combined with Daphne**

```bash
# Run Daphne (combined Django + FastAPI)
python run_daphne.py

# Access:
# - Django: http://localhost:8000/admin
# - FastAPI: http://localhost:8000/api/docs
```

### 5. Run Celery (Background Tasks)

**Full Django + Celery (includes periodic tasks):**
```bash
# Terminal 3: Run Celery worker
celery -A shared worker -l info

# Terminal 4: Run Celery beat (scheduled tasks)
celery -A shared beat -l info
```

**FastAPI-only Worker (no Django):**
```bash
# For FastAPI-only workers that don't need Django
DJANGO_REQUIRED=false celery -A shared worker -l info
```

**Production:**
```bash
# Run with Django
celery -A shared worker -l info -E
celery -A shared beat -l info
```

## 🔧 Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DJANGO_SETTINGS_MODULE` | Django settings module | `backend.config.dev` |
| `DATABASE_URL` | PostgreSQL connection URL | `postgresql+asyncpg://...` |
| `REDIS_URL` | Redis connection URL | `redis://localhost:6379/0` |
| `CELERY_BROKER_URL` | Celery broker URL | `redis://localhost:6379/0` |
| `OPENAI_API_KEY` | OpenAI API key | Required for AI features |
| `SECRET_KEY` | JWT secret key | Change in production |
| `ENCRYPTION_KEY` | Token encryption key | Generate with Fernet |

### Database Configuration

The application uses PostgreSQL as the primary database. SQLAlchemy async is used for FastAPI endpoints, while Django ORM handles Django operations.

**Note:** Both frameworks access the same database tables. Models must be kept in sync using the shared schemas.

## 📚 API Documentation

### FastAPI Endpoints

#### Authentication
```
POST /api/v1/auth/login          # OAuth2 password flow
POST /api/v1/auth/token          # JSON login
POST /api/v1/auth/register       # User registration
GET  /api/v1/auth/me             # Current user info
POST /api/v1/auth/refresh         # Refresh token
```

#### Posts
```
GET    /api/v1/posts              # List posts (paginated)
GET    /api/v1/posts/{id}         # Get post details
POST   /api/v1/posts              # Create post
PATCH  /api/v1/posts/{id}         # Update post
DELETE /api/v1/posts/{id}         # Delete post
POST   /api/v1/posts/{id}/submit   # Submit for approval
POST   /api/v1/posts/{id}/approve  # Approve post
POST   /api/v1/posts/{id}/reject   # Reject post
```

#### AI Processing
```
POST /api/v1/ai/generate         # Generate content
POST /api/v1/ai/optimize-post    # Optimize existing post
POST /api/v1/ai/generate-variations  # Generate multiple variations
GET  /api/v1/ai/usage             # Check AI usage quota
```

#### Health Checks
```
GET /health                      # Basic health check
GET /health/detailed            # Detailed health check
GET /health/ready               # Readiness probe
```

### Using the API

```bash
# Login and get token
curl -X POST "http://localhost:8001/api/v1/auth/token" \
  -H "Content-Type: application/json" \
  -d '{"username": "user", "password": "password"}'

# Use token in requests
curl -X GET "http://localhost:8001/api/v1/posts" \
  -H "Authorization: Bearer <token>"
```

## 🧪 Development Workflow

### Code Style

```bash
# Format code
black .
isort .

# Type checking
mypy .

# Linting
flake8 .

# Import sorting
ruff check .
```

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=api --cov=backend

# Run specific test file
pytest tests/test_posts.py
```

### Creating New Features

1. **Django Models** → Add to `apps/<app>/models.py`
2. **Shared Schemas** → Mirror in `shared/schemas.py` (DRY)
3. **FastAPI Routes** → Add to `api/routers/`
4. **Celery Tasks** → Add to `apps/<app>/tasks/tasks.py`
5. **URL Configuration** → Update `api/main.py`

## 🔒 Security Considerations

- JWT tokens expire after 30 minutes (configurable)
- Passwords are hashed with bcrypt
- CORS is configured for specific origins
- Rate limiting is implemented on AI endpoints
- Environment variables are used for sensitive data
- **TODO**: Encrypt social account tokens with Fernet
- **TODO**: Add 2FA support for production
- **TODO**: Implement password strength policies

## 📈 Performance

- **FastAPI**: Handles high-throughput API requests with async/await
- **Django**: Manages admin and background tasks
- **PostgreSQL**: Optimized queries with proper indexing
- **Redis**: Caching and Celery broker
- **Daphne**: ASGI server for concurrent connections
- **Celery**: Distributed task queue with retry logic

## 🚢 Production Deployment

### Using Docker

```dockerfile
# See docker-compose.yml for full setup
docker-compose up -d
```

### Manual Deployment

```bash
# Install production dependencies
pip install -r requirements/prod.txt

# Collect static files
python manage.py collectstatic

# Run migrations
python manage.py migrate

# Start Daphne
daphne -b 0.0.0.0 -p 8000 backend.backend.asgi:application

# Start Celery worker
celery -A shared worker -l info -E

# Start Celery beat
celery -A shared beat -l info
```

## 🛣️ Roadmap

### Phase 1 (MVP) - Current
- [x] User authentication
- [x] Social account connection (LinkedIn)
- [x] Post scheduling with approval workflow
- [x] AI content generation (OpenAI)
- [x] Telegram notifications
- [x] Custom Django Admin with Dark Indigo theme
- [x] Webhook support
- [x] Hybrid Django + FastAPI architecture
- [x] Celery background tasks (Django-optional)

### Phase 2 (Growth)
- [ ] Usage quotas UI
- [ ] Email notifications
- [ ] Webhook analytics
- [ ] Basic analytics dashboard
- [ ] Team collaboration

### Phase 3 (Scale)
- [ ] Multi-tenancy
- [ ] Billing/Stripe integration
- [ ] Advanced analytics
- [ ] Multi-platform support (Twitter, Facebook, Instagram)

## 📝 License

MIT License - See LICENSE file for details.

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests and linting
5. Submit a pull request

## 📞 Support

For issues and questions, please open a GitHub issue.
