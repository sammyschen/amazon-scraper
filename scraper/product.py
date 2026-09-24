"""
Product layer: open /dp/{asin} and turn the page into one row of the approved
24-column schema - the same fields the keyword mode reads from search cards.

Column conventions on product pages:
  subtitle   the product's variation, e.g. "Colour: Black; Size: M" (search cards
             show a one-line feature summary there; product pages have none)
  stock      blank when simply "In stock", otherwise Amazon's availability note
  advertised always "No" - a product page is not an ad placement
"""

import re
from datetime import datetime

from bs4 import BeautifulSoup
from playwright.sync_api import Error as PlaywrightError

from .browser import Blocked
from .utils import BASE, full_size_image, product_url, text, to_count, to_money
from .variations import page_asin, variation_of

PRODUCT_READY = "#productTitle"
ATTEMPTS = 3  # retries for pages that time out or come back empty

PRICE_SELECTORS = [
    "#corePriceDisplay_desktop_feature_div .priceToPay",
    "#corePriceDisplay_desktop_feature_div .a-price:not(.a-text-price)",
    "#corePrice_feature_div .a-price:not(.a-text-price)",
    "#corePrice_desktop .a-price:not(.a-text-price)",
    "#apex_desktop .a-price:not(.a-text-price)",
    "#tp_price_block_total_price_ww",
]
OLD_PRICE_IDS = "#price_inside_buybox, #priceblock_ourprice, #priceblock_dealprice, #kindle-price, #price"
LIST_PRICE_SELECTORS = [
    "#corePriceDisplay_desktop_feature_div .basisPrice",
    "#corePrice_feature_div .basisPrice",
    "#corePrice_desktop .a-text-price",
    "#apex_desktop .basisPrice",
]
DEAL_RE = re.compile(r"Limited time deal|Limited Prime deal|Lightning deal|Deal of the Day|"
                     r"Prime (?:Big )?Day deal|Black Friday deal|Cyber Monday deal", re.I)


class ProductError(Exception):
    """This product could not be scraped (the batch carries on without it)."""


# ---------------------------------------------------------------- loading ---

def load_product_page(browser, asin):
    """HTML of the product page. Raises ProductError if the product doesn't exist or
    the page won't load after retries, Blocked on a CAPTCHA."""
    url = f"{BASE}/dp/{asin}?th=1&psc=1"  # th/psc: show exactly this variation
    problem = "page did not load"
    for _ in range(ATTEMPTS):
        try:
            # A session that has already viewed a product page gets later product pages
            # without their content (title, price...), so each one starts cookie-free.
            browser.clear_cookies()
            if browser.load(url, PRODUCT_READY, timeout=15_000):
                return browser.html()
        except PlaywrightError as e:  # network hiccup; a closed browser can't be retried
            if "closed" in str(e):
                raise
            problem = str(e).splitlines()[0]
            continue
        if browser.status == 404:
            raise ProductError("product does not exist (page not found)")
    raise ProductError(f"{problem} after {ATTEMPTS} attempts")


# ---------------------------------------------------------------- parsing ---

def _price(el):
    """Price of an .a-price element: its hidden '£1,299.00' text, else the visible parts."""
    if not el:
        return None
    price = to_money(text(el.select_one(".a-offscreen")))
    if price is None:
        whole = re.sub(r"[^\d,]", "", text(el.select_one(".a-price-whole")))
        frac = re.sub(r"\D", "", text(el.select_one(".a-price-fraction")))
        price = to_money(f"{whole}.{frac}" if whole and frac else whole)
    return price


def _first(soup, selectors, parse):
    for sel in selectors:
        for el in soup.select(sel):
            value = parse(el)
            if value not in (None, ""):
                return value, el
    return None, None


