"""
conftest.py — Shared pytest fixtures for all agent tests.
"""
import pytest
import json
import os
from unittest.mock import AsyncMock, MagicMock

os.environ.setdefault("DRY_RUN", "true")
os.environ.setdefault("OPENAI_API_KEY", "test-key")
os.environ.setdefault("DJANGO_BASE_URL", "http://localhost:8000")


@pytest.fixture
def mock_mcp_client():
    """Returns a mock MCP client that never hits Django."""
    client = MagicMock()
    client.call_tool = AsyncMock(return_value={"status": "ok"})
    return client


@pytest.fixture
def sample_church():
    return {
        "id": 1,
        "name": "Grace Chapel",
        "email": "admin@gracechapel.com",
        "subscription_plan": "BASIC",
        "subscription_status": "ACTIVE",
        "subscription_expiry": "2026-04-28",
    }


@pytest.fixture
def expiring_churches():
    return [
        {
            "id": 1,
            "name": "Grace Chapel",
            "email": "admin@gracechapel.com",
            "subscription_expiry": "2026-04-24",   # 3 days from now
            "subscription_status": "ACTIVE",
        }
    ]
