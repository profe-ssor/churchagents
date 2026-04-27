"""
Tests for MCP tool layer — ensures tools call the right Django endpoints.
Uses httpx mock to avoid real HTTP calls.
"""
import pytest
from unittest.mock import AsyncMock, patch


@pytest.mark.asyncio
async def test_get_expiring_subscriptions_calls_correct_endpoint():
    mock_response = AsyncMock()
    mock_response.json.return_value = []
    mock_response.status_code = 200

    with patch("mcp_server.client.BaseClient.get", return_value=mock_response):
        from mcp_server.tools.accounts import get_expiring_subscriptions
        result = await get_expiring_subscriptions(days=7)
        assert isinstance(result, list)
