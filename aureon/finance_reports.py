"""Period-aware management reporting over manually recorded ledger entries."""
from datetime import datetime, timedelta, timezone
from .db import connect


def profit_and_loss(db_path, start=None, end=None, currency=None):
    def parse(value, label):
        if value is None:
            return None
        if not isinstance(value, str):
            raise ValueError(label + " must be an ISO date or timestamp")
        try:
            date_only = len(value) == 10
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            if date_only and label == "end":
                parsed = parsed + timedelta(days=1)
            return parsed.astimezone(timezone.utc).isoformat(), date_only and label == "end"
        except ValueError:
            raise ValueError(label + " must be an ISO date or timestamp") from None
    lower_result = parse(start, "start")
    upper_result = parse(end, "end")
    lower = lower_result[0] if lower_result else None
    upper = upper_result[0] if upper_result else None
    upper_exclusive = upper_result[1] if upper_result else False
    if lower and upper and lower > upper:
        raise ValueError("start must not be after end")
    if currency is not None and (not isinstance(currency, str) or len(currency) != 3 or not currency.isascii() or not currency.isalpha()):
        raise ValueError("currency must be a three-letter code")
    clauses, params = [], []
    if lower:
        clauses.append("created_at>=?")
        params.append(lower)
    if upper:
        clauses.append("created_at<?" if upper_exclusive else "created_at<=?")
        params.append(upper)
    if currency:
        clauses.append("currency=?")
        params.append(currency.upper())
    query = "SELECT currency,entry_type,actual,SUM(amount) amount,COUNT(*) count FROM finance_entries"
    if clauses:
        query += " WHERE " + " AND ".join(clauses)
    query += " GROUP BY currency,entry_type,actual ORDER BY currency,entry_type,actual"
    with connect(db_path) as conn:
        rows = conn.execute(query, params).fetchall()
    report = {}
    for row in rows:
        item = report.setdefault(row["currency"], {"actual_revenue": 0.0, "actual_expenses": 0.0,
            "estimated_revenue": 0.0, "estimated_expenses": 0.0, "line_items": []})
        key = ("actual_" if row["actual"] else "estimated_") + ("revenue" if row["entry_type"] == "revenue" else "expenses")
        item[key] += float(row["amount"])
        item["line_items"].append({"type": row["entry_type"], "actual": bool(row["actual"]),
                                   "amount": round(float(row["amount"]), 2), "entries": row["count"]})
    for item in report.values():
        for key in ("actual_revenue", "actual_expenses", "estimated_revenue", "estimated_expenses"):
            item[key] = round(item[key], 2)
        item["actual_net"] = round(item["actual_revenue"] - item["actual_expenses"], 2)
        item["estimated_net"] = round(item["estimated_revenue"] - item["estimated_expenses"], 2)
        item["actual_margin"] = round(item["actual_net"] / item["actual_revenue"], 4) if item["actual_revenue"] else None
    return {"period": {"start": lower, "end": upper}, "currencies": report,
            "source": "Aureon manually recorded ledger",
            "limitations": ["No bank, store payout, payment, tax or FX feeds are connected.",
                            "Different currencies are never combined."]}
