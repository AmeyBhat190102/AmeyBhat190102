"""Test env: set before any app import. DRY_RUN keeps the LLM and channels
offline; the DATABASE_URL is a placeholder — db.py's pool is lazy, and any test
that would touch Postgres monkeypatches the db functions it needs."""
import os

os.environ.setdefault("DATABASE_URL", "postgresql://placeholder:placeholder@localhost:5/placeholder")
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")
os.environ.setdefault("DRY_RUN", "true")
os.environ.setdefault("WEBHOOK_SECRET", "test-secret")
