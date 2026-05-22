from collections import Counter

def budget_prediction(total, days, budget):
    if days == 0:
        return "No data"
    avg = total / days
    return "Budget risk detected" if avg * 30 > budget else "Budget under control"

def top_reason(reasons):
    if not reasons:
        return "No data"
    return Counter(reasons).most_common(1)[0][0]

def habit_awareness(expenses, monthly_budget):
    if not expenses:
        return {
            "budget_status": "No data",
            "top_reason": "No data"
        }

    total_spent = sum(e["amount"] for e in expenses)
    days = len(set(e["date"] for e in expenses))
    reasons = [e["category"] for e in expenses]

    return {
        "budget_status": budget_prediction(total_spent, days, monthly_budget),
        "top_reason": top_reason(reasons),
        "total_spent": total_spent
    }