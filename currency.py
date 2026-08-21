import requests

CURRENCY_MAP = {
    "IN": {"currency": "INR", "symbol": "₹", "local_term": "crore"},
    "US": {"currency": "USD", "symbol": "$", "local_term": "billion"},
    "GB": {"currency": "GBP", "symbol": "£", "local_term": "billion"},
    "JP": {"currency": "JPY", "symbol": "¥", "local_term": "兆"},
    "AE": {"currency": "AED", "symbol": "AED", "local_term": "billion"},
    "DE": {"currency": "EUR", "symbol": "€", "local_term": "billion"},
    "FR": {"currency": "EUR", "symbol": "€", "local_term": "billion"},
}

def detect_country_from_idea(idea: str):
    idea_lower = idea.lower()
    if "india" in idea_lower or "inr" in idea_lower:
        return "IN"
    if "japan" in idea_lower or "jpy" in idea_lower or "tokyo" in idea_lower:
        return "JP"
    if "uk" in idea_lower or "britain" in idea_lower or "london" in idea_lower:
        return "GB"
    if "dubai" in idea_lower or "uae" in idea_lower:
        return "AE"
    if "germany" in idea_lower or "france" in idea_lower or "europe" in idea_lower:
        return "DE"
    return "US"

def get_fx_with_proof(amount_usd: float, target_currency: str):
    try:
        r = requests.get(f"https://api.exchangerate.host/convert?from=USD&to={target_currency}&amount={amount_usd}", timeout=10).json()
        if r.get("result"):
            return {
                "converted": r.get("result"),
                "rate": r.get("info", {}).get("rate"),
                "date": r.get("date"),
                "source": "https://exchangerate.host",
                "proof": f"1 USD = {r.get('info', {}).get('rate')} {target_currency} on {r.get('date')} [exchangerate.host]"
            }
    except (requests.RequestException, ValueError, TypeError):
        pass
    return {"converted": None, "proof": "FX conversion failed - showing original currency"}
