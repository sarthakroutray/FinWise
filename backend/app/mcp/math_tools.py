"""
Deterministic finance calculators exposed as MCP tools for Gemini function-calling.

Each function returns a standardised dict with:
  - result: the numeric answer
  - latex_formula: the LaTeX representation
  - chart_data: list of {x, y} points for Recharts
  - axis_config: {x: label, y: label}
  - component_type: "dynamic_chart"
  - chart_engine: "recharts"
  - chart_type: "line" | "bar" | "area" | "pie"
"""

from __future__ import annotations

import math
from typing import Any


def compound_interest(
    principal: float,
    rate: float,
    compounds_per_year: int = 12,
    years: int = 10,
) -> dict[str, Any]:
    """
    Calculate compound interest: A = P(1 + r/n)^(nt)

    Parameters
    ----------
    principal : initial investment ($)
    rate : annual interest rate (decimal, e.g. 0.05 for 5%)
    compounds_per_year : compounding frequency (12 = monthly)
    years : investment horizon
    """
    r, n, t = rate, compounds_per_year, years
    chart_data = []
    for yr in range(0, t + 1):
        value = principal * (1 + r / n) ** (n * yr)
        chart_data.append({"year": yr, "value": round(value, 2)})

    final = chart_data[-1]["value"]

    return {
        "component_type": "dynamic_chart",
        "chart_engine": "recharts",
        "chart_type": "area",
        "result": final,
        "total_interest": round(final - principal, 2),
        "latex_formula": f"$$ A = {principal:,.0f} \\left(1 + \\frac{{{rate}}}{{{n}}}\\right)^{{{n} \\times {t}}} = {final:,.2f} $$",
        "chart_data": chart_data,
        "axis_config": {"x": "year", "y": "value", "x_label": "Year", "y_label": "Balance ($)"},
    }


def loan_amortization(
    principal: float,
    annual_rate: float,
    term_months: int = 360,
) -> dict[str, Any]:
    """
    Generate a loan amortization schedule.

    Parameters
    ----------
    principal : loan amount ($)
    annual_rate : annual interest rate (decimal)
    term_months : loan term in months (360 = 30 years)
    """
    r = annual_rate / 12
    if r == 0:
        monthly_payment = principal / term_months
    else:
        monthly_payment = principal * (r * (1 + r) ** term_months) / ((1 + r) ** term_months - 1)

    balance = principal
    chart_data = [{"month": 0, "balance": round(balance, 2), "interest_paid": 0, "principal_paid": 0}]
    total_interest = 0.0
    total_principal = 0.0

    for month in range(1, term_months + 1):
        interest = balance * r
        principal_paid = monthly_payment - interest
        balance -= principal_paid
        total_interest += interest
        total_principal += principal_paid

        # Only add yearly data points to keep chart manageable
        if month % 12 == 0 or month == term_months:
            chart_data.append({
                "month": month,
                "year": month // 12,
                "balance": round(max(balance, 0), 2),
                "total_interest": round(total_interest, 2),
                "total_principal": round(total_principal, 2),
            })

    return {
        "component_type": "dynamic_chart",
        "chart_engine": "recharts",
        "chart_type": "area",
        "result": round(monthly_payment, 2),
        "monthly_payment": round(monthly_payment, 2),
        "total_interest": round(total_interest, 2),
        "total_paid": round(total_interest + principal, 2),
        "latex_formula": f"$$ M = {principal:,.0f} \\cdot \\frac{{r(1+r)^n}}{{(1+r)^n - 1}} = {monthly_payment:,.2f}/\\text{{mo}} $$",
        "chart_data": chart_data,
        "axis_config": {"x": "year", "y": "balance", "x_label": "Year", "y_label": "Remaining Balance ($)"},
    }


def savings_projection(
    monthly_deposit: float,
    annual_rate: float = 0.05,
    years: int = 20,
) -> dict[str, Any]:
    """
    Project future savings with regular monthly contributions.

    Parameters
    ----------
    monthly_deposit : amount saved per month ($)
    annual_rate : expected annual return (decimal)
    years : projection horizon
    """
    r = annual_rate / 12
    chart_data = []
    for yr in range(0, years + 1):
        n = yr * 12
        if r == 0:
            fv = monthly_deposit * n
        else:
            fv = monthly_deposit * (((1 + r) ** n - 1) / r)
        chart_data.append({
            "year": yr,
            "value": round(fv, 2),
            "contributions": round(monthly_deposit * n, 2),
        })

    final = chart_data[-1]["value"]
    total_contributed = monthly_deposit * years * 12

    return {
        "component_type": "dynamic_chart",
        "chart_engine": "recharts",
        "chart_type": "area",
        "result": final,
        "total_contributions": round(total_contributed, 2),
        "total_growth": round(final - total_contributed, 2),
        "latex_formula": f"$$ FV = {monthly_deposit:,.0f} \\cdot \\frac{{(1 + r)^n - 1}}{{r}} = {final:,.2f} $$",
        "chart_data": chart_data,
        "axis_config": {"x": "year", "y": "value", "x_label": "Year", "y_label": "Savings ($)"},
    }


def budget_breakdown(
    income: float,
    expenses: dict[str, float],
) -> dict[str, Any]:
    """
    Visualise income vs. categorised expenses.

    Parameters
    ----------
    income : monthly income ($)
    expenses : dict of {category: amount}
    """
    total_expenses = sum(expenses.values())
    savings = income - total_expenses

    chart_data = [{"name": cat, "value": round(amt, 2)} for cat, amt in expenses.items()]
    if savings > 0:
        chart_data.append({"name": "Savings", "value": round(savings, 2)})

    return {
        "component_type": "dynamic_chart",
        "chart_engine": "recharts",
        "chart_type": "pie",
        "result": round(savings, 2),
        "income": income,
        "total_expenses": round(total_expenses, 2),
        "savings_rate": round((savings / income) * 100, 1) if income > 0 else 0,
        "latex_formula": f"$$ \\text{{Savings}} = {income:,.0f} - {total_expenses:,.0f} = {savings:,.0f} \\quad ({round((savings/income)*100, 1) if income > 0 else 0}\\%) $$",
        "chart_data": chart_data,
        "axis_config": {"x": "name", "y": "value", "x_label": "Category", "y_label": "Amount ($)"},
    }
