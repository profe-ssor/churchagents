# Church Management Agents — 4-Day Build Plan

**Goal:** Build a working multi-agent support system on top of your existing Django church management backend.  
**Project folder:** `/home/professor/projects/churchagents/`  
**Django backend:** `/home/professor/Desktop/church-management-saas-backend/`

---

## What You Are Building

8 AI agents that monitor and act on your church management SaaS:

| # | Agent | Core Job |
|---|-------|---------|
| 1 | OrchestratorAgent | Admin Q&A + route tasks to other agents |
| 2 | SubscriptionWatchdogAgent | Detect expiring/failed subscriptions, send alerts |
| 3 | TreasuryHealthAgent | Monitor finances, flag anomalies, alert on stalled approvals |
| 4 | MemberCareAgent | Birthdays, visitor follow-ups, inactive member alerts |
| 5 | DepartmentProgramAgent | Stalled program approvals, activity reminders |
| 6 | AnnouncementAgent | Pending approvals, weekly digest, publish distribution |
| 7 | AuditSecurityAgent | Failed logins, bulk deletes, permission changes |
| 8 | SecretariatAgent | Transfer letters, meeting minutes, certificates |

---

## MVP Strategy

You cannot build everything perfectly in 4 days. This plan delivers a **working, tested MVP** by splitting work into what is critical vs what can be added after.

| Priority | Label | Meaning |
|----------|-------|---------|
| 🔴 | MUST | MVP blocked without this |
| 🟡 | SHOULD | Important but can do basic version |
| 🟢 | NICE | Polish — add after MVP ships |

---

## Pre-Work (Do This Before Day 1 — Takes ~30 minutes)

### Accounts to create

- [ ] **OpenAI** — go to `platform.openai.com` → API Keys → Create key → set $20 spend limit
- [ ] **LangSmith** — go to `smith.langchain.com` → sign up → create project `church-agents` → copy API key
- [ ] ChromaDB — no account needed, installed via pip
- [ ] Verify Paystack webhook URL in dashboard (`/api/webhooks/paystack/`)

### Save your keys

Create this file — **never commit it to git:**

```
/home/professor/projects/churchagents/.env
```

```env
# Django Backend
DJANGO_BASE_URL=http://localhost:8000
AGENT_JWT_EMAIL=agent-bot@yourdomain.com
AGENT_JWT_PASSWORD=replace-with-strong-password

# OpenAI
OPENAI_API_KEY=sk-proj-...
OPENAI_MODEL=gpt-4.1

# LangSmith
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=ls__...
LANGCHAIN_PROJECT=church-agents

# Vector Store
VECTOR_STORE_TYPE=chroma
CHROMA_PERSIST_DIR=./data/chroma

# Redis
AGENT_MEMORY_REDIS_URL=redis://localhost:6379/2

# Celery
CELERY_BROKER_URL=redis://localhost:6379/0

# Behaviour Thresholds
SUBSCRIPTION_ALERT_DAYS=7,3,1
EXPENSE_STALL_THRESHOLD_HOURS=48
PROGRAM_STALL_THRESHOLD_HOURS=72
MEMBER_INACTIVE_DAYS=30
VISITOR_FOLLOWUP_DAYS=3,7
ANOMALY_TRANSACTION_THRESHOLD=5000
SUPPORT_TEAM_EMAIL=support@yourdomain.com
PLATFORM_ADMIN_EMAIL=admin@yourdomain.com
```

---

---

# DAY 1 — Foundation
**Focus: Backend models + project setup + MCP server skeleton**
**Estimated hours: 6–7 hrs**

---

## DAY 1 — TASK 1: Set Up the Agents Python Project 🔴 MUST

```bash
cd /home/professor/projects/churchagents

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Create requirements.txt
cat > requirements.txt << 'EOF'
openai-agents>=0.0.12
langchain>=0.3.0
langchain-openai>=0.2.0
langgraph>=0.2.0
chromadb>=0.5.0
python-dotenv>=1.0.0
httpx>=0.27.0
redis>=5.0.0
celery>=5.3.0
reportlab>=4.0.0
mcp>=1.0.0
EOF

pip install -r requirements.txt
```

Create the folder structure:

```bash
mkdir -p mcp_server/tools
mkdir -p agents
mkdir -p scheduler
mkdir -p memory
mkdir -p data/chroma
touch mcp_server/__init__.py
touch mcp_server/tools/__init__.py
touch agents/__init__.py
touch scheduler/__init__.py
touch memory/__init__.py
```

Final structure:

```
churchagents/
├── .env                         ← your keys
├── requirements.txt
├── mcp_server/
│   ├── server.py                ← MCP entrypoint
│   ├── auth.py                  ← JWT login to Django
│   ├── client.py                ← Base HTTP client
│   └── tools/
│       ├── accounts.py
│       ├── members.py
│       ├── treasury.py
│       ├── departments.py
│       ├── notifications.py
│       ├── secretariat.py
│       └── agent_infra.py
├── agents/
│   ├── orchestrator.py
│   ├── subscription_watchdog.py
│   ├── treasury_health.py
│   ├── member_care.py
│   ├── department_program.py
│   ├── announcement.py
│   ├── audit_security.py
│   └── secretariat_agent.py
├── scheduler/
│   └── tasks.py
├── memory/
│   └── redis_memory.py
└── data/chroma/                 ← vector store persists here
```

---

## DAY 1 — TASK 2: Add Models to Django Backend 🔴 MUST

Go to your Django backend:

```bash
cd /home/professor/Desktop/church-management-saas-backend
source .venv/bin/activate   # or however you activate your env
```

### Step 1 — Create the `agents` app

```bash
python manage.py startapp agents_app
```

> Name it `agents_app` to avoid clashing with your agents/ Python project folder.

### Step 2 — Add models to `agents_app/models.py`

```python
import uuid
from django.db import models
from accounts.models import Church


class AgentLog(models.Model):
    """Records every action an agent takes — full audit trail"""
    STATUS_CHOICES = [('SUCCESS', 'Success'), ('FAILED', 'Failed'), ('SKIPPED', 'Skipped')]
    TRIGGER_CHOICES = [('SCHEDULED', 'Scheduled'), ('WEBHOOK', 'Webhook'), ('ON_DEMAND', 'On Demand'), ('EVENT', 'Event')]

    agent_name   = models.CharField(max_length=100)
    church       = models.ForeignKey(Church, null=True, blank=True, on_delete=models.SET_NULL)
    action       = models.CharField(max_length=200)
    input_data   = models.JSONField(default=dict)
    output_data  = models.JSONField(default=dict)
    status       = models.CharField(max_length=20, choices=STATUS_CHOICES)
    error        = models.TextField(blank=True)
    duration_ms  = models.IntegerField(default=0)
    triggered_by = models.CharField(max_length=20, choices=TRIGGER_CHOICES)
    created_at   = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']


class AgentTask(models.Model):
    """A task assigned to an agent — tracked from start to finish"""
    STATUS_CHOICES = [('PENDING','Pending'),('RUNNING','Running'),('DONE','Done'),('FAILED','Failed')]
    PRIORITY_CHOICES = [('LOW','Low'),('MEDIUM','Medium'),('HIGH','High'),('URGENT','Urgent')]

    task_id      = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    agent_name   = models.CharField(max_length=100)
    church       = models.ForeignKey(Church, null=True, blank=True, on_delete=models.SET_NULL)
    title        = models.CharField(max_length=300)
    description  = models.TextField(blank=True)
    status       = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    priority     = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='MEDIUM')
    result       = models.JSONField(default=dict)
    created_by   = models.CharField(max_length=100)
    started_at   = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at   = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']


class AgentMemory(models.Model):
    """Conversation history for admin Q&A sessions"""
    session_id   = models.CharField(max_length=100, db_index=True)
    agent_name   = models.CharField(max_length=100)
    church       = models.ForeignKey(Church, null=True, blank=True, on_delete=models.SET_NULL)
    role         = models.CharField(max_length=20)   # user | assistant
    content      = models.TextField()
    created_at   = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']


class AgentAlert(models.Model):
    """Every alert/email/SMS sent by any agent"""
    STATUS_CHOICES = [('SENT','Sent'),('FAILED','Failed'),('SKIPPED','Skipped')]
    CHANNEL_CHOICES = [('EMAIL','Email'),('SMS','SMS'),('IN_APP','In App')]

    agent_name   = models.CharField(max_length=100)
    church       = models.ForeignKey(Church, null=True, blank=True, on_delete=models.SET_NULL)
    alert_type   = models.CharField(max_length=50)
    channel      = models.CharField(max_length=10, choices=CHANNEL_CHOICES)
    recipient    = models.CharField(max_length=200)
    subject      = models.CharField(max_length=300, blank=True)
    body         = models.TextField()
    status       = models.CharField(max_length=10, choices=STATUS_CHOICES)
    sent_at      = models.DateTimeField(auto_now_add=True)


class AgentSchedule(models.Model):
    """Configure and enable/disable each agent's schedule"""
    agent_name   = models.CharField(max_length=100, unique=True)
    is_enabled   = models.BooleanField(default=True)
    cron_expr    = models.CharField(max_length=100)
    last_run     = models.DateTimeField(null=True, blank=True)
    next_run     = models.DateTimeField(null=True, blank=True)
    last_status  = models.CharField(max_length=20, blank=True)
    updated_at   = models.DateTimeField(auto_now=True)
```

