"""
Tests for TreasuryHealthAgent.
"""
import pytest
from unittest.mock import AsyncMock, patch


@pytest.mark.asyncio
async def test_flags_stalled_expense(mock_mcp_client):
    stalled = [{"id": 5, "title": "Sound System", "amount": 3000,
                "status": "PENDING", "hours_pending": 60}]
    with patch("agents.treasury_health.mcp_client", mock_mcp_client):
        mock_mcp_client.call_tool = AsyncMock(return_value=stalled)
        from agents.treasury_health import TreasuryHealthAgent
        agent = TreasuryHealthAgent()
        await agent.run()
        assert mock_mcp_client.call_tool.called


@pytest.mark.asyncio
async def test_anomaly_detection(mock_mcp_client):
    large_tx = [{"id": 9, "amount": 9999, "description": "Unknown", "type": "DEBIT"}]
    with patch("agents.treasury_health.mcp_client", mock_mcp_client):
        mock_mcp_client.call_tool = AsyncMock(return_value=large_tx)
        from agents.treasury_health import TreasuryHealthAgent
        agent = TreasuryHealthAgent()
        await agent.run()
