"""
Keyword discovery: Amazon search results -> rows, read straight from the result cards.

Amazon only shows 20 result pages per search (~300-400 products). If more are
wanted, the same search is repeated under Amazon's other sort orders
(Price high/low, Newest, Best Sellers, Avg. customer review) and merged without
duplicates. A sort order that keeps returning products already collected is skipped.
"""

import re
from datetime import datetime
from urllib.parse import parse_qs, urlencode, urljoin, urlparse

from bs4 import BeautifulSoup
from playwright.sync_api import Error as PlaywrightError

from .browser import Blocked
from .utils import BASE, full_size_image, product_url, text, to_count, to_money

RESULT_SELECTOR = 'div[data-component-type="s-search-result"]'
# Amazon's sort orders, in the order they are tried when more products are needed.
# Price sorts come first: they reach products the Featured pages didn't, whereas
# Best Sellers / reviews mostly repeat the same popular items.
SORTS = {
    "relevanceblender": "Featured",
    "price-desc-rank": "Price: high to low",
    "price-asc-rank": "Price: low to high",
    "date-desc-rank": "Newest arrivals",
    "exact-aware-popularity-rank": "Best Sellers",
    "review-rank": "Avg. customer review",
}
# Give up on a sort order after this many pages in a row with <= STALL_NEW new products.
STALL_PAGES, STALL_NEW = 4, 2


# ---------------------------------------------------------------- parsing ---

def parse_card(card):
    asin = card.get("data-asin", "").strip()
    if not asin:
        return None
    card_text = text(card)

    img = card.select_one("img.s-image")
    title_link = card.select_one('[data-cy="title-recipe"] a h2')
    title = (title_link.get("aria-label") or text(title_link)) if title_link else ""
    if not title and img:  # fallback: image alt text holds the (truncated) full title
        title = img.get("alt", "")
    title = re.sub(r"^Sponsored Ad\s*[–-]\s*", "", title)
    brand = text(card.select_one('[data-cy="title-recipe"] h2.s-line-clamp-1'))

    price_box = card.select_one('[data-cy="price-recipe"]')
    price = list_price = None
    list_type = ""
    if price_box:
        current = price_box.select_one(".a-price:not(.a-text-price) .a-offscreen")
        price = to_money(text(current))
        struck = price_box.select_one(".a-price.a-text-price")
        if struck:
            list_price = to_money(text(struck.select_one(".a-offscreen")))
            label = text(struck.parent)
            list_type = "RRP" if "RRP" in label else "Was" if "Was" in label else ""
    discount = (
        round((1 - price / list_price) * 100, 1)
        if price and list_price and list_price > price else None
    )

    reviews = card.select_one('[data-cy="reviews-block"]')
    rating = ratings_count = None
    bought = ""
    if reviews:
        m = re.search(r"([\d.]+) out of 5", text(reviews.select_one(".a-icon-alt")))
        rating = float(m.group(1)) if m else None
        count_link = reviews.select_one('a[aria-label$="ratings"], a[aria-label$="rating"]')
        ratings_count = to_count(count_link.get("aria-label") if count_link else "")
        m = re.search(r"[\d.,]+[KkM]?\+? bought in past month", text(reviews))
        bought = m.group() if m else ""

    stock = re.search(
        r"Only \d+ left in stock(?: \(more on the way\))?|Temporarily out of stock|Currently unavailable",
        card_text,
    )

    return {
        "asin": asin,
        "brand": brand,
        "title": title,
        "subtitle": text(card.select_one(".title-differentiators")),
        "condition": "Renewed" if re.search(r"\b(Renewed|Refurbished)\b", f"{brand} {title}") else "New",
        "price_gbp": price,
        "list_price_gbp": list_price,
        "list_price_type": list_type,
        "discount_pct": discount,
        "rating": rating,
        "ratings_count": ratings_count,
        "bought_past_month": bought,
        "stock": stock.group() if stock else "",
        "badge": text(card.select_one(
            "[data-component-type='s-status-badge-component'], .puis-status-badge-container"
        )),
        "deal": "Limited time deal" if "Limited time deal" in text(price_box) else "",
        "advertised": bool(card.select_one(".puis-sponsored-label-text")),
        "delivery": text(card.select_one(".udm-primary-delivery-message")),
        "other_offers": text(card.select_one('[data-cy="secondary-offer-recipe"]')),
        "url": product_url(asin),
        "image_url": full_size_image(img.get("src", "")) if img else "",
    }