def parse_product_page(html, asin):
    """One output row (without rank / page / found_via / scraped_at) from a product page."""
    asin = page_asin(html, asin)
    variation = variation_of(html, asin)
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    top = soup.select_one("#ppd") or soup  # the product's own area, not the carousels below

    title = text(soup.select_one("#productTitle"))
    byline = re.sub(r"^(Visit the|Brand:)\s+|\s+Store$", "", text(soup.select_one("#bylineInfo")))
    brand = text(soup.select_one("tr.po-brand td.a-span9")) or byline

    price, _ = _first(soup, PRICE_SELECTORS, _price)
    if price is None:
        price = to_money(text(soup.select_one(OLD_PRICE_IDS)))
    list_price, list_el = _first(soup, LIST_PRICE_SELECTORS,
                                 lambda el: to_money(text(el.select_one(".a-offscreen") or el)))
    list_type = ""
    if list_el:
        label = text(list_el) + " " + text(list_el.parent)
        list_type = next((t for t in ("RRP", "Was", "Typical", "List Price") if t in label), "")
    if not (price and list_price and list_price > price):
        list_price, list_type = None, ""
    discount = round((1 - price / list_price) * 100, 1) if list_price else None

    rating = re.search(r"([\d.]+) out of 5", (soup.select_one("#acrPopover") or {}).get("title", "")
                       or text(soup.select_one("#averageCustomerReviews .a-icon-alt")))
    bought = re.search(r"[\d.,]+[KkM]?\+? bought in past month", text(top))

    availability = text(soup.select_one("#availability")) or text(soup.select_one("#outOfStock"))
    stock = ("" if not availability or availability.lower().startswith("in stock")
             else re.split(r"(?<=\.)\s", availability)[0].rstrip("."))

    best_seller = re.search(r"#[\d,]+ Best Seller in .+", text(soup.select_one("#zeitgeistBadge_feature_div")))
    choice = "Amazon's Choice" if "Amazon's Choice" in text(soup.select_one("#acBadge_feature_div")) else ""
    deal = DEAL_RE.search(" ".join(text(e) for e in soup.select(
        "#dealBadge_feature_div, #corePriceDisplay_desktop_feature_div, #apex_desktop")))

    delivery = text(soup.select_one("#mir-layout-DELIVERY_BLOCK-slot-PRIMARY_DELIVERY_MESSAGE_LARGE")) \
        or text(soup.select_one("#deliveryBlockMessage"))
    delivery = re.split(r"\s*(?:Or fastest delivery|Details|Order within)", delivery)[0].strip(" .")

    offers_text = " ".join(text(e) for e in soup.select(
        "#olpLinkWidget_feature_div, #buybox-see-all-buying-choices, #usedAccordionRow"))
    offers = re.search(r"(?:New & Used|New|Used)\s*\(\d+\)\s*from\s*£[\d,]+(?:\.\d+)?", offers_text)

    img = soup.select_one("#landingImage, #imgTagWrapperId img, #main-image, #imgBlkFront")
    image = (img.get("data-old-hires") or img.get("src") or "") if img else ""
    if image.startswith("data:") and img.get("data-a-dynamic-image"):
        image = next(iter(re.findall(r'"(https://[^"]+)"', img["data-a-dynamic-image"])), "")

    return {
        "asin": asin,
        "brand": brand,
        "title": title,
        "subtitle": variation,
        "condition": "Renewed" if re.search(r"\b(Renewed|Refurbished)\b", f"{brand} {title}") else "New",
        "price_gbp": price,
        "list_price_gbp": list_price,
        "list_price_type": list_type,
        "discount_pct": discount,
        "rating": float(rating.group(1)) if rating else None,
        "ratings_count": to_count(text(soup.select_one("#acrCustomerReviewText"))),
        "bought_past_month": bought.group() if bought else "",
        "stock": stock,
        "badge": best_seller.group().strip() if best_seller else choice,
        "deal": deal.group() if deal else "",
        "advertised": False,
        "delivery": delivery,
        "other_offers": offers.group() if offers else "",
        "url": product_url(asin),
        "image_url": full_size_image(image),
    }


def scrape_product(browser, asin):
    """The shared product scraper: ASIN -> one output row."""
    return parse_product_page(load_product_page(browser, asin), asin)


# ------------------------------------------------------------------ batch ---

def scrape_products(browser, items, found_via, cached_pages=None, describe=None):
    """Scrape each discovered item ({"asin", optional "rank", "page", "variation"}).
    One failed product never stops the batch; a CAPTCHA or Ctrl+C stops it and keeps
    what was collected. Returns (rows, failures [(asin, reason)], stop_note)."""
    cached_pages = dict(cached_pages or {})
    describe = describe or (lambda item: item["asin"])
    rows, failures, seen, note = [], [], set(), ""
    total = len(items)
    try:
        for i, item in enumerate(items, start=1):
            prefix = f"[{i}/{total}] {describe(item)}"
            try:
                html = cached_pages.pop(item["asin"], None) or load_product_page(browser, item["asin"])
                row = parse_product_page(html, item["asin"])
            except ProductError as e:
                failures.append((item["asin"], str(e)))
                print(f"{prefix} — failed: {e}")
                continue
            except PlaywrightError as e:
                if "closed" in str(e):
                    raise
                reason = str(e).splitlines()[0]
                failures.append((item["asin"], reason))
                print(f"{prefix} — failed: {reason}")
                continue
            if row["asin"] in seen:  # Amazon redirected to a product already collected
                print(f"{prefix} — same product as an earlier row ({row['asin']}), skipped")
                continue
            seen.add(row["asin"])
            row.update(rank=item.get("rank"), page=item.get("page", 1), found_via=found_via,
                       scraped_at=datetime.now().strftime("%Y-%m-%d %H:%M"))
            row["subtitle"] = row["subtitle"] or item.get("variation", "")
            rows.append(row)
            price = f"£{row['price_gbp']:,.2f}" if row["price_gbp"] else "no price"
            print(f"{prefix} — ok: {price}  {row['title'][:60]}")
    except Blocked as e:
        note = str(e)
        print("\n" + note)
    except KeyboardInterrupt:
        note = "Stopped early with Ctrl+C."
        print("\nStopping - saving what was collected...")
    except PlaywrightError as e:
        note = f"Browser stopped: {str(e).splitlines()[0]}"
        print("\n" + note)
    return rows, failures, note
