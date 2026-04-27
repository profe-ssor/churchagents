"""
Tests for SubscriptionWatchdogAgent.
Runs with DRY_RUN=true — no real emails or DB writes.
"""
import pytest
from unittest.mock import AsyncMock, patch


@pytest.mark.asyncio
async def test_detects_expiring_church(expiring_churches, mock_mcp_client):
    """Agent should identify churches expiring within alert window."""
    with patch("agents.subscription_watchdog.mcp_client", mock_mcp_client):
        mock_mcp_client.call_tool = AsyncMock(return_value=expiring_churches)
        from agents.subscription_watchdog import SubscriptionWatchdogAgent
        agent = SubscriptionWatchdogAgent()
        # Should complete without raising
        await agent.run()
        assert mock_mcp_client.call_tool.called


@pytest.mark.asyncio
async def test_no_alerts_for_healthy_churches(mock_mcp_client, sample_church):
    """Agent should not send alerts when no churches are expiring."""
    sample_church["subscription_expiry"] = "2026-12-31"
    with patch("agents.subscription_watchdog.mcp_client", mock_mcp_client):
        mock_mcp_client.call_tool = AsyncMock(return_value=[sample_church])
        from agents.subscription_watchdog import SubscriptionWatchdogAgent
        agent = SubscriptionWatchdogAgent()
        await agent.run()
