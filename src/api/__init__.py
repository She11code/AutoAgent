"""API module: FastAPI server and routes."""

from .routes import router
from .server import create_app

__all__ = ["create_app", "router"]
