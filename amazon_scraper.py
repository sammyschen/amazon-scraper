"""
Amazon UK scraper -> Excel (.xlsx) / CSV.  Three ways to pick the products:

  Keyword      amazon macbook -n 500              search results, read from the result cards
  ASIN Family  amazon asin B0CG19QXWD             every child/variation under the same parent
  Ranking      amazon ranking "<Best Sellers URL>" 20   top N of a ranking page (default 20)

ASIN Family and Ranking open each product's own page (scraper/product.py). All modes
write the same workbook: a Products sheet (same 24 columns) and an Info sheet.

More examples (with the `amazon` shell alias; otherwise use
`.venv/bin/python amazon_scraper.py` from this folder):
    amazon                               # asks what to scrape
    amazon macbook --500                 # same as -n 500
    amazon dji mini 4 pro -n 200 --csv --open
    amazon --url "https://www.amazon.co.uk/s?k=dji&rh=..." -n 300
    amazon asin B0G3JL134C -n 20         # a big family: only the first 20 children
    amazon --asin https://www.amazon.co.uk/dp/B0CG19QXWD
    amazon --ranking "https://www.amazon.co.uk/gp/bestsellers/electronics" -n 50

Output goes to ./output/ next to this script. Open the .xlsx in Excel, or in
Google Sheets use File > Import > Upload.
"""

import argparse
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import parse_qs, quote_plus, urlparse

from scraper.asin_family import discover_asin_family
from scraper.browser import Blocked, Browser
from scraper.export import export_results
from scraper.product import ProductError, scrape_products
from scraper.ranking import RankingError, get_ranked_products
from scraper.search import scrape_search
from scraper.utils import BASE, parse_asin, slugify

DEFAULT_COUNT = 100     # keyword mode
DEFAULT_RANKING = 20    # ranking mode
BIG_FAMILY = 50         # ask before scraping a family bigger than this
SECONDS_PER_PRODUCT = 10
RANKING_URL_RE = re.compile(
    r"/(zgbs|gp/bestsellers|gp/new-releases|gp/movers-and-shakers|gp/most-wished-for|gp/most-gifted)"
    r"|/(Best-Sellers|bestsellers|new-releases|movers-and-shakers|most-wished-for|most-gifted)", re.I)


def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def timestamp():
    return datetime.now().strftime("%Y-%m-%d_%H%M")


def eta(n):
    minutes = round(n * SECONDS_PER_PRODUCT / 60)
    return "under a minute" if minutes < 1 else f"about {minutes} min"


def detect_mode(value):
    """What the user typed -> ("asin", ASIN) | ("ranking", URL) | ("url", URL) | ("keyword", text)."""
    asin = parse_asin(value)
    if asin:
        return "asin", asin
    if re.match(r"https?://", value):
        return ("ranking" if RANKING_URL_RE.search(value) else "url"), value
    return "keyword", value


def failed_summary(failures):
    if not failures:
        return 0
    return f"{len(failures)} - " + "; ".join(f"{a} ({reason})" for a, reason in failures)


def print_totals(requested, rows, failures):
    print(f"\nTotal requested: {requested}\nSuccessful: {len(rows)}\nFailed: {len(failures)}")
    for asin, reason in failures:
        print(f"  {asin} — {reason}")


# ------------------------------------------------------------------ modes ---

def run_keyword(browser, args):
    url = args.url or f"{BASE}/s?k={quote_plus(args.keyword)}"
    search = args.keyword or parse_qs(urlparse(url).query).get("k", ["search"])[0]
    print(f'Mode: Keyword\n\nCollecting {args.count} products for "{search}" from amazon.co.uk ...\n')

    rows, note = scrape_search(browser, url, args.count)
    print(f"\n{note}")
    info = {
        "Search": search,
        "Search URL": url,
        "Requested": args.count,
        "Collected": len(rows),
        "Sort orders used": ", ".join(dict.fromkeys(r["found_via"] for r in rows)),
        "Scraped at": now(),
        "Note": note,
        "rank": "Order the product was found in: the first sort order's pages first, then the next.",
    }
    return rows, info, f"amazon_{slugify(search)}_{len(rows)}_{timestamp()}"


