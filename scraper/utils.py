"""Small helpers shared by every layer."""

import re

from .config import BASE, CURRENCY, CURRENCY_SYMBOL  # noqa: F401  (BASE re-exported)

# Modern ASINs start with "B0"; books use their 10-character ISBN.
ASIN_PATTERN = r"(?:B0[0-9A-Z]{8}|\d{9}[\dX])"


def text(el):
    return el.get_text(" ", strip=True) if el else ""


def to_money(s):
    """'$1,299.00' -> 1299.0"""
    m = re.search(r"[\d,]+(?:\.\d+)?", s or "")
    return float(m.group().replace(",", "")) if m else None


def to_price(s):
    """A price in the marketplace currency: '$1,299.00' -> 1299.0. Returns None for a
    price shown in another currency (e.g. 'GBP 112.26' when the delivery location
    isn't in the US), so it is never recorded as dollars."""
    s = (s or "").replace("\xa0", " ")
    if CURRENCY_SYMBOL not in s and CURRENCY not in s:
        return None
    return to_money(s)


def list_price_label(label):
    """Label of a struck-through price: 'List: $99.99' / 'List Price: $99.99' -> 'List Price',
    'Typical price: ...' -> 'Typical', 'Was: ...' -> 'Was', 'RRP: ...' -> 'RRP'."""
    for key, name in (("RRP", "RRP"), ("Was", "Was"), ("Typical", "Typical"), ("List", "List Price")):
        if key in label:
            return name
    return ""


def to_count(s):
    """'2,210 ratings' -> 2210, '(2.2K)' -> 2200"""
    m = re.search(r"([\d.,]+)\s*([KkMm])?", s or "")
    if not m:
        return None
    n = float(m.group(1).replace(",", ""))
    mult = {"k": 1_000, "m": 1_000_000}.get((m.group(2) or "").lower(), 1)
    return int(round(n * mult))


def full_size_image(src):
    """Drop Amazon's size suffix ("._AC_UY218_") to link the full-size image."""
    return re.sub(r"\._[^/]+_\.", ".", src or "")


def product_url(asin):
    return f"{BASE}/dp/{asin}"


def parse_asin(value):
    """'B0CG19QXWD' or an Amazon product URL -> 'B0CG19QXWD'; None if it is neither."""
    value = (value or "").strip()
    m = re.search(r"/(?:dp|gp/product|gp/aw/d|product-reviews)/(%s)" % ASIN_PATTERN, value, re.I)
    if m:
        return m.group(1).upper()
    return value.upper() if re.fullmatch(ASIN_PATTERN, value, re.I) else None


def slugify(s, limit=None):
    slug = re.sub(r"\W+", "_", s).strip("_").lower()
    return (slug[:limit].strip("_") if limit else slug) or "search"