### Step 3 — Add `SubscriptionAlert` to `accounts/models.py`

Open `accounts/models.py` and add at the bottom:

```python
class SubscriptionAlert(models.Model):
    """Prevents duplicate expiry emails being sent to the same church"""
    ALERT_TYPES = [('D7','7 Days'),('D3','3 Days'),('D1','1 Day'),('D0','Expired'),('PAYMENT_FAIL','Payment Failed')]

    church       = models.ForeignKey('Church', on_delete=models.CASCADE)
    alert_type   = models.CharField(max_length=20, choices=ALERT_TYPES)
    channel      = models.CharField(max_length=10)   # EMAIL | SMS
    sent_at      = models.DateTimeField(auto_now_add=True)
    acknowledged = models.BooleanField(default=False)

    class Meta:
        unique_together = [['church', 'alert_type']]
```

### Step 4 — Build the `secretariat` app models

Open `secretariat/models.py` (currently empty) and add:

```python
from django.db import models
from accounts.models import Church


class MeetingMinutes(models.Model):
    MEETING_TYPES = [
        ('ELDER_BOARD', 'Elder Board'),
        ('CHURCH_BOARD', 'Church Board'),
        ('COMMITTEE', 'Committee'),
        ('GENERAL', 'General Meeting'),
    ]
    church        = models.ForeignKey(Church, on_delete=models.CASCADE)
    meeting_type  = models.CharField(max_length=20, choices=MEETING_TYPES)
    date          = models.DateField()
    attendees     = models.ManyToManyField('members.Member', blank=True)
    agenda        = models.TextField(blank=True)
    summary       = models.TextField()
    decisions     = models.TextField()
    document      = models.FileField(upload_to='secretariat/minutes/', blank=True)
    recorded_by   = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True)
    created_at    = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date']


class DocumentRequest(models.Model):
    DOC_TYPES = [
        ('TRANSFER', 'Transfer Letter'),
        ('CERTIFICATE', 'Membership Certificate'),
        ('RECOMMENDATION', 'Recommendation Letter'),
        ('BAPTISM', 'Baptism Certificate'),
        ('MARRIAGE', 'Marriage Record'),
    ]
    STATUS = [('PENDING','Pending'),('IN_PROGRESS','In Progress'),('COMPLETED','Completed')]

    church        = models.ForeignKey(Church, on_delete=models.CASCADE)
    member        = models.ForeignKey('members.Member', on_delete=models.CASCADE)
    doc_type      = models.CharField(max_length=20, choices=DOC_TYPES)
    purpose       = models.CharField(max_length=300, blank=True)
    status        = models.CharField(max_length=15, choices=STATUS, default='PENDING')
    requested_by  = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True)
    document      = models.FileField(upload_to='secretariat/docs/', blank=True)
    generated_at  = models.DateTimeField(null=True, blank=True)
    created_at    = models.DateTimeField(auto_now_add=True)


class BaptismRecord(models.Model):
    church      = models.ForeignKey(Church, on_delete=models.CASCADE)
    member      = models.OneToOneField('members.Member', on_delete=models.CASCADE)
    date        = models.DateField()
    officiant   = models.CharField(max_length=200)
    location    = models.CharField(max_length=300, blank=True)
    notes       = models.TextField(blank=True)
    certificate = models.FileField(upload_to='secretariat/baptism/', blank=True)
    created_at  = models.DateTimeField(auto_now_add=True)


class MarriageRecord(models.Model):
    church      = models.ForeignKey(Church, on_delete=models.CASCADE)
    spouse_1    = models.ForeignKey('members.Member', related_name='marriages_1', on_delete=models.CASCADE)
    spouse_2    = models.ForeignKey('members.Member', related_name='marriages_2', on_delete=models.CASCADE)
    date        = models.DateField()
    officiant   = models.CharField(max_length=200)
    location    = models.CharField(max_length=300, blank=True)
    certificate = models.FileField(upload_to='secretariat/marriage/', blank=True)
    created_at  = models.DateTimeField(auto_now_add=True)


class TransferLetter(models.Model):
    church            = models.ForeignKey(Church, on_delete=models.CASCADE)
    member            = models.ForeignKey('members.Member', on_delete=models.CASCADE)
    destination_name  = models.CharField(max_length=300)
    date_issued       = models.DateField(auto_now_add=True)
    issued_by         = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True)
    document          = models.FileField(upload_to='secretariat/transfers/', blank=True)
    delivered         = models.BooleanField(default=False)
    created_at        = models.DateTimeField(auto_now_add=True)


class CorrespondenceLog(models.Model):
    TYPES = [('INCOMING','Incoming'),('OUTGOING','Outgoing')]

    church        = models.ForeignKey(Church, on_delete=models.CASCADE)
    corr_type     = models.CharField(max_length=10, choices=TYPES)
    sender        = models.CharField(max_length=300)
    recipient     = models.CharField(max_length=300)
    subject       = models.CharField(max_length=400)
    date          = models.DateField()
    reference_no  = models.CharField(max_length=100, unique=True)
    document      = models.FileField(upload_to='secretariat/correspondence/', blank=True)
    created_at    = models.DateTimeField(auto_now_add=True)
```

### Step 5 — Register apps and migrate

In `church_saas/settings.py`, add to `INSTALLED_APPS`:

```python
'agents_app',
```

> `secretariat` is already in INSTALLED_APPS.

Run migrations:

```bash
python manage.py makemigrations agents_app
python manage.py makemigrations secretariat
python manage.py makemigrations accounts
python manage.py migrate
```

### Step 6 — Create the agent bot user

```bash
python manage.py shell
```

```python
from accounts.models import User
user = User.objects.create_superuser(
    email='agent-bot@yourdomain.com',
    password='replace-with-strong-password',
    first_name='Church',
    last_name='Agent Bot',
)
user.is_platform_admin = True
user.save()
print("Bot user created:", user.email)
exit()
```

### ✅ Day 1 Checkpoint

- [ ] Python project structure created
- [ ] All packages installed
- [ ] `agents_app` models migrated
- [ ] `secretariat` models migrated
- [ ] `SubscriptionAlert` migrated
- [ ] Agent bot user created in Django
- [ ] `.env` file populated with keys

---

---

# DAY 2 — MCP Server + First Agent
**Focus: Build the MCP server + SubscriptionWatchdogAgent end-to-end**
**Estimated hours: 6–7 hrs**