def parse_page(html):
    soup = BeautifulSoup(html, "lxml")
    rows = [r for r in (parse_card(c) for c in soup.select(RESULT_SELECTOR)) if r]
    nxt = soup.select_one("a.s-pagination-next[href]")
    return rows, (urljoin(BASE, nxt["href"]) if nxt else None)


# ------------------------------------------------------------ search URLs ---

def with_sort(url, sort):
    """Same search, different sort order, back on page 1."""
    parts = urlparse(url)
    query = {k: v[0] for k, v in parse_qs(parts.query).items()
             if k not in ("s", "page", "ref", "qid", "xpid")}
    query["s"] = sort
    return parts._replace(query=urlencode(query)).geturl()


def search_passes(url):
    """[(sort label, url), ...] - the URL as given first, then the other sort orders."""
    current = parse_qs(urlparse(url).query).get("s", ["relevanceblender"])[0]
    passes = [(SORTS.get(current, current), url)]
    passes += [(label, with_sort(url, s)) for s, label in SORTS.items() if s != current]
    return passes


# ---------------------------------------------------------------- running ---

def add(found, row):
    """Keep one row per ASIN; returns 1 if the product is new. A product shown both
    as an ad and as a normal result keeps its normal (organic) position."""
    prev = found.get(row["asin"])
    if prev is None:
        found[row["asin"]] = row
        return 1
    if prev["advertised"] and not row["advertised"]:
        row["advertised"] = True
        found[row["asin"]] = row
    else:
        prev["advertised"] = prev["advertised"] or row["advertised"]
    return 0


def scrape_search(browser, url, target):
    """Collect `target` unique products for a search URL. Returns (rows, note);
    rows are ranked 1..n in the order found."""
    found, note = {}, ""
    try:
        for pass_no, (sort_label, next_url) in enumerate(search_passes(url)):
            if len(found) >= target:
                break
            if pass_no:
                print(f"\nRe-sorting by '{sort_label}' to find more...")
            page_no = stalled = 0
            while next_url and len(found) < target:
                if stalled >= STALL_PAGES:
                    print("  (mostly products already collected - moving on)")
                    break
                page_no += 1
                if not browser.load(next_url, RESULT_SELECTOR):
                    break  # nothing on this page - try the next sort order
                rows, next_url = parse_page(browser.html())
                stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
                new = 0
                for pos, r in enumerate(rows):
                    r.update(page=page_no, found_via=sort_label, scraped_at=stamp,
                             _order=(pass_no, page_no, pos))
                    new += add(found, r)
                stalled = stalled + 1 if new <= STALL_NEW else 0
                print(f"  [{sort_label}] page {page_no:>2}: {len(rows)} products, "
                      f"{new} new  ->  {min(len(found), target)}/{target}")
                if not next_url:
                    print("  (Amazon has no more pages for this order)")
    except Blocked as e:
        note = str(e)
        print("  " + note)
    except KeyboardInterrupt:
        note = "Stopped early with Ctrl+C."
        print("\nStopping - saving what was collected...")
    except PlaywrightError as e:
        if not found:
            raise
        note = f"Browser error, saved what was collected: {e}"
        print("\n" + note)
    if not note:
        note = (f"Collected the {target} products requested." if len(found) >= target else
                f"Only {len(found)} products exist for this search across all sort orders.")

    rows = sorted(found.values(), key=lambda r: r["_order"])[:target]
    for i, r in enumerate(rows, start=1):
        r["rank"] = i
    return rows, note
