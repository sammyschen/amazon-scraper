"""
Ranking discovery: an Amazon ranking page -> the top N ASINs with their rank.

Works with Best Sellers, New Releases, Movers & Shakers, Most Wished For and Gift
Ideas pages (any category), which list 50 products per page with a "Next page"
for 51-100. As a fallback, any other Amazon product list (e.g. a search results
URL) is ranked in page order, skipping ads.
"""

import json
import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .utils import ASIN_PATTERN, BASE, text

RANKING_READY = ("[data-client-recs-list], #gridItemRoot, "
                 "div[data-component-type='s-search-result'], [data-asin]")
ATTEMPTS = 3  # a fresh session's first page sometimes doesn't come through


class RankingError(Exception):
    """The ranking page could not be loaded or parsed."""


def _is_asin(value):
    return bool(re.fullmatch(ASIN_PATTERN, value or ""))


def parse_ranking_page(html, offset=0):
    """([{"asin", "rank"}, ...], next page URL or None, list title)."""
    soup = BeautifulSoup(html, "lxml")
    items = []

    # 1) Best Sellers & co. embed the whole ranked list (all 50) as JSON.
    for el in soup.select("[data-client-recs-list]"):
        try:
            recs = json.loads(el["data-client-recs-list"])
        except ValueError:
            continue
        for rec in recs:
            rank = str((rec.get("metadataMap") or {}).get("render.zg.rank", ""))
            if _is_asin(rec.get("id")):
                items.append({"asin": rec["id"], "rank": int(rank) if rank.isdigit() else None})
        if items:
            break

    # 2) Same pages without the JSON: rank badges ("#12") on the grid items.
    if not items:
        for g in soup.select("#gridItemRoot"):
            holder = g.select_one("[data-asin]")
            badge = re.sub(r"\D", "", text(g.select_one(".zg-bdg-text")))
            if holder and _is_asin(holder.get("data-asin")):
                items.append({"asin": holder["data-asin"], "rank": int(badge) if badge else None})

    # 3) Any other product list, in page order (ads skipped).
    if not items:
        cards = soup.select('div[data-component-type="s-search-result"]') or soup.select("[data-asin]")
        for c in cards:
            if _is_asin(c.get("data-asin")) and not c.select_one(".puis-sponsored-label-text"):
                items.append({"asin": c["data-asin"], "rank": None})

    for pos, it in enumerate(items, start=1):
        it["rank"] = it["rank"] or offset + pos
    nxt = soup.select_one("ul.a-pagination li.a-last a[href], a.s-pagination-next[href]")
    headings = [text(h) for h in soup.select("h1")]
    title = next((h for h in headings if h and h != "Amazon Best Sellers"), "") \
        or text(soup.select_one("title")).split(":")[0].strip()
    return items, (urljoin(BASE, nxt["href"]) if nxt else None), title


def get_ranked_products(browser, url, limit=20):
    """Top `limit` products of a ranking page, sorted by rank and de-duplicated
    (first rank wins). Returns (items [{"asin", "rank", "page"}], title, discovered)."""
    items, seen, title, next_url, page_no = [], set(), "", url, 0
    while next_url and len(items) < limit:
        page_no += 1
        if not any(browser.load(next_url, RANKING_READY) for _ in range(ATTEMPTS)):
            if page_no == 1:
                raise RankingError("The ranking page could not be loaded.")
            break
        found, next_url, page_title = parse_ranking_page(browser.html(), offset=len(items))
        title = title or page_title
        if not found and page_no == 1:
            raise RankingError("No ranked products were found on this page.")
        for it in sorted(found, key=lambda it: it["rank"]):
            if it["asin"] not in seen:
                seen.add(it["asin"])
                items.append({**it, "page": page_no})
        print(f"  Ranking page {page_no}: {len(found)} products")
    items.sort(key=lambda it: it["rank"])
    return items[:limit], title, len(items)