---

## DAY 2 — TASK 1: Build the MCP Server Base 🔴 MUST

### `mcp_server/auth.py`

```python
"""Gets and refreshes a JWT token from the Django backend"""
import httpx
import os
from dotenv import load_dotenv

load_dotenv()

_token_cache = {"access": None, "refresh": None}


def get_token() -> str:
    if _token_cache["access"]:
        return _token_cache["access"]
    return _login()


def _login() -> str:
    resp = httpx.post(
        f"{os.getenv('DJANGO_BASE_URL')}/api/auth/login/",
        json={
            "email": os.getenv("AGENT_JWT_EMAIL"),
            "password": os.getenv("AGENT_JWT_PASSWORD"),
        },
        timeout=10,
    )
    resp.raise_for_status()
    data = resp.json()
    _token_cache["access"] = data["access"]
    _token_cache["refresh"] = data["refresh"]
    return _token_cache["access"]


def refresh_token() -> str:
    resp = httpx.post(
        f"{os.getenv('DJANGO_BASE_URL')}/api/auth/token/refresh/",
        json={"refresh": _token_cache["refresh"]},
        timeout=10,
    )
    resp.raise_for_status()
    _token_cache["access"] = resp.json()["access"]
    return _token_cache["access"]
```

### `mcp_server/client.py`

```python
"""Base HTTP client — all tools call this"""
import httpx
import os
from mcp_server.auth import get_token, refresh_token


BASE_URL = os.getenv("DJANGO_BASE_URL", "http://localhost:8000")


def get(endpoint: str, params: dict = None) -> dict:
    return _request("GET", endpoint, params=params)


def post(endpoint: str, data: dict = None) -> dict:
    return _request("POST", endpoint, json=data)


def put(endpoint: str, data: dict = None) -> dict:
    return _request("PUT", endpoint, json=data)


def _request(method: str, endpoint: str, **kwargs) -> dict:
    token = get_token()
    headers = {"Authorization": f"Bearer {token}"}
    url = f"{BASE_URL}{endpoint}"

    resp = httpx.request(method, url, headers=headers, timeout=30, **kwargs)

    # Token expired — refresh and retry once
    if resp.status_code == 401:
        token = refresh_token()
        headers["Authorization"] = f"Bearer {token}"
        resp = httpx.request(method, url, headers=headers, timeout=30, **kwargs)

    resp.raise_for_status()
    return resp.json()
```

---

## DAY 2 — TASK 2: Build MCP Tools — Accounts + Notifications 🔴 MUST

### `mcp_server/tools/accounts.py`

```python
from mcp_server.client import get, put


def get_all_churches(plan: str = None) -> dict:
    params = {}
    if plan:
        params["plan"] = plan
    return get("/api/auth/churches/", params=params)


def get_expiring_subscriptions(days: int) -> dict:
    return get("/api/auth/churches/", params={"expires_in_days": days})


def get_church_detail(church_id: int) -> dict:
    return get(f"/api/auth/churches/{church_id}/")


def disable_church_access(church_id: int) -> dict:
    return put(f"/api/auth/churches/{church_id}/platform-access/",
               data={"platform_access_enabled": False})


def reinstate_church_access(church_id: int) -> dict:
    return put(f"/api/auth/churches/{church_id}/platform-access/",
               data={"platform_access_enabled": True})


def get_failed_payments() -> dict:
    return get("/api/payments/", params={"status": "failed"})


def get_audit_logs(church_id: int = None, action: str = None,
                   date_from: str = None, date_to: str = None) -> dict:
    params = {}
    if church_id:
        params["church_id"] = church_id
    if action:
        params["action"] = action
    if date_from:
        params["created_after"] = date_from
    if date_to:
        params["created_before"] = date_to
    return get("/api/activity/", params=params)


def get_locked_accounts(church_id: int = None) -> dict:
    params = {"is_locked": "true"}
    if church_id:
        params["church_id"] = church_id
    return get("/api/auth/users/", params=params)
```

### `mcp_server/tools/notifications.py`

```python
from mcp_server.client import post


def send_email(to: str, subject: str, body: str, church_id: int) -> dict:
    return post("/api/notifications/send-email/", {
        "recipient_email": to,
        "subject": subject,
        "message": body,
        "church_id": church_id,
    })


def send_sms(to: str, message: str, church_id: int) -> dict:
    return post("/api/notifications/send-sms/", {
        "recipient_phone": to,
        "message": message,
        "church_id": church_id,
    })


def send_bulk(church_id: int, target_group: str, subject: str,
              message: str, channel: str = "EMAIL") -> dict:
    return post("/api/notifications/send-bulk/", {
        "church_id": church_id,
        "target_group": target_group,
        "subject": subject,
        "message": message,
        "channel": channel,
    })
```

---

## DAY 2 — TASK 3: Build SubscriptionWatchdogAgent 🔴 MUST

This is your most important agent — do it first, test it fully.

### `agents/subscription_watchdog.py`

