"""
Marketplace settings - the one place that says which Amazon site is scraped.

Everything marketplace-specific (domain, currency, delivery location, locale and
the currency-named spreadsheet columns) is derived from here.
"""

MARKETPLACE = "Amazon US"
COUNTRY = "United States"
AMAZON_DOMAIN = "amazon.com"
BASE = f"https://www.{AMAZON_DOMAIN}"
LOCALE = "en-US"

CURRENCY = "USD"
CURRENCY_SYMBOL = "$"

# Delivery location applied at the start of every run. Availability, delivery,
# stock, offers and even prices depend on it (from outside the US Amazon shows
# converted prices, e.g. "GBP 112.26", until a US ZIP code is set).
DELIVERY_ZIP = "10010"

# Spreadsheet price columns and their Excel number format follow the currency.
PRICE_COL = f"price_{CURRENCY.lower()}"            # price_usd
LIST_PRICE_COL = f"list_price_{CURRENCY.lower()}"  # list_price_usd
PRICE_FORMAT = f"{CURRENCY_SYMBOL}#,##0.00"
