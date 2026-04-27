"""
main.py — Manual agent runner (use this to trigger any agent on demand)
For scheduled runs, use: celery -A scheduler.celery_app worker --beat -Q agents,celery
"""
import asyncio
import argparse
import pprint
from dotenv import load_dotenv

load_dotenv()


def _print_run_summary(result):
    """Agents log at INFO by default (often hidden); always echo the dict return for CLI runs."""
    if result is None:
        return
    print("\n--- agent result ---")
    pprint.pp(result)


async def run(agent_name: str):
    if agent_name == "orchestrator":
        from agents.orchestrator import OrchestratorAgent
        agent = OrchestratorAgent()
        response = await agent.ask(input("Ask the church admin AI: "))
        print(response)

    elif agent_name == "subscription":
        from agents.subscription_watchdog import SubscriptionWatchdogAgent
        agent = SubscriptionWatchdogAgent()
        _print_run_summary(await agent.run())

    elif agent_name == "treasury":
        from agents.treasury_health import TreasuryHealthAgent
        agent = TreasuryHealthAgent()
        _print_run_summary(await agent.run())

    elif agent_name == "members":
        from agents.member_care import MemberCareAgent
        agent = MemberCareAgent()
        _print_run_summary(await agent.run())

    elif agent_name == "departments":
        from agents.department_program import DepartmentProgramAgent
        agent = DepartmentProgramAgent()
        _print_run_summary(await agent.run())

    elif agent_name == "announcements":
        from agents.announcement import AnnouncementAgent
        agent = AnnouncementAgent()
        _print_run_summary(await agent.run())

    elif agent_name == "audit":
        from agents.audit_security import AuditSecurityAgent
        agent = AuditSecurityAgent()
        _print_run_summary(await agent.run())

    elif agent_name == "secretariat":
        from agents.secretariat_agent import SecretariatAgent
        agent = SecretariatAgent()
        _print_run_summary(await agent.run())

    else:
        print(f"Unknown agent: {agent_name}")
        print("Available: orchestrator, subscription, treasury, members, departments, announcements, audit, secretariat")
        print("Interactive orchestrator only. For the dashboard Ask page, run: python orchestrator_server.py")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run a church management agent")
    parser.add_argument("agent", help="Agent to run")
    args = parser.parse_args()
    asyncio.run(run(args.agent))