```python
"""
SubscriptionWatchdogAgent
- Runs daily at 7:00 AM
- Detects: trial expiring in 7/3/1 days, expired, payment failed
- Sends tiered email alerts to church admins
- Disables access for expired churches
"""
import os
from datetime import datetime, timedelta
from openai import OpenAI
from agents import Agent, Runner, tool
from dotenv import load_dotenv

from mcp_server.tools.accounts import (
    get_expiring_subscriptions, get_church_detail,
    disable_church_access, get_failed_payments
)
from mcp_server.tools.notifications import send_email
from mcp_server.client import get, post

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


# ── Email templates ──────────────────────────────────────────────

TEMPLATES = {
    "D7": {
        "subject": "Your trial expires in 7 days — upgrade now",
        "body": """Dear {admin_name},

Your church account "{church_name}" on OpenDoor is on a TRIAL plan that expires in 7 days on {expiry_date}.

To continue using the platform without interruption, please upgrade your plan.

Upgrade here: {frontend_url}/billing

If you have questions, reply to this email or contact our support team.

Best regards,
OpenDoor Support Team
"""
    },
    "D3": {
        "subject": "Action needed: your OpenDoor plan expires in 3 days",
        "body": """Dear {admin_name},

This is an urgent reminder that your church "{church_name}" access expires in 3 days on {expiry_date}.

Please upgrade immediately to avoid losing access to your member data, financials, and communications.

Upgrade here: {frontend_url}/billing

Best regards,
OpenDoor Support Team
"""
    },
    "D1": {
        "subject": "FINAL NOTICE: Access expires tomorrow",
        "body": """Dear {admin_name},

Your OpenDoor account for "{church_name}" expires TOMORROW on {expiry_date}.

After expiry your access will be suspended. All your data is safe and will be restored immediately on payment.

Upgrade now: {frontend_url}/billing

Best regards,
OpenDoor Support Team
"""
    },
    "D0": {
        "subject": "Your OpenDoor account has been suspended",
        "body": """Dear {admin_name},

Your church account "{church_name}" subscription has expired and access has been suspended.

Your data is safe. To restore access immediately, please renew your subscription:

Renew here: {frontend_url}/billing

Best regards,
OpenDoor Support Team
"""
    },
    "PAYMENT_FAIL": {
        "subject": "Payment failed — please update your billing info",
        "body": """Dear {admin_name},

We were unable to process the payment for your "{church_name}" OpenDoor subscription.

Please update your payment method to avoid service interruption:

Update billing: {frontend_url}/billing

Best regards,
OpenDoor Support Team
"""
    },
}


def _alert_already_sent(church_id: int, alert_type: str) -> bool:
    """Check if we already sent this alert to avoid duplicates"""
    try:
        result = get("/api/agents/alerts/", params={
            "church_id": church_id,
            "alert_type": alert_type,
        })
        return result.get("count", 0) > 0
    except Exception:
        return False


def _log_alert_sent(church_id: int, alert_type: str, recipient: str) -> None:
    try:
        post("/api/agents/alerts/", {
            "agent_name": "SubscriptionWatchdogAgent",
            "church_id": church_id,
            "alert_type": alert_type,
            "channel": "EMAIL",
            "recipient": recipient,
            "subject": TEMPLATES.get(alert_type, {}).get("subject", ""),
            "body": "",
            "status": "SENT",
        })
    except Exception:
        pass


def _send_alert(church: dict, alert_type: str) -> None:
    """Send the correct email for this alert type"""
    church_id = church["id"]
    admin_email = church.get("admin_email") or church.get("email", "")
    admin_name = church.get("admin_name", "Admin")
    church_name = church.get("name", "Your Church")
    expiry_date = church.get("subscription_ends_at", "soon")
    frontend_url = os.getenv("DJANGO_BASE_URL", "").replace(":8000", ":3000")

    if _alert_already_sent(church_id, alert_type):
        print(f"  [SKIP] Alert {alert_type} already sent to {church_name}")
        return

    template = TEMPLATES[alert_type]
    body = template["body"].format(
        admin_name=admin_name,
        church_name=church_name,
        expiry_date=expiry_date,
        frontend_url=frontend_url,
    )

    try:
        send_email(
            to=admin_email,
            subject=template["subject"],
            body=body,
            church_id=church_id,
        )
        _log_alert_sent(church_id, alert_type, admin_email)
        print(f"  [SENT] {alert_type} → {church_name} ({admin_email})")
    except Exception as e:
        print(f"  [ERROR] Failed to send {alert_type} to {church_name}: {e}")


def run() -> dict:
    """Main entry point — called by Celery Beat every morning"""
    print(f"\n[SubscriptionWatchdogAgent] Starting run at {datetime.now()}")
    results = {"sent": 0, "skipped": 0, "errors": 0}

    # Check 7-day expiries
    for days, label in [(7, "D7"), (3, "D3"), (1, "D1")]:
        try:
            data = get_expiring_subscriptions(days)
            churches = data.get("results", data) if isinstance(data, dict) else data
            for church in churches:
                _send_alert(church, label)
                results["sent"] += 1
        except Exception as e:
            print(f"  [ERROR] {label} scan failed: {e}")
            results["errors"] += 1

    # Check already-expired churches
    try:
        expired = get("/api/auth/churches/", params={"subscription_expired": "true"})
        for church in expired.get("results", []):
            _send_alert(church, "D0")
            try:
                disable_church_access(church["id"])
                print(f"  [DISABLED] {church.get('name')}")
            except Exception as e:
                print(f"  [ERROR] Could not disable {church.get('name')}: {e}")
    except Exception as e:
        print(f"  [ERROR] Expired scan failed: {e}")

    # Check failed payments
    try:
        failed = get_failed_payments()
        for payment in failed.get("results", []):
            church = get_church_detail(payment["church"])
            _send_alert(church, "PAYMENT_FAIL")
    except Exception as e:
        print(f"  [ERROR] Payment failure scan failed: {e}")

    print(f"[SubscriptionWatchdogAgent] Done. Results: {results}\n")
    return results


if __name__ == "__main__":
    run()
```

### Test it manually:

```bash
cd /home/professor/projects/churchagents
source .venv/bin/activate
python -c "from agents.subscription_watchdog import run; run()"
```

### ✅ Day 2 Checkpoint

- [ ] `mcp_server/auth.py` written and tested (can log in to Django)
- [ ] `mcp_server/client.py` written
- [ ] `mcp_server/tools/accounts.py` written
- [ ] `mcp_server/tools/notifications.py` written
- [ ] `SubscriptionWatchdogAgent` written and manually tested
- [ ] At least one test email delivered successfully

---

---

# DAY 3 — Core Agents
**Focus: OrchestratorAgent + TreasuryHealthAgent + MemberCareAgent**
**Estimated hours: 7–8 hrs**

---

## DAY 3 — TASK 1: Build Remaining MCP Tool Files 🔴 MUST

### `mcp_server/tools/members.py`

```python
from mcp_server.client import get, post


def get_members(church_id: int, **filters) -> dict:
    params = {"church_id": church_id, **filters}
    return get("/api/members/", params=params)


def get_member_profile(member_id: int) -> dict:
    return get(f"/api/members/{member_id}/")


def get_members_with_birthdays(date_str: str) -> dict:
    return get("/api/members/", params={"birthday": date_str})


def get_inactive_members(church_id: int, days: int = 30) -> dict:
    return get("/api/members/", params={"church_id": church_id, "inactive_days": days})


def get_new_members(church_id: int, joined_after: str) -> dict:
    return get("/api/members/", params={"church_id": church_id, "joined_after": joined_after})


def get_visitors(church_id: int) -> dict:
    return get("/api/members/visitors/", params={"church_id": church_id})


def get_member_stats(church_id: int) -> dict:
    return get("/api/analytics/", params={"church_id": church_id})
```

### `mcp_server/tools/treasury.py`

```python
from mcp_server.client import get, post


def get_treasury_stats(church_id: int) -> dict:
    return get("/api/treasury/statistics/", params={"church_id": church_id})


def get_income_transactions(church_id: int, date_from: str = None, date_to: str = None) -> dict:
    params = {"church_id": church_id}
    if date_from:
        params["date_from"] = date_from
    if date_to:
        params["date_to"] = date_to
    return get("/api/treasury/income-transactions/", params=params)


def get_expense_transactions(church_id: int, **filters) -> dict:
    return get("/api/treasury/expense-transactions/", params={"church_id": church_id, **filters})


def get_stalled_expense_requests(church_id: int, hours: int = 48) -> dict:
    return get("/api/treasury/expense-requests/",
               params={"church_id": church_id, "stalled_hours": hours})


def get_assets(church_id: int) -> dict:
    return get("/api/treasury/assets/", params={"church_id": church_id})
```

### `mcp_server/tools/departments.py`

```python
from mcp_server.client import get, post


def get_departments(church_id: int) -> dict:
    return get("/api/departments/", params={"church_id": church_id})


def get_programs(church_id: int) -> dict:
    return get("/api/programs/", params={"church_id": church_id})


def get_stalled_programs(church_id: int, hours: int = 72) -> dict:
    return get("/api/programs/", params={"church_id": church_id, "stalled_hours": hours})


def get_upcoming_activities(church_id: int, days: int = 1) -> dict:
    return get("/api/departments/activities/", params={"church_id": church_id, "days_ahead": days})


def get_pending_announcements(church_id: int) -> dict:
    return get("/api/announcements/", params={"church_id": church_id, "status": "PENDING_REVIEW"})


def get_published_announcements(church_id: int) -> dict:
    return get("/api/announcements/published/", params={"church_id": church_id})
```

---

## DAY 3 — TASK 2: Build TreasuryHealthAgent 🔴 MUST

### `agents/treasury_health.py`

