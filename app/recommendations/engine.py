from typing import List

import pandas as pd


def generate_recommendations(health: dict, df: pd.DataFrame) -> List[str]:
    """Generate 3-6 actionable financial recommendations based on health metrics."""
    recommendations: List[str] = []
    score = health.get("score", 50)
    savings_rate = health.get("savings_rate", 0)
    anomaly_ratio = health.get("anomaly_ratio", 0)
    trend = health.get("forecast_trend", "stable")

    # Identify top spending category (excluding Income/Transfer)
    spend_df = df[df["amount"] < 0].copy() if "category" in df.columns else pd.DataFrame()
    top_category = "Other"
    if not spend_df.empty and "category" in spend_df.columns:
        cat_totals = spend_df.groupby("category")["amount"].sum().abs()
        cat_totals = cat_totals.drop(labels=["Income", "Transfer"], errors="ignore")
        if not cat_totals.empty:
            top_category = cat_totals.idxmax()

    # Score-based recommendations
    if score < 40:
        recommendations.append(
            "Your financial health is critical. Create an emergency budget immediately "
            "and eliminate all non-essential spending for the next 30 days."
        )
    elif score < 55:
        recommendations.append(
            "Your finances need attention. Set up automatic transfers to a savings account "
            "equal to at least 10% of your income."
        )
    elif score < 70:
        recommendations.append(
            "You're on the right track. Consider increasing your savings rate by 5% and "
            "reviewing subscription services for potential cancellations."
        )
    else:
        recommendations.append(
            "Strong financial health! Consider diversifying into index funds or retirement "
            "accounts to maximize long-term growth."
        )

    # Anomaly-based recommendations
    if anomaly_ratio > 0.15:
        recommendations.append(
            "High number of unusual transactions detected. Review flagged transactions for "
            "potential fraud or unplanned large expenses."
        )
    elif anomaly_ratio > 0.05:
        recommendations.append(
            "Some spending anomalies detected. Set up transaction alerts for amounts "
            "exceeding your typical spending threshold."
        )

    # Savings-rate-based recommendations
    if savings_rate < 0.1:
        recommendations.append(
            "Your savings rate is below 10%. Use the 50/30/20 rule: 50% needs, 30% wants, "
            "20% savings and debt repayment."
        )
    elif savings_rate < 0.2:
        recommendations.append(
            "Aim to increase your savings rate to 20%. Automate savings on payday to make "
            "it effortless."
        )

    # Trend-based recommendations
    if trend == "declining":
        recommendations.append(
            "Your spending trend is rising. Identify and cut discretionary expenses, "
            "especially recurring subscriptions you no longer use."
        )
    elif trend == "improving":
        recommendations.append(
            "Your spending trend is improving — keep it up! Consider allocating the savings "
            "toward an emergency fund or high-yield savings account."
        )

    # Top-category recommendation
    if top_category != "Other":
        recommendations.append(
            f"Your top spending category is {top_category}. Look for ways to reduce costs "
            f"here — compare providers, use cashback apps, or set a monthly cap."
        )

    # Ensure min 3, max 6
    if len(recommendations) < 3:
        recommendations.append(
            "Track your daily expenses for one month to identify hidden spending patterns."
        )
    return recommendations[:6]
