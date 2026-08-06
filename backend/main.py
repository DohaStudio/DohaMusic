"""ASGI entrypoint for DohaMusic Backend."""

from backend.app.factory import create_app

app = create_app()
