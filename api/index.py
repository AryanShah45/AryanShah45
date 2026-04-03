"""Vercel serverless entry point — exports the FastAPI ASGI app."""

import os
import sys

# Add project root to sys.path so src.* imports resolve correctly
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.web.app import app  # noqa: E402, F401
