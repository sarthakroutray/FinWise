import re


def categorize_expenses(description: str) -> str:
    """Classify transaction description into a spending category via keyword matching."""
    desc = (description or "").lower()
    categories = {
        "Food": re.compile(
            r"(restaurant|cafe|coffee|pizza|burger|food|dining|bakery|donut|starbucks|"
            r"mcdonald|subway|uber\s*eats|doordash|grubhub|zomato|swiggy|kfc|domino)"
        ),
        "Transport": re.compile(
            r"(uber|lyft|taxi|cab|metro|bus|rail|train|fuel|gas\s*station|petrol|"
            r"parking|toll|airline|flight|transit)"
        ),
        "Utilities": re.compile(
            r"(electric|water|gas\b|internet|wifi|broadband|phone|mobile|telecom|"
            r"utility|sewage|cable|bill\s*pay)"
        ),
        "Entertainment": re.compile(
            r"(netflix|spotify|hulu|disney|cinema|movie|theatre|theater|gaming|"
            r"playstation|xbox|steam|concert|event|ticket)"
        ),
        "Healthcare": re.compile(
            r"(hospital|clinic|doctor|pharmacy|medical|health|dental|optom|lab|"
            r"diagnos|insurance|wellness|physiotherapy)"
        ),
        "Shopping": re.compile(
            r"(amazon|walmart|target|costco|ebay|flipkart|mall|store|shop|retail|"
            r"clothing|fashion|electronics|ikea|home\s*depot)"
        ),
        "Income": re.compile(
            r"(salary|payroll|deposit|interest\s*credit|dividend|refund|cashback|"
            r"reimburs|bonus|stipend|freelance|income)"
        ),
        "Transfer": re.compile(
            r"(transfer|neft|rtgs|imps|upi|wire|ach|zelle|venmo|paypal|"
            r"bank\s*transfer|self\s*transfer)"
        ),
    }
    for category, pattern in categories.items():
        if pattern.search(desc):
            return category
    return "Other"