```python
"""
TreasuryHealthAgent
- Runs weekly on Monday 8:00 AM
- Flags stalled expense requests > 48h
- Detects budget overruns
- Sends alerts to treasurers
"""
import os
from datetime import datetime
from dotenv import load_dotenv

from mcp_server.tools.treasury import (
    get_treasury_stats, get_stalled_expense_requests, get_assets
)
from mcp_server.tools.accounts import get_all_churches
from mcp_server.tools.notifications import send_email

load_dotenv()

STALL_HOURS = int(os.getenv("EXPENSE_STALL_THRESHOLD_HOURS", 48))
ANOMALY_THRESHOLD = float(os.getenv("ANOMALY_TRANSACTION_THRESHOLD", 5000))


def _check_stalled_requests(church: dict) -> int:
    church_id = church["id"]
    church_name = church.get("name", "Unknown")
    treasurer_email = church.get("treasurer_email", church.get("admin_email", ""))

    try:
        result = get_stalled_expense_requests(church_id, STALL_HOURS)
        stalled = result.get("results", [])

        for req in stalled:
            req_title = req.get("title", "Expense Request")
            req_amount = req.get("amount", 0)
            stage = req.get("approval_stage", "unknown stage")

            send_email(
                to=treasurer_email,
                subject=f"Action needed: Expense request pending over {STALL_HOURS}h",
                body=f"""Dear Treasurer,

The following expense request for {church_name} has been waiting for approval for over {STALL_HOURS} hours:

Request: {req_title}
Amount: GHS {req_amount}
Stuck at: {stage}

Please review and take action: {os.getenv('DJANGO_BASE_URL', '')}/treasury/expense-requests/

Best regards,
OpenDoor Agent System
""",
                church_id=church_id,
            )
            print(f"  [ALERT] Stalled expense sent for {church_name}: {req_title}")

        return len(stalled)
    except Exception as e:
        print(f"  [ERROR] Stall check for {church_name}: {e}")
        return 0


def run() -> dict:
    print(f"\n[TreasuryHealthAgent] Starting run at {datetime.now()}")
    total_stalled = 0

    try:
        all_churches = get_all_churches()
        churches = all_churches.get("results", all_churches) if isinstance(all_churches, dict) else all_churches

        for church in churches:
            if not church.get("platform_access_enabled", True):
                continue
            stalled = _check_stalled_requests(church)
            total_stalled += stalled

    except Exception as e:
        print(f"  [ERROR] {e}")

    print(f"[TreasuryHealthAgent] Done. Stalled alerts sent: {total_stalled}\n")
    return {"stalled_alerts": total_stalled}


if __name__ == "__main__":
    run()
```

---

## DAY 3 — TASK 3: Build MemberCareAgent 🔴 MUST

### `agents/member_care.py`

```python
"""
MemberCareAgent
- Daily 8:00 AM: birthday greetings + visitor follow-ups
- Sunday 8:00 PM: inactive member scan
- Event: new member created → immediate welcome email
"""
import os
from datetime import datetime, date
from dotenv import load_dotenv

from mcp_server.tools.members import (
    get_members_with_birthdays, get_inactive_members,
    get_visitors, get_new_members
)
from mcp_server.tools.notifications import send_email

load_dotenv()

INACTIVE_DAYS = int(os.getenv("MEMBER_INACTIVE_DAYS", 30))
FRONTEND_URL = os.getenv("DJANGO_BASE_URL", "").replace(":8000", ":3000")


def send_birthday_greetings(church_id: int) -> int:
    today = date.today().strftime("%m-%d")
    try:
        result = get_members_with_birthdays(today)
        members = result.get("results", [])
        for member in members:
            email = member.get("email", "")
            name = member.get("first_name", "Friend")
            church_name = member.get("church_name", "your church")
            if not email:
                continue
            send_email(
                to=email,
                subject=f"Happy Birthday {name}! 🎂",
                body=f"""Dear {name},

On behalf of everyone at {church_name}, we wish you a very Happy Birthday!

May this day be filled with joy, love and God's blessings.

With love,
{church_name} Family
""",
                church_id=church_id,
            )
            print(f"  [BDAY] Sent to {name} ({email})")
        return len(members)
    except Exception as e:
        print(f"  [ERROR] Birthday scan: {e}")
        return 0


def follow_up_visitors(church_id: int) -> int:
    try:
        result = get_visitors(church_id)
        visitors = result.get("results", [])
        sent = 0
        for visitor in visitors:
            email = visitor.get("email", "")
            name = visitor.get("first_name", "Friend")
            visit_date = visitor.get("visit_date", "recently")
            if not email:
                continue
            send_email(
                to=email,
                subject="It was great to meet you!",
                body=f"""Dear {name},

Thank you for visiting us {visit_date}. We truly enjoyed having you with us.

We would love to have you join our church family. Feel free to reach out anytime.

God bless you,
The Church Family
""",
                church_id=church_id,
            )
            sent += 1
        return sent
    except Exception as e:
        print(f"  [ERROR] Visitor follow-up: {e}")
        return 0


def alert_inactive_members(church_id: int) -> int:
    try:
        result = get_inactive_members(church_id, INACTIVE_DAYS)
        members = result.get("results", [])
        for member in members:
            email = member.get("email", "")
            name = member.get("first_name", "Friend")
            if not email:
                continue
            send_email(
                to=email,
                subject="We miss you!",
                body=f"""Dear {name},

We have not seen you in a while and wanted you to know that you are missed!

We would love to reconnect with you. Please come back and be part of our family again.

With love,
Your Church Family
""",
                church_id=church_id,
            )
        return len(members)
    except Exception as e:
        print(f"  [ERROR] Inactive scan: {e}")
        return 0


def run_daily(church_id: int = None) -> dict:
    """Called every morning at 8:00 AM"""
    print(f"\n[MemberCareAgent] Daily run at {datetime.now()}")

    from mcp_server.tools.accounts import get_all_churches
    if church_id:
        church_ids = [church_id]
    else:
        data = get_all_churches()
        churches = data.get("results", data)
        church_ids = [c["id"] for c in churches if c.get("platform_access_enabled", True)]

    total_bday = total_visitor = 0
    for cid in church_ids:
        total_bday += send_birthday_greetings(cid)
        total_visitor += follow_up_visitors(cid)

    print(f"[MemberCareAgent] Done. Birthdays: {total_bday}, Visitor follow-ups: {total_visitor}\n")
    return {"birthdays": total_bday, "visitor_followups": total_visitor}


def run_weekly_inactive(church_id: int = None) -> dict:
    """Called every Sunday evening"""
    print(f"\n[MemberCareAgent] Inactive scan at {datetime.now()}")

    from mcp_server.tools.accounts import get_all_churches
    if church_id:
        church_ids = [church_id]
    else:
        data = get_all_churches()
        churches = data.get("results", data)
        church_ids = [c["id"] for c in churches if c.get("platform_access_enabled", True)]

    total = sum(alert_inactive_members(cid) for cid in church_ids)
    print(f"[MemberCareAgent] Inactive alerts sent: {total}\n")
    return {"inactive_alerts": total}


if __name__ == "__main__":
    run_daily()
```

---

## DAY 3 — TASK 4: Build OrchestratorAgent 🔴 MUST

### `agents/orchestrator.py`

