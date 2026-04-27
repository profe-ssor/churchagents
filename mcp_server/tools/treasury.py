"""
MCP Tools — Treasury
Endpoints: /api/treasury/...
"""
from __future__ import annotations

from collections import defaultdict

from mcp_server import client
from datetime import date, timedelta, datetime

from monitoring.alert_thresholds import ANOMALY_AMOUNT, BUDGET_UTILIZATION_WARN


async def get_treasury_stats(church_id: str = None) -> dict:
    """Overall income vs expense summary."""
    params = {}
    if church_id:
        params["church_id"] = church_id
    return await client.get("/api/treasury/statistics/", params=params)


async def get_income_transactions(church_id: str = None, days: int = 30) -> list:
    """Return income transactions within the last `days` days."""
    params = {}
    if church_id:
        params["church_id"] = church_id
    data = await client.get("/api/treasury/income-transactions/", params=params)
    transactions = data.get("results", data) if isinstance(data, dict) else data
    cutoff = date.today() - timedelta(days=days)
    return [
        t for t in transactions
        if t.get("date") and date.fromisoformat(t["date"][:10]) >= cutoff
    ]


async def get_expense_transactions(church_id: str = None, days: int = 30) -> list:
    """Return expense transactions within the last `days` days."""
    params = {}
    if church_id:
        params["church_id"] = church_id
    data = await client.get("/api/treasury/expense-transactions/", params=params)
    transactions = data.get("results", data) if isinstance(data, dict) else data
    cutoff = date.today() - timedelta(days=days)
    return [
        t for t in transactions
        if t.get("date") and date.fromisoformat(t["date"][:10]) >= cutoff
    ]


async def get_pending_expense_requests(church_id: str = None) -> list:
    """Return expense requests in SUBMITTED status (awaiting approval)."""
    # Django model status choices: DRAFT, SUBMITTED, DEPT_HEAD_APPROVED,
    # TREASURER_APPROVED, FIRST_ELDER_APPROVED, APPROVED
    params = {"status": "SUBMITTED"}
    if church_id:
        params["church_id"] = church_id
    data = await client.get("/api/treasury/expense-requests/", params=params)
    return data.get("results", data) if isinstance(data, dict) else data


async def get_stalled_expense_requests(church_id: str = None, hours: int = 48) -> list:
    """Return expense requests pending longer than `hours` hours."""
    requests = await get_pending_expense_requests(church_id=church_id)
    cutoff = datetime.utcnow() - timedelta(hours=hours)
    stalled = []
    for r in requests:
        created = r.get("created_at") or r.get("submitted_at", "")
        if created:
            created_dt = datetime.fromisoformat(created[:19])
            if created_dt < cutoff:
                r["hours_pending"] = int((datetime.utcnow() - created_dt).total_seconds() / 3600)
                stalled.append(r)
    return stalled


async def get_large_transactions(church_id: str = None, threshold: float = 5000) -> list:
    """Return transactions above the anomaly threshold."""
    income = await get_income_transactions(church_id=church_id, days=7)
    expenses = await get_expense_transactions(church_id=church_id, days=7)
    all_tx = income + expenses
    return [t for t in all_tx if float(t.get("amount", 0)) >= threshold]


async def get_expense_request(request_id: str) -> dict:
    return await client.get(f"/api/treasury/expense-requests/{request_id}/")


async def sum_income_for_calendar_month(
    year: int,
    month: int,
    church_id: str | None = None,
) -> dict:
    """
    Total income in a calendar month (filters client-side; fetches up to page_size rows).
    """
    params: dict = {"page_size": 500}
    if church_id:
        params["church_id"] = church_id
    data = await client.get("/api/treasury/income-transactions/", params=params)
    txs = data.get("results", data) if isinstance(data, dict) else data
    if not isinstance(txs, list):
        txs = []
    total = 0.0
    n = 0
    for t in txs:
        d = t.get("date") or t.get("transaction_date")
        if not d:
            continue
        try:
            dt = date.fromisoformat(str(d)[:10])
        except ValueError:
            continue
        if dt.year == year and dt.month == month:
            total += float(t.get("amount", 0))
            n += 1
    return {
        "church_id": church_id,
        "year": year,
        "month": month,
        "total_income": round(total, 2),
        "transaction_count": n,
        "note": "Totals only include transactions returned by this page_size query.",
    }


