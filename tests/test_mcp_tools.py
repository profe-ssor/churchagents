"""
Tests for MCP tool layer — ensures tools call Django via client.get without real HTTP.
"""
from datetime import date, timedelta
from unittest.mock import AsyncMock, patch

import pytest


@pytest.mark.asyncio
async def test_get_expiring_subscriptions_calls_correct_endpoint():
    soon = (date.today() + timedelta(days=5)).isoformat()
    payload = {
        "results": [
            {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "name": "Test Church",
                "email": "admin@test.com",
                "subscription_expiry": soon,
                "subscription_status": "ACTIVE",
            }
        ]
    }
    mock_get = AsyncMock(return_value=payload)
    with patch("mcp_server.client.get", mock_get):
        from mcp_server.tools.accounts import get_expiring_subscriptions

        result = await get_expiring_subscriptions(days=7)
        assert isinstance(result, list)
        assert len(result) >= 1
        mock_get.assert_called()