```python
"""
OrchestratorAgent
- Answers admin questions about the church system
- Routes tasks to specialist agents
- Delivers daily briefing
"""
import os
from openai import OpenAI
from dotenv import load_dotenv

from mcp_server.tools.accounts import get_all_churches, get_church_detail
from mcp_server.tools.members import get_member_stats
from mcp_server.tools.treasury import get_treasury_stats
from mcp_server.client import get

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1")

SYSTEM_PROMPT = """You are the OpenDoor Church Management AI Assistant.
You help platform administrators manage their church SaaS platform.
You have access to live data from the church management system.
Be concise, professional, and helpful.
When asked about numbers or data, always use the real data provided to you.
Never make up information."""


def _build_context(question: str) -> str:
    """Fetch relevant live data to include in the prompt"""
    context_parts = []

    try:
        churches = get_all_churches()
        total = churches.get("count", len(churches.get("results", [])))
        context_parts.append(f"Total churches on platform: {total}")
    except Exception:
        pass

    try:
        expiring = get("/api/auth/churches/", params={"expires_in_days": 7})
        exp_count = expiring.get("count", 0)
        if exp_count > 0:
            context_parts.append(f"Churches expiring in 7 days: {exp_count}")
    except Exception:
        pass

    return "\n".join(context_parts)


def ask(question: str, session_id: str = "default", church_id: int = None) -> str:
    """Main Q&A interface — admin asks a question, gets a response"""

    # Build context from live data
    context = _build_context(question)

    # Load conversation history from memory
    history = _load_memory(session_id)

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    if context:
        messages.append({"role": "system", "content": f"Current platform data:\n{context}"})
    messages.extend(history)
    messages.append({"role": "user", "content": question})

    response = client.chat.completions.create(
        model=MODEL,
        messages=messages,
        temperature=0.3,
    )
    answer = response.choices[0].message.content

    # Save to memory
    _save_memory(session_id, "user", question)
    _save_memory(session_id, "assistant", answer)

    return answer


def daily_briefing() -> str:
    """Generate morning briefing for platform admin"""
    try:
        churches = get_all_churches()
        expiring_7 = get("/api/auth/churches/", params={"expires_in_days": 7})
        failed_payments = get("/api/payments/", params={"status": "failed"})

        briefing_data = f"""
Churches total: {churches.get('count', '?')}
Expiring in 7 days: {expiring_7.get('count', 0)}
Failed payments: {failed_payments.get('count', 0)}
"""
        return ask(
            f"Generate a concise morning briefing for the platform admin based on this data: {briefing_data}",
            session_id="daily-briefing"
        )
    except Exception as e:
        return f"Could not generate briefing: {e}"


def _load_memory(session_id: str) -> list:
    try:
        result = get("/api/agents/memory/", params={"session_id": session_id})
        entries = result.get("results", [])
        return [{"role": e["role"], "content": e["content"]} for e in entries[-10:]]
    except Exception:
        return []


def _save_memory(session_id: str, role: str, content: str) -> None:
    try:
        from mcp_server.client import post
        post("/api/agents/memory/", {
            "session_id": session_id,
            "agent_name": "OrchestratorAgent",
            "role": role,
            "content": content,
        })
    except Exception:
        pass


if __name__ == "__main__":
    print(daily_briefing())
    while True:
        q = input("\nAdmin question: ").strip()
        if q.lower() in ("exit", "quit"):
            break
        print("\n" + ask(q))
```

### ✅ Day 3 Checkpoint

- [ ] All MCP tool files written (members, treasury, departments)
- [ ] `TreasuryHealthAgent` written and manually tested
- [ ] `MemberCareAgent` written and manually tested
- [ ] `OrchestratorAgent` written — tested with at least 3 admin questions
- [ ] Conversation memory saving/loading works

---

---

# DAY 4 — Remaining Agents + Scheduler
**Focus: 4 remaining agents + Celery Beat + end-to-end test**
**Estimated hours: 7–8 hrs**

---

## DAY 4 — TASK 1: Build DepartmentProgramAgent 🟡 SHOULD

### `agents/department_program.py`

```python
"""
DepartmentProgramAgent
- Daily: scan for programs stalled > 72h → notify department head
- Daily: send reminders for activities happening tomorrow
"""
import os
from datetime import datetime
from dotenv import load_dotenv

from mcp_server.tools.departments import get_stalled_programs, get_upcoming_activities
from mcp_server.tools.notifications import send_email
from mcp_server.tools.accounts import get_all_churches

load_dotenv()

STALL_HOURS = int(os.getenv("PROGRAM_STALL_THRESHOLD_HOURS", 72))


def check_stalled_programs(church_id: int) -> int:
    try:
        result = get_stalled_programs(church_id, STALL_HOURS)
        programs = result.get("results", [])
        for prog in programs:
            head_email = prog.get("department_head_email", "")
            if not head_email:
                continue
            send_email(
                to=head_email,
                subject=f"Program approval needed: {prog.get('title', 'Program')}",
                body=f"""Dear Department Head,

The program "{prog.get('title')}" has been waiting for approval for over {STALL_HOURS} hours.

Current stage: {prog.get('approval_stage', 'Pending')}
Department: {prog.get('department_name', '')}

Please review and take action to keep things moving.

Best regards,
OpenDoor Agent System
""",
                church_id=church_id,
            )
            print(f"  [DEPT] Stall alert sent for program: {prog.get('title')}")
        return len(programs)
    except Exception as e:
        print(f"  [ERROR] Program stall check: {e}")
        return 0


def send_activity_reminders(church_id: int) -> int:
    try:
        result = get_upcoming_activities(church_id, days=1)
        activities = result.get("results", [])
        for act in activities:
            organiser_email = act.get("organiser_email", "")
            if not organiser_email:
                continue
            send_email(
                to=organiser_email,
                subject=f"Reminder: '{act.get('title')}' is tomorrow",
                body=f"""Dear {act.get('organiser_name', 'Organiser')},

This is a reminder that the following activity is scheduled for tomorrow:

Activity: {act.get('title')}
Date: {act.get('date')}
Time: {act.get('time', 'TBD')}
Location: {act.get('location', 'TBD')}

Please ensure all preparations are in order.

Best regards,
OpenDoor Agent System
""",
                church_id=church_id,
            )
        return len(activities)
    except Exception as e:
        print(f"  [ERROR] Activity reminders: {e}")
        return 0


def run() -> dict:
    print(f"\n[DepartmentProgramAgent] Starting run at {datetime.now()}")
    data = get_all_churches()
    churches = data.get("results", data)
    total_stall = total_remind = 0
    for church in churches:
        if not church.get("platform_access_enabled", True):
            continue
        total_stall += check_stalled_programs(church["id"])
        total_remind += send_activity_reminders(church["id"])
    print(f"[DepartmentProgramAgent] Done. Stall: {total_stall}, Reminders: {total_remind}\n")
    return {"stalled": total_stall, "reminders": total_remind}
```

---

## DAY 4 — TASK 2: Build AnnouncementAgent 🟡 SHOULD

### `agents/announcement.py`

```python
"""
AnnouncementAgent
- Every 6h: check pending announcements > 24h → nudge approver
- Sunday 8AM: weekly digest to all churches
"""
import os
from datetime import datetime
from dotenv import load_dotenv

from mcp_server.tools.departments import get_pending_announcements, get_published_announcements
from mcp_server.tools.notifications import send_bulk
from mcp_server.tools.accounts import get_all_churches

load_dotenv()


def check_pending_announcements(church_id: int) -> int:
    try:
        result = get_pending_announcements(church_id)
        pending = result.get("results", [])
        for ann in pending:
            approver_email = ann.get("approver_email", "")
            if not approver_email:
                continue
            from mcp_server.tools.notifications import send_email
            send_email(
                to=approver_email,
                subject=f"Approval needed: '{ann.get('title')}'",
                body=f"""Dear {ann.get('approver_name', 'Approver')},

The following announcement is waiting for your review:

Title: {ann.get('title')}
Category: {ann.get('category', 'General')}
Priority: {ann.get('priority', 'MEDIUM')}
Submitted: {ann.get('created_at', '')}

Please review here: {os.getenv('DJANGO_BASE_URL', '')}/announcements/

Best regards,
OpenDoor Agent System
""",
                church_id=church_id,
            )
        return len(pending)
    except Exception as e:
        print(f"  [ERROR] Pending announcements check: {e}")
        return 0


def send_weekly_digest(church_id: int) -> None:
    try:
        result = get_published_announcements(church_id)
        announcements = result.get("results", [])
        if not announcements:
            return
        digest = "\n\n".join([
            f"• {a.get('title', '')}\n  {a.get('content', '')[:100]}..."
            for a in announcements[:5]
        ])
        send_bulk(
            church_id=church_id,
            target_group="ALL_MEMBERS",
            subject="This week's church announcements",
            message=f"Here are this week's announcements:\n\n{digest}",
            channel="EMAIL",
        )
        print(f"  [DIGEST] Weekly digest sent for church {church_id}")
    except Exception as e:
        print(f"  [ERROR] Weekly digest: {e}")


def run_check() -> dict:
    print(f"\n[AnnouncementAgent] Pending check at {datetime.now()}")
    data = get_all_churches()
    churches = data.get("results", data)
    total = sum(check_pending_announcements(c["id"]) for c in churches
                if c.get("platform_access_enabled", True))
    print(f"[AnnouncementAgent] Nudges sent: {total}\n")
    return {"nudges": total}


def run_weekly_digest_all() -> None:
    print(f"\n[AnnouncementAgent] Weekly digest at {datetime.now()}")
    data = get_all_churches()
    churches = data.get("results", data)
    for church in churches:
        if church.get("platform_access_enabled", True):
            send_weekly_digest(church["id"])
```