async def sum_expenses_for_calendar_month(
    year: int,
    month: int,
    church_id: str | None = None,
) -> dict:
    params: dict = {"page_size": 500}
    if church_id:
        params["church_id"] = church_id
    data = await client.get("/api/treasury/expense-transactions/", params=params)
    txs = data.get("results", data) if isinstance(data, dict) else data
    if not isinstance(txs, list):
        txs = []
    total = 0.0
    n = 0
    for t in txs:
        d = t.get("date") or t.get("transaction_date")
        if not d:
            continue
        try:
            dt = date.fromisoformat(str(d)[:10])
        except ValueError:
            continue
        if dt.year == year and dt.month == month:
            total += float(t.get("amount", 0))
            n += 1
    return {
        "church_id": church_id,
        "year": year,
        "month": month,
        "total_expenses": round(total, 2),
        "transaction_count": n,
        "note": "Totals only include transactions returned by this page_size query.",
    }


def _parse_iso_date(s: str | None) -> date | None:
    if not s:
        return None
    try:
        return date.fromisoformat(str(s)[:10])
    except ValueError:
        return None


def _tx_day(t: dict) -> date | None:
    return _parse_iso_date(t.get("date") or t.get("transaction_date"))


async def _fetch_income_transactions_raw(church_id: str | None, page_size: int = 500) -> list:
    params: dict[str, str] = {"page_size": str(page_size)}
    if church_id:
        params["church_id"] = church_id
    data = await client.get("/api/treasury/income-transactions/", params=params)
    txs = data.get("results", data) if isinstance(data, dict) else data
    return txs if isinstance(txs, list) else []


async def _fetch_expense_transactions_raw(church_id: str | None, page_size: int = 500) -> list:
    params: dict[str, str] = {"page_size": str(page_size)}
    if church_id:
        params["church_id"] = church_id
    data = await client.get("/api/treasury/expense-transactions/", params=params)
    txs = data.get("results", data) if isinstance(data, dict) else data
    return txs if isinstance(txs, list) else []


def _resolve_range(
    start_date: str | None,
    end_date: str | None,
    days: int,
) -> tuple[date, date]:
    """Inclusive date range; if start/end omitted, use last `days` days ending today."""
    today = date.today()
    if start_date and end_date:
        sd = _parse_iso_date(start_date) or today
        ed = _parse_iso_date(end_date) or today
        return (min(sd, ed), max(sd, ed))
    end = _parse_iso_date(end_date) or today
    span = max(1, int(days))
    start = end - timedelta(days=span - 1)
    return (start, end)


async def get_income_summary(
    church_id: str,
    start_date: str | None = None,
    end_date: str | None = None,
    days: int = 30,
) -> dict:
    """Aggregate income by category_name over a date range (client-side filter)."""
    start, end = _resolve_range(start_date, end_date, days)
    txs = await _fetch_income_transactions_raw(church_id)
    by_cat: dict[str, float] = defaultdict(float)
    total = 0.0
    n = 0
    for t in txs:
        d = _tx_day(t)
        if not d or d < start or d > end:
            continue
        amt = float(t.get("amount", 0))
        total += amt
        n += 1
        cat = (t.get("category_name") or "Uncategorized").strip() or "Uncategorized"
        by_cat[cat] += amt
    return {
        "church_id": church_id,
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "total_income": round(total, 2),
        "transaction_count": n,
        "by_category": dict(sorted(by_cat.items(), key=lambda x: -x[1])),
        "note": "Filtered from paginated income list; increase backend page_size if totals look low.",
    }