def run_asin_family(browser, args):
    print(f"Mode: ASIN Family\n\nInput ASIN: {args.asin}")
    family = discover_asin_family(browser, args.asin)
    children = family["children"]
    parent = family["parent_asin"]
    if not family["has_variations"]:
        print("Parent ASIN: none - this product has no variations")
    else:
        print(f"Parent ASIN: {parent or 'not detected'}"
              + ("  (the input is the parent)" if parent == args.asin else ""))
        print(f"Variation dimensions: {', '.join(family['dimensions']) or 'unknown'}")
    print(f"Child ASINs found: {len(children)}")

    limit = args.count
    if limit is None and len(children) > BIG_FAMILY and sys.stdin.isatty():
        answer = input(f"\nScraping all {len(children)} takes {eta(len(children))}. "
                       f"Press Enter for all, or type how many: ").strip()
        limit = int(answer) if answer.isdigit() and int(answer) > 0 else None
    items = children[:limit] if limit else children
    print(f"\nScraping {len(items)} product page(s), {eta(len(items))} ...\n")

    rows, failures, stop_note = scrape_products(
        browser, items, "ASIN Family", cached_pages=family["pages"],
        describe=lambda it: it["asin"] + (f" ({it['variation']})" if it["variation"] else ""))
    for i, r in enumerate(rows, start=1):
        r["rank"], r["page"] = i, 1
    print_totals(len(items), rows, failures)

    if stop_note:
        note = stop_note
    elif not family["has_variations"]:
        note = "The product has no variations, so it was scraped as a single-product family."
    elif len(items) < len(children):
        note = f"Collected the first {len(items)} of {len(children)} child products (limit set with -n)."
    else:
        note = "Collected all discoverable child products under the parent ASIN."
    if failures:
        note += f" {len(failures)} product page(s) failed - see Failed."
    info = {
        "Mode": "ASIN Family",
        "Input ASIN": args.asin,
        "Parent ASIN": parent if parent else ("Not detected" if family["has_variations"]
                                              else "None - the product has no variations"),
        "Variation dimensions": ", ".join(family["dimensions"]) or "No variations",
        "Requested": ("All discovered child ASINs" if len(items) == len(children)
                      else f"First {len(items)} of {len(children)} child ASINs"),
        "Discovered": len(children),
        "Collected": len(rows),
        "Failed": failed_summary(failures),
        "Scraped at": now(),
        "Note": note,
        "rank": "Sequential output order for ASIN Family Mode (the product shown for the input ASIN first).",
        "subtitle": "The child's variation, e.g. Colour: Black; Size: M.",
    }
    return rows, info, f"amazon_family_{parent or args.asin}_{len(rows)}_{timestamp()}"


def run_ranking(browser, args):
    print("Mode: Ranking\n")
    items, title, discovered = get_ranked_products(browser, args.ranking, args.count)
    print(f"Ranking page loaded: {title or args.ranking}")
    print(f"Products discovered: {discovered}\nRequested: Top {args.count}")
    if len(items) < args.count:
        print(f"Only {len(items)} ranked products are available.")
    print(f"\nScraping {len(items)} product pages, {eta(len(items))} ...\n")

    rows, failures, stop_note = scrape_products(
        browser, items, "Ranking", describe=lambda it: f"Rank #{it['rank']} — {it['asin']}")
    print_totals(len(items), rows, failures)

    if stop_note:
        note = stop_note
    elif len(items) < args.count:
        note = f"Only {len(items)} ranked products were available on the ranking page(s)."
    else:
        note = "Collected the requested ranked products."
    if failures:
        note += f" {len(failures)} product page(s) failed - see Failed."
    info = {
        "Mode": "Ranking",
        "Ranking URL": args.ranking,
        "Ranking list": title,
        "Requested": args.count,
        "Discovered": discovered,
        "Collected": len(rows),
        "Failed": failed_summary(failures),
        "Scraped at": now(),
        "Note": note,
        "rank": "Actual Amazon ranking position.",
    }
    return rows, info, f"amazon_ranking_{slugify(title or 'list', 40)}_top{args.count}_{timestamp()}"


# ------------------------------------------------------------------- main ---

