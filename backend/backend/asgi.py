"""
ASGI config for running both Django Channels and FastAPI on Daphne.
This configuration allows both Django admin and FastAPI endpoints to coexist.

Architecture:
- Django Channels: Handles WebSocket connections (real-time features)
- FastAPI: Handles high-throughput REST API endpoints
- Daphne: ASGI server that runs both

Routes:
- /api/* → FastAPI application
- /ws/* → Django Channels WebSocket consumers
- /* → Django application (admin, templates)
"""

import os
from pathlib import Path

# Set Django settings module before any Django imports
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.config.dev')

# Setup Django
import django
django.setup()

from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
import asyncio

# Import FastAPI after Django setup
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware


# Django ASGI application
django_asgi_app = get_asgi_application()


# FastAPI application
# Import here to avoid circular imports and ensure Django is setup
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from api.main import app as fastapi_app


# Configure FastAPI for mounting
# The app variable is what Daphne will use
fastapi_app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Create combined ASGI application
# We use a custom ASGI app that routes requests based on path
async def application(scope, receive, send):
    """
    Combined ASGI application that routes requests to Django or FastAPI.
    
    Routes:
    - /api/* → FastAPI
    - /ws/* → Django Channels WebSocket
    - /* → Django
    """
    path = scope.get('path', '')
    
    if path.startswith('/api/'):
        # Route to FastAPI
        await fastapi_app(scope, receive, send)
    elif path.startswith('/ws/'):
        # Route to Django Channels
        await django_asgi_app(scope, receive, send)
    else:
        # Route to Django
        await django_asgi_app(scope, receive, send)


# Alternative: Mount FastAPI under /api prefix
# This is cleaner and uses ASGI mounting properly
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Create a new FastAPI app that's mounted
api_app = FastAPI(
    docs_url=None,  # Disable docs at root
    redoc_url=None,
)

# Mount the main FastAPI app under /api
api_app.mount("/api", fastapi_app)


# Combined application with proper mounting
async def combined_application(scope, receive, send):
    """
    Combined ASGI application with proper ASGI mounting.
    """
    path = scope.get('path', '')
    
    if path.startswith('/api'):
        # Use the mounted FastAPI app
        await api_app(scope, receive, send)
    elif path.startswith('/ws'):
        # Use Django Channels
        await django_asgi_app(scope, receive, send)
    else:
        # Use Django
        await django_asgi_app(scope, receive, send)


# For Daphne, export the application
# Use this for production
app = combined_application


# Development convenience: separate apps
# Uncomment below for development with separate ports
# app = django_asgi_app  # Use Django only for development


if __name__ == "__main__":
    """
    Run Daphne from command line:
    daphne -b 0.0.0.0 -p 8000 backend.backend.asgi:application
    """
    import sys
    print("Use: daphne -b 0.0.0.0 -p 8000 backend.backend.asgi:application")
    print("For development, run Django and FastAPI separately:")
    print("  Django: python manage.py runserver 0.0.0.0:8000")
    print("  FastAPI: uvicorn api.main:app --host 0.0.0.0 --port 8001 --reload")
