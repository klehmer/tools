"""Goal-based financial planning.

Projects where each goal will end up given its current balance, time horizon,
planned monthly contribution, and an assumed annual return. Produces concrete
"you need to save $X/month" advice the frontend can render next to each goal.
"""
from __future__ import annotations

from datetime import datetime
from math import ceil
from typing import List

from models import Goal, GoalProjection, PlanResponse


def _months_between(start: datetime, target: datetime) -> int:
    if target <= start:
        return 0
    return max(1, ceil((target - start).days / 30.4375))


def _future_value(pv: float, pmt: float, annual_rate: float, months: int) -> float:
    """FV of a present lump sum plus an end-of-period monthly annuity."""
    if months <= 0:
        return pv
    r = annual_rate / 12.0
    if r == 0:
        return pv + pmt * months
    fv_pv = pv * ((1 + r) ** months)
    fv_pmt = pmt * (((1 + r) ** months - 1) / r)
    return fv_pv + fv_pmt


def _required_monthly(pv: float, target: float, annual_rate: float, months: int) -> float:
    if months <= 0:
        return max(0.0, target - pv)
    r = annual_rate / 12.0
    remaining = target - pv * ((1 + r) ** months if r else 1)
    if remaining <= 0:
        return 0.0
    if r == 0:
        return remaining / months
    return remaining / (((1 + r) ** months - 1) / r)


def project_goal(goal: Goal, annual_rate: float = 0.06) -> GoalProjection:
    now = datetime.utcnow()
    try:
        target_date = datetime.fromisoformat(goal.target_date)
    except ValueError:
        target_date = datetime.fromisoformat(goal.target_date + "T00:00:00")

    months = _months_between(now, target_date)
    pmt = goal.monthly_contribution or 0.0
    projected = _future_value(goal.current_amount, pmt, annual_rate, months)
    required = _required_monthly(goal.current_amount, goal.target_amount, annual_rate, months)

    shortfall = round(max(0.0, goal.target_amount - projected), 2)
    on_track = projected + 1 >= goal.target_amount

    advice: List[str] = []
    if months == 0:
        advice.append("Target date has passed — consider extending it or splitting into phases.")
    elif on_track:
        advice.append(
            f"On track. Contributing ${pmt:,.0f}/mo for {months} months at "
            f"{annual_rate * 100:.0f}% reaches ${projected:,.0f}."
        )
    else:
        advice.append(
            f"Raise monthly contribution to ${required:,.0f} to hit "
            f"${goal.target_amount:,.0f} by {goal.target_date}."
        )
        if pmt and required > pmt * 2:
            advice.append("Required contribution is more than 2× the current plan — consider extending the timeline.")
        if goal.kind == "retirement" and annual_rate < 0.05:
            advice.append("Retirement goals typically assume 5–7% long-term returns; revisit the return assumption.")

    return GoalProjection(
        goal=goal,
        months_remaining=months,
        required_monthly=round(required, 2),
        projected_end_amount=round(projected, 2),
        on_track=on_track,
        shortfall=shortfall,
        advice=advice,
    )


def build_plan(
    goals: List[Goal],
    annual_rate: float,
    monthly_income: float,
    monthly_spending: float,
    monthly_subscriptions: float,
) -> PlanResponse:
    projections = [project_goal(g, annual_rate) for g in goals]
    total_required = round(sum(p.required_monthly for p in projections), 2)
    # "Available" = income minus everything going out the door already.
    available = round(monthly_income - monthly_spending - monthly_subscriptions, 2)

    if total_required <= max(0.0, available):
        feasibility = "comfortable"
    elif total_required <= max(0.0, available) * 1.2:
        feasibility = "tight"
    else:
        feasibility = "infeasible"

    if feasibility == "comfortable":
        summary = (
            f"All goals fit inside your ${available:,.0f}/mo surplus with "
            f"${available - total_required:,.0f}/mo to spare."
        )
    elif feasibility == "tight":
        summary = (
            f"Funding all goals requires ${total_required:,.0f}/mo but only "
            f"${available:,.0f}/mo is free. Consider trimming subscriptions "
            f"or stretching a goal's timeline."
        )
    else:
        gap = round(total_required - available, 2)
        summary = (
            f"Goals exceed available cash flow by ${gap:,.0f}/mo. You will "
            f"need to raise income, cut spending, or push out target dates."
        )

    return PlanResponse(
        projections=projections,
        total_required_monthly=total_required,
        available_monthly_surplus=available,
        feasibility=feasibility,  # type: ignore[arg-type]
        summary=summary,
    )
