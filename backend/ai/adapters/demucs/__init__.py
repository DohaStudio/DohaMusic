"""Demucs adapter boundary without importing optional model dependencies."""

from backend.ai.adapters.demucs.adapter import DemucsAdapter
from backend.ai.adapters.demucs.config import DemucsConfig

__all__ = ["DemucsAdapter", "DemucsConfig"]
