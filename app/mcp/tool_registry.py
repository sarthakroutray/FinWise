"""
Tool registry for MCP — maps tool names to Gemini function declarations
and provides a single ``execute()`` dispatcher.
"""

from __future__ import annotations

import logging
from typing import Any, Callable

from app.mcp import math_tools

logger = logging.getLogger(__name__)


# ── Gemini function-declaration schema for each tool ────────────────────────

_TOOL_DECLARATIONS: list[dict[str, Any]] = [
    {
        "name": "compound_interest",
        "description": "Calculate compound interest over a given period. Returns chart data + LaTeX formula.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "principal": {"type": "NUMBER", "description": "Initial investment amount in dollars"},
                "rate": {"type": "NUMBER", "description": "Annual interest rate as decimal (e.g. 0.05 for 5%)"},
                "compounds_per_year": {"type": "INTEGER", "description": "Compounding frequency (default 12 = monthly)"},
                "years": {"type": "INTEGER", "description": "Investment horizon in years"},
            },
            "required": ["principal", "rate"],
        },
    },
    {
        "name": "loan_amortization",
        "description": "Generate a loan amortization schedule with monthly payment, total interest, and chart data.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "principal": {"type": "NUMBER", "description": "Loan amount in dollars"},
                "annual_rate": {"type": "NUMBER", "description": "Annual interest rate as decimal"},
                "term_months": {"type": "INTEGER", "description": "Loan term in months (default 360 = 30yr)"},
            },
            "required": ["principal", "annual_rate"],
        },
    },
    {
        "name": "savings_projection",
        "description": "Project future savings with regular monthly deposits. Returns growth chart.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "monthly_deposit": {"type": "NUMBER", "description": "Monthly savings amount in dollars"},
                "annual_rate": {"type": "NUMBER", "description": "Expected annual return as decimal (default 0.05)"},
                "years": {"type": "INTEGER", "description": "Projection horizon in years (default 20)"},
            },
            "required": ["monthly_deposit"],
        },
    },
    {
        "name": "budget_breakdown",
        "description": "Visualise income vs categorised expenses. Returns pie chart data.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "income": {"type": "NUMBER", "description": "Monthly income in dollars"},
                "expenses": {
                    "type": "OBJECT",
                    "description": "Dict of {category_name: amount} for each expense category",
                },
            },
            "required": ["income", "expenses"],
        },
    },
    {
        "name": "scratchpad_query",
        "description": "Execute an SQL query on the conversation's private SQLite scratchpad database. "
                       "The user's transactions are pre-loaded in a 'transactions' table with columns: "
                       "date, description, amount, balance, category.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "sql": {"type": "STRING", "description": "The SQL query to execute"},
            },
            "required": ["sql"],
        },
    },
    {
        "name": "scratchpad_list_tables",
        "description": "List all tables currently in the conversation's scratchpad database.",
        "parameters": {
            "type": "OBJECT",
            "properties": {},
        },
    },
]

# ── Mapping tool names → Python callables ───────────────────────────────────

_TOOL_FUNCTIONS: dict[str, Callable[..., Any]] = {
    "compound_interest": math_tools.compound_interest,
    "loan_amortization": math_tools.loan_amortization,
    "savings_projection": math_tools.savings_projection,
    "budget_breakdown": math_tools.budget_breakdown,
    # scratchpad tools are handled specially in execute()
}


def get_tool_declarations() -> list[dict[str, Any]]:
    """Return the Gemini-compatible function declarations for all MCP tools."""
    return _TOOL_DECLARATIONS


def execute(name: str, params: dict[str, Any], *, scratchpad: Any = None) -> dict[str, Any]:
    """
    Execute a named tool with the given parameters.

    Parameters
    ----------
    name : tool name (must match a declaration)
    params : keyword arguments for the tool function
    scratchpad : optional ScratchpadDB instance for SQL tools
    """
    # Scratchpad tools are a special case — they need the DB instance
    if name == "scratchpad_query":
        if scratchpad is None:
            return {"error": "No scratchpad database available for this session"}
        sql = params.get("sql", "")
        return scratchpad.execute_sql(sql)

    if name == "scratchpad_list_tables":
        if scratchpad is None:
            return {"error": "No scratchpad database available for this session"}
        return {"tables": scratchpad.list_tables()}

    func = _TOOL_FUNCTIONS.get(name)
    if func is None:
        logger.warning("Unknown tool call: %s", name)
        return {"error": f"Unknown tool: {name}"}

    try:
        result = func(**params)
        return result
    except Exception as exc:
        logger.exception("Tool execution error: %s(%s)", name, params)
        return {"error": str(exc)}