async def get_expense_summary(
    church_id: str,
    start_date: str | None = None,
    end_date: str | None = None,
    days: int = 30,
) -> dict:
    """Aggregate expenses by category and department name."""
    start, end = _resolve_range(start_date, end_date, days)
    txs = await _fetch_expense_transactions_raw(church_id)
    by_cat: dict[str, float] = defaultdict(float)
    by_dept: dict[str, float] = defaultdict(float)
    total = 0.0
    n = 0
    for t in txs:
        d = _tx_day(t)
        if not d or d < start or d > end:
            continue
        amt = float(t.get("amount", 0))
        total += amt
        n += 1
        cat = (t.get("category_name") or "Uncategorized").strip() or "Uncategorized"
        dept = (t.get("department_name") or "Unassigned").strip() or "Unassigned"
        by_cat[cat] += amt
        by_dept[dept] += amt
    return {
        "church_id": church_id,
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "total_expenses": round(total, 2),
        "transaction_count": n,
        "by_category": dict(sorted(by_cat.items(), key=lambda x: -x[1])),
        "by_department": dict(sorted(by_dept.items(), key=lambda x: -x[1])),
        "note": "Filtered from paginated expense list; totals may be incomplete if over page_size.",
    }


async def detect_anomalies(
    church_id: str,
    threshold: float | None = None,
    days: int = 7,
) -> dict:
    """Income + expense transactions at or above `threshold` in the last `days` days."""
    thr = float(threshold) if threshold is not None else float(ANOMALY_AMOUNT)
    income = await get_income_transactions(church_id=church_id, days=days)
    expenses = await get_expense_transactions(church_id=church_id, days=days)
    flagged: list[dict] = []
    for t in income + expenses:
        if float(t.get("amount", 0)) >= thr:
            flagged.append(t)
    return {
        "church_id": church_id,
        "threshold": thr,
        "days": days,
        "count": len(flagged),
        "transactions": flagged[:100],
    }


async def get_asset_inventory(church_id: str, page_size: int = 200) -> dict:
    """List church assets (requires API token scoped to that church for many backends)."""
    params = {"page_size": str(page_size)}
    # Many treasury routes accept church_id for platform service users
    params["church_id"] = church_id
    try:
        data = await client.get("/api/treasury/assets/", params=params)
    except Exception as e:
        return {"church_id": church_id, "count": 0, "assets": [], "error": str(e)}
    rows = data.get("results", data) if isinstance(data, dict) else data
    if not isinstance(rows, list):
        rows = []
    return {
        "church_id": church_id,
        "count": len(rows),
        "assets": rows[: page_size],
        "note": "Asset list uses tenant context; platform JWT may need church-scoped login or X-Church-ID.",
    }


async def get_budget_vs_actual(church_id: str, department_id: str) -> dict:
    """
    Compare program budget totals (from approved programs) vs expense transactions for the department.
    Department master records do not carry annual allocation; budgets live on programs.
    """
    from mcp_server.tools import departments as dept_tools

    dept = await dept_tools.get_department(department_id)
    d_church = dept.get("church")
    if isinstance(d_church, dict):
        dep_cid = str(d_church.get("id") or "")
    else:
        dep_cid = str(d_church or "")
    if dep_cid and dep_cid != str(church_id):
        return {
            "error": "department_church_mismatch",
            "church_id_arg": church_id,
            "department_church_id": dep_cid,
        }

    data = await client.get(
        "/api/programs/",
        params={"church_id": church_id, "page_size": "500"},
    )
    programs = data.get("results", data) if isinstance(data, dict) else data
    if not isinstance(programs, list):
        programs = []

    prog_income = 0.0
    prog_expense = 0.0
    n_prog = 0
    for p in programs:
        dep = p.get("department")
        if isinstance(dep, dict):
            pid = str(dep.get("id") or "")
        else:
            pid = str(dep) if dep is not None else ""
        if pid != str(department_id):
            continue
        prog_income += float(p.get("total_income") or 0)
        prog_expense += float(p.get("total_expenses") or 0)
        n_prog += 1

    exp_tx = await _fetch_expense_transactions_raw(church_id)
    actual_spend = 0.0
    n_tx = 0
    dept_name = (dept.get("name") or "").strip()
    for t in exp_tx:
        dn = (t.get("department_name") or "").strip()
        if not dn or not dept_name or dn != dept_name:
            continue
        actual_spend += float(t.get("amount", 0))
        n_tx += 1

    budget_util = None
    if prog_income > 0:
        budget_util = round(prog_expense / prog_income, 4)

    return {
        "church_id": church_id,
        "department_id": department_id,
        "department_name": dept.get("name"),
        "programs_considered": n_prog,
        "program_budget_total_income": round(prog_income, 2),
        "program_budget_total_expenses": round(prog_expense, 2),
        "expense_transactions_actual_sum": round(actual_spend, 2),
        "expense_transactions_matched_count": n_tx,
        "budget_expense_to_income_ratio": budget_util,
        "note": (
            "Program totals come from department programs; actual spend sums expense transactions "
            "whose department_name matches this department."
        ),
    }


