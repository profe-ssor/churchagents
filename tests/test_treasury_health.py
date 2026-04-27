"""
Tests for TreasuryHealthAgent.
"""
from unittest.mock import AsyncMock, patch

import pytest


@pytest.mark.asyncio
async def test_flags_stalled_expense():
    stalled = [
        {
            "id": 5,
            "title": "Sound System",
            "amount": 3000,
            "status": "PENDING",
            "hours_pending": 60,
        }
    ]
    churches = [{"id": "550e8400-e29b-41d4-a716-446655440001", "name": "First Church"}]
    with (
        patch(
            "agents.treasury_health.accounts.get_all_churches",
            new_callable=AsyncMock,
            return_value=churches,
        ),
        patch(
            "agents.treasury_health.treasury.get_stalled_expense_requests",
            new_callable=AsyncMock,
            return_value=stalled,
        ),
        patch(
            "agents.treasury_health.treasury.get_large_transactions",
            new_callable=AsyncMock,
            return_value=[],
        ),
    ):
        from agents.treasury_health import TreasuryHealthAgent

        agent = TreasuryHealthAgent()
        await agent.run()


@pytest.mark.asyncio
async def test_anomaly_detection():
    large_tx = [
        {"id": 9, "amount": 9999, "description": "Unknown", "type": "DEBIT"},
    ]
    churches = [{"id": "550e8400-e29b-41d4-a716-446655440002", "name": "Second Church"}]
    with (
        patch(
            "agents.treasury_health.accounts.get_all_churches",
            new_callable=AsyncMock,
            return_value=churches,
        ),
        patch(
            "agents.treasury_health.treasury.get_stalled_expense_requests",
            new_callable=AsyncMock,
            return_value=[],
        ),
        patch(
            "agents.treasury_health.treasury.get_large_transactions",
            new_callable=AsyncMock,
            return_value=large_tx,
        ),
    ):
        from agents.treasury_health import TreasuryHealthAgent

        agent = TreasuryHealthAgent()
        await agent.run()