def parse_args():
    argv = []
    for a in sys.argv[1:]:  # allow the shorthand "--500" / "-500" for "-n 500"
        m = re.fullmatch(r"--?(\d+)", a)
        argv += ["-n", m.group(1)] if m else [a]
    # spec-style forms: "asin B0..", "ranking URL [N]", "keyword words [N]"
    explicit_keyword = bool(argv) and argv[0] == "keyword"
    if explicit_keyword:
        argv = argv[1:]
    elif len(argv) > 1 and argv[0] in ("asin", "ranking"):
        argv = [f"--{argv[0]}"] + argv[1:]

    ap = argparse.ArgumentParser(
        prog="amazon",
        description="Scrape Amazon UK products into Excel - by keyword, ASIN family or ranking page.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="examples:\n"
               "  amazon                          ask what to scrape\n"
               "  amazon macbook -n 500           500 MacBook search results (also: --500)\n"
               "  amazon dji mini 4 pro -n 200 --csv --open\n"
               "  amazon asin B0CG19QXWD          every variation of this product\n"
               "  amazon asin B0G3JL134C -n 20    ...only the first 20 of a big family\n"
               '  amazon ranking "https://www.amazon.co.uk/gp/bestsellers/electronics" 20\n'
               '  amazon --url "https://www.amazon.co.uk/s?k=..." -n 300',
    )
    ap.add_argument("keyword", nargs="*", help="what to search for (several words are fine)")
    ap.add_argument("-n", "--count", type=int,
                    help=f"how many products (keyword default {DEFAULT_COUNT}, ranking default "
                         f"{DEFAULT_RANKING}, ASIN family default all)")
    ap.add_argument("--asin", help="ASIN or product URL: scrape every child under its parent")
    ap.add_argument("--ranking", metavar="URL", help="ranking page (Best Sellers etc.): scrape the top N")
    ap.add_argument("--url", help="a full amazon.co.uk search URL instead of a keyword (keeps its filters)")
    ap.add_argument("--csv", action="store_true", help="also write a .csv next to the .xlsx")
    ap.add_argument("--open", action="store_true", help="open the spreadsheet when finished")
    ap.add_argument("--show-browser", action="store_true", help="show Chrome (needed to solve a CAPTCHA)")
    ap.add_argument("--out", default="output", help="output folder (default: output/ next to this script)")
    args = ap.parse_args(argv)

    words = list(args.keyword)
    if (args.asin or args.ranking or explicit_keyword) and words and words[-1].isdigit() \
            and args.count is None:
        args.count = int(words.pop())  # "ranking URL 20", "keyword mouse 20"
    if (args.asin or args.ranking) and words:
        ap.error(f"unexpected words: {' '.join(words)}")
    keyword = " ".join(words).strip()
    if sum(map(bool, (args.asin, args.ranking, args.url, keyword))) > 1:
        ap.error("give only one of: keyword, --asin, --ranking, --url")

    if args.asin:
        args.mode, value = "asin", args.asin
    elif args.ranking:
        args.mode, value = "ranking", args.ranking
    elif args.url:
        args.mode, value = "url", args.url
    elif keyword:
        args.mode, value = ("keyword", keyword) if explicit_keyword or len(words) > 1 \
            else detect_mode(keyword)  # a lone ASIN or URL picks its own mode
    else:  # nothing given: ask
        try:
            value = ""
            while not value:
                value = input("Search Amazon UK for (keyword, ASIN or ranking URL): ").strip()
            args.mode, value = detect_mode(value)
            if args.mode != "asin" and args.count is None:
                default = DEFAULT_RANKING if args.mode == "ranking" else DEFAULT_COUNT
                answer = input(f"How many products? [{default}]: ").strip()
                args.count = int(answer) if answer.isdigit() else default
        except (KeyboardInterrupt, EOFError):
            sys.exit("\nCancelled.")

    args.asin = args.ranking = args.url = args.keyword = None
    if args.mode == "asin":
        args.asin = parse_asin(value)
        if not args.asin:
            ap.error(f"'{value}' is not a valid ASIN (10 characters, e.g. B0CG19QXWD) or product URL")
    elif args.mode == "ranking":
        if not re.match(r"https?://(www\.)?amazon\.co\.uk/", value):
            ap.error("the ranking page must be an https://www.amazon.co.uk/... URL")
        args.ranking = value
        args.count = args.count or DEFAULT_RANKING
    else:
        args.url = value if args.mode == "url" else None
        args.keyword = value if args.mode == "keyword" else None
        args.mode = "keyword"
        args.count = args.count or DEFAULT_COUNT
    if args.count is not None and args.count < 1:
        ap.error("the product count must be at least 1")
    return args


def main():
    args = parse_args()
    run = {"keyword": run_keyword, "asin": run_asin_family, "ranking": run_ranking}[args.mode]
    try:
        with Browser(show=args.show_browser) as browser:
            rows, info, stem = run(browser, args)
    except KeyboardInterrupt:
        sys.exit("\nCancelled.")
    except (ProductError, RankingError, Blocked) as e:  # discovery failed: nothing to save
        sys.exit(f"\nCould not continue: {e}")
    if not rows:
        sys.exit("\nNo products scraped. " + str(info.get("Note", "")))

    out_dir = Path(__file__).resolve().parent / args.out
    out_dir.mkdir(parents=True, exist_ok=True)
    files = export_results(rows, info, out_dir / stem, csv=args.csv)
    print(f"\nSaved {len(rows)} products -> {files[0]}")
    for f in files[1:]:
        print(f"Also saved -> {f}")
    if args.open:
        subprocess.run(["open", str(files[0])], check=False)


if __name__ == "__main__":
    main()
