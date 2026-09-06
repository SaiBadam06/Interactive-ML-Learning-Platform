"""Vercel entrypoint. The Python runtime looks for a WSGI `app` in this module."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ.setdefault("DATA_DIR", "/tmp")  # only writable path on Vercel

from app import app  # noqa: E402