---

## DAY 4 — TASK 3: Build AuditSecurityAgent 🟡 SHOULD

### `agents/audit_security.py`

```python
"""
AuditSecurityAgent
- Nightly 1AM: scan audit logs for suspicious events
- Real-time: account lockout alert
"""
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv

from mcp_server.tools.accounts import get_audit_logs, get_locked_accounts
from mcp_server.tools.notifications import send_email

load_dotenv()

SUPPORT_EMAIL = os.getenv("SUPPORT_TEAM_EMAIL", "")
BULK_THRESHOLD = int(os.getenv("BULK_DELETE_THRESHOLD", 10))


def check_locked_accounts() -> int:
    try:
        result = get_locked_accounts()
        locked = result.get("results", [])
        if locked:
            names = ", ".join([u.get("email", "") for u in locked[:5]])
            send_email(
                to=SUPPORT_EMAIL,
                subject=f"Security Alert: {len(locked)} account(s) locked",
                body=f"""Security Alert from OpenDoor Agent System

{len(locked)} user account(s) have been locked due to failed login attempts:

{names}
{"...and more" if len(locked) > 5 else ""}

Date: {datetime.now().strftime("%Y-%m-%d %H:%M")}

Please review in the admin panel.
""",
                church_id=None,
            )
            print(f"  [SECURITY] Lockout alert sent: {len(locked)} accounts")
        return len(locked)
    except Exception as e:
        print(f"  [ERROR] Lockout check: {e}")
        return 0


def scan_audit_logs() -> dict:
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    today = datetime.now().strftime("%Y-%m-%d")
    suspicious = []

    for action in ["DELETE", "PERMISSION_CHANGE", "BULK_DELETE"]:
        try:
            result = get_audit_logs(action=action, date_from=yesterday, date_to=today)
            entries = result.get("results", [])
            if entries:
                suspicious.extend(entries)
        except Exception:
            pass

    if suspicious:
        summary = "\n".join([
            f"- {e.get('action')} by {e.get('user_email', '?')} on {e.get('created_at', '?')}"
            for e in suspicious[:10]
        ])
        send_email(
            to=SUPPORT_EMAIL,
            subject=f"Nightly Security Report: {len(suspicious)} suspicious event(s)",
            body=f"""Nightly Security Scan — {today}

{len(suspicious)} suspicious event(s) detected in the last 24 hours:

{summary}

Please review your audit logs for full details.

OpenDoor Agent System
""",
            church_id=None,
        )
        print(f"  [SECURITY] Nightly report sent: {len(suspicious)} events")

    return {"suspicious_events": len(suspicious)}


def run() -> dict:
    print(f"\n[AuditSecurityAgent] Starting nightly scan at {datetime.now()}")
    locked = check_locked_accounts()
    scan_result = scan_audit_logs()
    print(f"[AuditSecurityAgent] Done.\n")
    return {"locked": locked, **scan_result}
```

---

## DAY 4 — TASK 4: Build SecretariatAgent (MVP Version) 🟡 SHOULD

### `agents/secretariat_agent.py`

```python
"""
SecretariatAgent (MVP)
- Generates transfer letters on demand
- Weekly reminder for pending document requests
- Logs meeting minutes
"""
import os
from datetime import datetime
from dotenv import load_dotenv
from openai import OpenAI

from mcp_server.tools.members import get_member_profile
from mcp_server.tools.notifications import send_email
from mcp_server.client import get, post

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1")


def generate_transfer_letter(member_id: int, destination_church: str,
                              church_id: int, issued_by: str) -> str:
    """Generate a formal transfer letter using GPT-4.1"""
    member = get_member_profile(member_id)
    name = f"{member.get('first_name', '')} {member.get('last_name', '')}".strip()
    church_name = member.get("church_name", "Our Church")
    today = datetime.now().strftime("%B %d, %Y")

    prompt = f"""Write a formal church transfer letter with these details:
Member name: {name}
From church: {church_name}
To church: {destination_church}
Date: {today}
Issued by: {issued_by}
The letter should confirm their membership, baptism status if known, and wish them well.
Keep it formal, under 200 words."""

    response = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
    )
    letter = response.choices[0].message.content

    # Save the transfer letter record
    try:
        post("/api/secretariat/transfer-letters/", {
            "church": church_id,
            "member": member_id,
            "destination_name": destination_church,
            "issued_by_name": issued_by,
        })
    except Exception:
        pass

    return letter


def check_pending_requests(church_id: int) -> int:
    try:
        result = get("/api/secretariat/document-requests/",
                     params={"church_id": church_id, "status": "PENDING"})
        pending = result.get("results", [])
        if pending:
            admin_email = ""
            try:
                from mcp_server.tools.accounts import get_church_detail
                church = get_church_detail(church_id)
                admin_email = church.get("admin_email", "")
            except Exception:
                pass

            if admin_email:
                items = "\n".join([
                    f"- {r.get('member_name', '?')}: {r.get('doc_type', '?')} (since {r.get('created_at', '?')[:10]})"
                    for r in pending
                ])
                send_email(
                    to=admin_email,
                    subject=f"{len(pending)} document request(s) pending",
                    body=f"""Dear Admin,

The following document requests are waiting to be processed:

{items}

Please action them here: {os.getenv('DJANGO_BASE_URL', '')}/secretariat/

Best regards,
OpenDoor Agent System
""",
                    church_id=church_id,
                )
        return len(pending)
    except Exception as e:
        print(f"  [ERROR] Pending docs check: {e}")
        return 0


def run() -> dict:
    print(f"\n[SecretariatAgent] Weekly reminders at {datetime.now()}")
    from mcp_server.tools.accounts import get_all_churches
    data = get_all_churches()
    churches = data.get("results", data)
    total = sum(check_pending_requests(c["id"]) for c in churches
                if c.get("platform_access_enabled", True))
    print(f"[SecretariatAgent] Done. Reminders: {total}\n")
    return {"reminders": total}
```

---

## DAY 4 — TASK 5: Set Up Celery Beat Scheduler 🔴 MUST

### `scheduler/tasks.py`

