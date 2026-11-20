"""Shared fixtures for the Sentinel QA suite."""
from __future__ import annotations

from pathlib import Path

import pytest

from app import app as flask_app

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture()
def app():
    flask_app.config.update(TESTING=True)
    return flask_app


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def repo_root():
    return ROOT