async def scan_department_budget_pressure(
    church_id: str,
    warn_ratio: float | None = None,
) -> list[dict]:
    """
    Departments where aggregated program expenses / income >= warn_ratio (income > 0).
    Used by TreasuryHealthAgent extended checks.
    """
    ratio = float(warn_ratio) if warn_ratio is not None else float(BUDGET_UTILIZATION_WARN)
    data = await client.get(
        "/api/programs/",
        params={"church_id": church_id, "page_size": "500"},
    )
    programs = data.get("results", data) if isinstance(data, dict) else data
    if not isinstance(programs, list):
        return []

    agg: dict[str, dict[str, float | str]] = {}
    for p in programs:
        dep = p.get("department")
        if isinstance(dep, dict):
            did = str(dep.get("id") or "")
        else:
            did = str(dep) if dep is not None else ""
        if not did:
            continue
        if did not in agg:
            agg[did] = {
                "department_id": did,
                "department_name": str(p.get("department_name") or ""),
                "total_income": 0.0,
                "total_expenses": 0.0,
            }
        agg[did]["total_income"] = float(agg[did]["total_income"]) + float(p.get("total_income") or 0)
        agg[did]["total_expenses"] = float(agg[did]["total_expenses"]) + float(p.get("total_expenses") or 0)

    out: list[dict] = []
    for row in agg.values():
        inc = float(row["total_income"])
        exp = float(row["total_expenses"])
        if inc <= 0:
            continue
        util = exp / inc
        if util >= ratio:
            out.append(
                {
                    "department_id": row["department_id"],
                    "department_name": row["department_name"],
                    "utilization": round(util, 4),
                    "total_income": round(inc, 2),
                    "total_expenses": round(exp, 2),
                }
            )
    return sorted(out, key=lambda x: -x["utilization"])


async def church_income_stale(church_id: str, days: int) -> bool:
    """True if there are no income transactions in the inclusive last `days` days."""
    txs = await get_income_transactions(church_id=church_id, days=days)
    return len(txs) == 0


async def generate_financial_report(
    church_id: str,
    report_format: str = "json",
    year: int | None = None,
    month: int | None = None,
) -> dict:
    """
    Structured financial bundle for orchestrator / admin (not binary PDF/XLSX generation).
    """
    fmt = (report_format or "json").strip().lower()
    stats = await get_treasury_stats(church_id=church_id)
    stalled = await get_stalled_expense_requests(church_id=church_id)
    anomalies = await detect_anomalies(church_id=church_id)
    inc_summary = await get_income_summary(church_id, days=30)
    exp_summary = await get_expense_summary(church_id, days=30)
    report: dict = {
        "church_id": church_id,
        "format": fmt,
        "treasury_statistics": stats,
        "stalled_expense_requests_count": len(stalled),
        "stalled_expense_sample": stalled[:15],
        "anomaly_transactions_count": anomalies.get("count", 0),
        "anomaly_sample": (anomalies.get("transactions") or [])[:10],
        "income_last_30d_summary": inc_summary,
        "expense_last_30d_summary": exp_summary,
    }
    if year and month and 1 <= month <= 12:
        report["calendar_month"] = {
            "year": year,
            "month": month,
            "income": await sum_income_for_calendar_month(year, month, church_id),
            "expenses": await sum_expenses_for_calendar_month(year, month, church_id),
        }
    if fmt in ("pdf", "xlsx", "csv"):
        report["export_note"] = (
            f"format={fmt}: binary / file generation is not implemented here; "
            "use format=json for machine-readable output or export from Django admin."
        )
    return report
