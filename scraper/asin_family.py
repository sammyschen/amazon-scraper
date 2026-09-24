"""
ASIN Family discovery: one ASIN (parent, child or stand-alone) -> every child ASIN
under the same parent.

Opening a parent ASIN makes Amazon show its default child; either way the page
carries the whole family's variation data (see variations.py), so one page load
discovers the family. That page is handed on so its child isn't loaded twice.
"""

from .product import load_product_page
from .variations import get_child_asins, get_dimensions, get_parent_asin, page_asin


def discover_asin_family(browser, asin):
    """Returns {input_asin, parent_asin, has_variations, dimensions,
    children: [{"asin", "variation"}], pages: {asin: html}}.
    Raises ProductError if the input ASIN can't be loaded."""
    html = load_product_page(browser, asin)
    shown = page_asin(html, asin)  # the child Amazon displays for this ASIN
    children = get_child_asins(html)
    family = {
        "input_asin": asin,
        "parent_asin": get_parent_asin(html),
        "has_variations": bool(children),
        "dimensions": get_dimensions(html),
        "pages": {shown: html},
    }
    # The product shown for the input ASIN comes first, then its siblings in option order.
    first = next((c for c in children if c["asin"] == shown), {"asin": shown, "variation": ""})
    family["children"] = [first] + [c for c in children if c["asin"] != shown]
    return family
