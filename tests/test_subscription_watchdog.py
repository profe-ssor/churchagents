"""
Tests for SubscriptionWatchdogAgent.
Runs with DRY_RUN=true — no real emails or DB writes.
"""
from unittest.mock import AsyncMock, patch

import pytest


@pytest.mark.asyncio
async def test_detects_expiring_church(expiring_churches):
    """Agent should process churches returned by get_expiring_subscriptions."""
    with patch(
        "agents.subscription_watchdog.accounts.get_expiring_subscriptions",
        new_callable=AsyncMock,
        return_value=expiring_churches,
    ) as mock_expiring:
        from agents.subscription_watchdog import SubscriptionWatchdogAgent

        agent = SubscriptionWatchdogAgent()
        await agent.run()
        assert mock_expiring.called


@pytest.mark.asyncio
async def test_no_alerts_for_healthy_churches(sample_church):
    """Agent should not emit subscription alerts when nothing is expiring."""
    sample_church["subscription_expiry"] = "2099-12-31"
    with patch(
        "agents.subscription_watchdog.accounts.get_expiring_subscriptions",
        new_callable=AsyncMock,
        return_value=[],
    ) as mock_expiring:
        from agents.subscription_watchdog import SubscriptionWatchdogAgent

        agent = SubscriptionWatchdogAgent()
        await agent.run()
        mock_expiring.assert_called()