```python
"""
Celery Beat tasks — triggers all agents on schedule.
Add this to your CELERY_BEAT_SCHEDULE in church_saas/settings.py
OR run standalone from the agents project.
"""
from celery import Celery
from celery.schedules import crontab
import os
from dotenv import load_dotenv

load_dotenv()

app = Celery("church_agents", broker=os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0"))

app.conf.beat_schedule = {
    # Orchestrator — daily briefing 7:00 AM
    "orchestrator-daily-briefing": {
        "task": "scheduler.tasks.run_orchestrator_briefing",
        "schedule": crontab(hour=7, minute=0),
    },
    # Subscription Watchdog — daily 7:00 AM
    "subscription-watchdog-daily": {
        "task": "scheduler.tasks.run_subscription_watchdog",
        "schedule": crontab(hour=7, minute=5),
    },
    # Treasury Health — Monday 8:00 AM
    "treasury-health-weekly": {
        "task": "scheduler.tasks.run_treasury_health",
        "schedule": crontab(hour=8, minute=0, day_of_week=1),
    },
    # Member Care birthdays — daily 8:00 AM
    "member-care-daily": {
        "task": "scheduler.tasks.run_member_care_daily",
        "schedule": crontab(hour=8, minute=0),
    },
    # Member Care inactive — Sunday 8:00 PM
    "member-care-inactive": {
        "task": "scheduler.tasks.run_member_care_inactive",
        "schedule": crontab(hour=20, minute=0, day_of_week=0),
    },
    # Department Program — daily 9:00 AM
    "dept-program-daily": {
        "task": "scheduler.tasks.run_dept_program",
        "schedule": crontab(hour=9, minute=0),
    },
    # Announcement check — every 6 hours
    "announcement-check": {
        "task": "scheduler.tasks.run_announcement_check",
        "schedule": crontab(minute=0, hour="*/6"),
    },
    # Announcement weekly digest — Sunday 8:00 AM
    "announcement-digest": {
        "task": "scheduler.tasks.run_announcement_digest",
        "schedule": crontab(hour=8, minute=0, day_of_week=0),
    },
    # Audit Security — nightly 1:00 AM
    "audit-security-nightly": {
        "task": "scheduler.tasks.run_audit_security",
        "schedule": crontab(hour=1, minute=0),
    },
    # Secretariat reminders — Monday 9:00 AM
    "secretariat-weekly": {
        "task": "scheduler.tasks.run_secretariat",
        "schedule": crontab(hour=9, minute=5, day_of_week=1),
    },
}


@app.task
def run_orchestrator_briefing():
    from agents.orchestrator import daily_briefing
    result = daily_briefing()
    print(f"[SCHEDULER] Orchestrator briefing: {result[:100]}")


@app.task
def run_subscription_watchdog():
    from agents.subscription_watchdog import run
    return run()


@app.task
def run_treasury_health():
    from agents.treasury_health import run
    return run()


@app.task
def run_member_care_daily():
    from agents.member_care import run_daily
    return run_daily()


@app.task
def run_member_care_inactive():
    from agents.member_care import run_weekly_inactive
    return run_weekly_inactive()


@app.task
def run_dept_program():
    from agents.department_program import run
    return run()


@app.task
def run_announcement_check():
    from agents.announcement import run_check
    return run_check()


@app.task
def run_announcement_digest():
    from agents.announcement import run_weekly_digest_all
    return run_weekly_digest_all()


@app.task
def run_audit_security():
    from agents.audit_security import run
    return run()


@app.task
def run_secretariat():
    from agents.secretariat_agent import run
    return run()
```

### Start the scheduler:

```bash
# Terminal 1 — start the worker
cd /home/professor/projects/churchagents
source .venv/bin/activate
celery -A scheduler.tasks worker --loglevel=info

# Terminal 2 — start the beat (scheduler)
celery -A scheduler.tasks beat --loglevel=info
```

---

## DAY 4 — TASK 6: End-to-End Test All Agents 🔴 MUST

Create `test_all_agents.py` in the root of your agents project:

```python
#!/usr/bin/env python3
"""
Run all agents manually to verify they work end-to-end.
Run before going live: python test_all_agents.py
"""
import os
from dotenv import load_dotenv
load_dotenv()

print("\n" + "="*60)
print("CHURCH AGENTS — END-TO-END TEST")
print("="*60)

tests = [
    ("SubscriptionWatchdogAgent", "agents.subscription_watchdog", "run"),
    ("TreasuryHealthAgent",       "agents.treasury_health",       "run"),
    ("MemberCareAgent (daily)",   "agents.member_care",           "run_daily"),
    ("DepartmentProgramAgent",    "agents.department_program",    "run"),
    ("AnnouncementAgent",         "agents.announcement",          "run_check"),
    ("AuditSecurityAgent",        "agents.audit_security",        "run"),
    ("SecretariatAgent",          "agents.secretariat_agent",     "run"),
]

results = {}
for name, module_path, func_name in tests:
    print(f"\n▶ Running {name}...")
    try:
        import importlib
        module = importlib.import_module(module_path)
        func = getattr(module, func_name)
        result = func()
        results[name] = {"status": "PASS", "result": result}
        print(f"  ✓ PASS: {result}")
    except Exception as e:
        results[name] = {"status": "FAIL", "error": str(e)}
        print(f"  ✗ FAIL: {e}")

print("\n" + "="*60)
print("TEST SUMMARY")
print("="*60)
for name, r in results.items():
    icon = "✓" if r["status"] == "PASS" else "✗"
    print(f"  {icon} {name}: {r['status']}")

# Test Orchestrator Q&A
print("\n▶ Testing OrchestratorAgent Q&A...")
try:
    from agents.orchestrator import ask
    answer = ask("How many churches are on the platform?")
    print(f"  Q: How many churches are on the platform?")
    print(f"  A: {answer[:150]}...")
    print(f"  ✓ PASS")
except Exception as e:
    print(f"  ✗ FAIL: {e}")
```

Run it:

```bash
python test_all_agents.py
```

### ✅ Day 4 Checkpoint

- [ ] `DepartmentProgramAgent` written and tested
- [ ] `AnnouncementAgent` written and tested
- [ ] `AuditSecurityAgent` written and tested
- [ ] `SecretariatAgent` MVP written and tested
- [ ] `scheduler/tasks.py` written
- [ ] Celery worker starts without errors
- [ ] Celery beat starts without errors
- [ ] `test_all_agents.py` passes all agents

---

---

# Post-MVP — Add After the 4 Days 🟢 NICE

These are valuable but not needed for the MVP to work:

- [ ] **Admin chat interface** — a simple web UI or Telegram bot for the OrchestratorAgent
- [ ] **Pinecone** — upgrade from ChromaDB to Pinecone for better RAG in production
- [ ] **LangGraph workflows** — replace simple loops in Watchdog/Treasury with proper graph-based state machines
- [ ] **CrewAI report generation** — multi-agent crew for generating complex church reports
- [ ] **Secretariat PDF generation** — use `reportlab` to generate actual PDF certificates
- [ ] **Paystack webhook handler** — real-time subscription reinstatement on payment success
- [ ] **Django REST API for agents** — expose `AgentLog`, `AgentTask`, `AgentMemory` via DRF for admin dashboard visibility
- [ ] **Secretariat full API** — serializers + views + urls for all 6 secretariat models

---

# Quick Reference — Run Any Agent Manually

```bash
cd /home/professor/projects/churchagents
source .venv/bin/activate

# Run any agent directly
python -c "from agents.subscription_watchdog import run; run()"
python -c "from agents.treasury_health import run; run()"
python -c "from agents.member_care import run_daily; run_daily()"
python -c "from agents.member_care import run_weekly_inactive; run_weekly_inactive()"
python -c "from agents.department_program import run; run()"
python -c "from agents.announcement import run_check; run_check()"
python -c "from agents.audit_security import run; run()"
python -c "from agents.secretariat_agent import run; run()"

# Ask the orchestrator a question
python -c "from agents.orchestrator import ask; print(ask('Which churches are expiring this week?'))"

# Run all tests
python test_all_agents.py

# Start scheduler
celery -A scheduler.tasks worker --loglevel=info
celery -A scheduler.tasks beat   --loglevel=info
```

---

# Files You Will Have At The End

```
churchagents/
├── BUILD_PLAN.md               ← this file
├── agent_architecture.html     ← visual architecture
├── setup_guide.html            ← setup reference
├── .env                        ← your keys (never commit)
├── requirements.txt
├── test_all_agents.py
│
├── mcp_server/
│   ├── auth.py
│   ├── client.py
│   └── tools/
│       ├── accounts.py
│       ├── members.py
│       ├── treasury.py
│       ├── departments.py
│       ├── notifications.py
│       ├── secretariat.py
│       └── agent_infra.py
│
├── agents/
│   ├── orchestrator.py
│   ├── subscription_watchdog.py
│   ├── treasury_health.py
│   ├── member_care.py
│   ├── department_program.py
│   ├── announcement.py
│   ├── audit_security.py
│   └── secretariat_agent.py
│
├── scheduler/
│   └── tasks.py
│
└── data/chroma/
```

---

*Build plan for Church Management SaaS Agent System — 4 days to MVP*
