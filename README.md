# Amazon UK Scraper

Collect product data from **amazon.co.uk** into an Excel spreadsheet from the terminal. You can pick products in three ways:

| Mode | You give it | You get |
|---|---|---|
| **Keyword** | a search term + how many products | the search results, e.g. 500 "macbook" products |
| **ASIN Family** | one product (ASIN or link) | every variation of that product (all colours, sizes, bundles...) |
| **Ranking** | a Best Sellers / ranking page + N | the top N products with their real rank |

```bash
amazon macbook -n 200
amazon asin B0CG19QXWD
amazon ranking "https://www.amazon.co.uk/gp/bestsellers/electronics" 20
```

Every run saves an `.xlsx` workbook, plus an optional `.csv`. Each workbook has the same 24 columns (price, RRP/discount, rating, number of ratings, "bought in past month", stock, badges, delivery and more) and an **Info** sheet describing the run.

---

## Contents

- [Requirements](#requirements)
- [Installation](#installation)
- [Quick start](#quick-start)
- [The three modes](#the-three-modes)
- [All options](#all-options)
- [The spreadsheet](#the-spreadsheet)
- [Tips and troubleshooting](#tips-and-troubleshooting)
- [How it works](#how-it-works)
- [Project structure](#project-structure)
- [Known limitations](#known-limitations)
- [Responsible use](#responsible-use)

---

## Requirements

- **macOS** (Linux works too, except `--open`)
- **Python 3.10+** (developed on 3.13)
- **Google Chrome**, installed normally. The scraper drives your real Chrome, which is what lets it pass Amazon's bot check. You don't need to download any other browser.

## Installation

```bash
git clone https://github.com/sammyschen/amazon-uk-scraper.git
cd amazon-uk-scraper
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

Check that it runs:

```bash
.venv/bin/python amazon_scraper.py --help
```

### Optional: the `amazon` shortcut

This lets you type `amazon ...` from any folder instead of `.venv/bin/python amazon_scraper.py ...`. Run it **inside the project folder**:

```bash
echo "alias amazon='\"$PWD/.venv/bin/python\" \"$PWD/amazon_scraper.py\"'" >> ~/.zshrc
source ~/.zshrc
```

(Using bash? Replace `~/.zshrc` with `~/.bashrc`.) To remove the shortcut later, delete the `alias amazon=...` line from that file.

The rest of this guide uses `amazon`. Without the shortcut, write `.venv/bin/python amazon_scraper.py` instead.

## Quick start

```bash
amazon
```

With no arguments it asks what you want. Type a keyword, an ASIN, or a ranking-page link, and it works out the mode itself:

```
Search Amazon UK for (keyword, ASIN or ranking URL): dji mini 4 pro
How many products? [100]: 50
```

The finished spreadsheet is saved in the `output/` folder, and its path is printed at the end:

```
Saved 50 products -> .../output/amazon_dji_mini_4_pro_50_2026-09-24_1530.xlsx
```

---

## The three modes

### 1. Keyword mode: search results

```bash
amazon macbook -n 500            # 500 products
amazon macbook --500             # shorthand for the same thing
amazon dji mini 4 pro -n 200     # several words, no quotes needed
amazon keyword "iphone 15" 30    # explicit form: here the last number is the count
```

- The default is **100 products**.
- To reuse a search that has filters (price range, brand, Prime...), set it up in your browser and pass the link: `amazon --url "https://www.amazon.co.uk/s?k=dji&rh=..." -n 300`
- **About large numbers:** Amazon shows at most **20 result pages** per search (roughly 300–400 products). If you ask for more, the scraper re-runs the same search with Amazon's other sort orders (*Price: high to low*, *Price: low to high*, *Newest arrivals*, *Best Sellers*, *Avg. customer review*) and merges the results without duplicates. A sort order that keeps returning products already collected is skipped after 4 pages. The `found_via` column shows which sort order found each product.
- All data comes from the search result cards, so this is the fastest mode: roughly 16–22 products every ~10 seconds.

> **Watch out:** without the `keyword` prefix, trailing numbers are part of the search. `amazon iphone 15` searches for "iphone 15". Use `-n` for the count: `amazon iphone 15 -n 50`.

### 2. ASIN Family mode: every variation of one product

```bash
amazon asin B0CG19QXWD                                   # an ASIN
amazon asin https://www.amazon.co.uk/dp/B0CG19QXWD       # or a product link
amazon B0CG19QXWD                                        # a lone ASIN is detected automatically
amazon asin B0G3JL134C -n 20                             # only the first 20 of a big family
```

The **ASIN** is Amazon's product ID. It appears in every product link after `/dp/`, and under *Product information* on the page.

You can give it any of three kinds of ASIN:

- a **child**: one specific colour/size. It finds the parent, then all the siblings.
- a **parent**: the product family itself. Amazon shows its default child, and the scraper collects every child.
- a **product with no variations**: it scrapes that single product.

```
Mode: ASIN Family

Input ASIN: B0CG19QXWD
Parent ASIN: B0HC6NY128
Variation dimensions: Style Name
Child ASINs found: 3

[1/3] B0CG19QXWD (Style Name: Osmo Pocket 3) — ok: £262.00  DJI Osmo Pocket 3, ...
[2/3] B0CG19FGQ5 (Style Name: Osmo Pocket 3 Creator Combo) — ok: £399.00  DJI Osmo ...
[3/3] B0H2MTN6DM (Style Name: Osmo Pocket 3 Audio Combo ...) — ok: £448.00  DJI Osmo ...
```

- Each row's `subtitle` holds that child's variation, e.g. `Fit Type: Regular Fit; Colour: Navy; Size: M`.
- The default is **all children**. This mode opens every product page (about 10 s each), and clothing families can be huge: one T-shirt has 312 size/colour combinations, about 50 minutes. For families over 50 products it asks first. You can press Enter for all or type a number, or set a limit up front with `-n`.

### 3. Ranking mode: top N of a ranking page

```bash
amazon ranking "https://www.amazon.co.uk/gp/bestsellers/electronics" 20
amazon ranking "https://www.amazon.co.uk/gp/bestsellers/electronics"        # default: top 20
amazon --ranking "https://www.amazon.co.uk/Best-Sellers-Camera-Drones/zgbs/electronics/..." -n 50
```

- It works with **Best Sellers, New Releases, Movers & Shakers, Most Wished For and Gift Ideas** pages in any category or subcategory. Open the list on amazon.co.uk and copy the link from the address bar.
- These lists hold up to **100** products (2 pages of 50), and the `rank` column is the **real position** on the list.
- Any other Amazon product list (for example a search results link) also works. It is ranked in page order, with ads skipped.
- Like ASIN Family mode, it opens each product's page (about 10 s each). The top 20 takes about 3–4 minutes.

---

## All options

| Option | What it does |
|---|---|
| `keyword ...` | Search words (Keyword mode) |
| `-n N`, `--count N`, `--N` | How many products. Defaults: keyword **100**, ranking **20**, ASIN family **all** |
| `asin X` / `--asin X` | ASIN Family mode. `X` is an ASIN or a product link |
| `ranking URL [N]` / `--ranking URL` | Ranking mode |
| `--url URL` | Keyword mode using a full search link (keeps its filters) |
| `--csv` | Also save a `.csv` copy |
| `--open` | Open the spreadsheet when finished (macOS) |
| `--show-browser` | Show the Chrome window, needed if you must solve a CAPTCHA |
| `--out DIR` | Output folder (default: `output/` in the project folder) |
| `-h`, `--help` | Show help and examples |

---

## The spreadsheet

Files are named by mode:

```
output/amazon_macbook_500_2026-09-24_1530.xlsx                                   keyword
output/amazon_family_B0HC6NY128_3_2026-09-24_1714.xlsx                           ASIN family (parent ASIN)
output/amazon_ranking_best_sellers_in_electronics_photo_top20_2026-09-24_1722.xlsx   ranking
```

**Opening in Google Sheets:** go to *File → Import → Upload*, choose the `.xlsx`, then *Insert new sheet(s)*.

### Products sheet: one row per product, always these 24 columns

| Column | Meaning |
|---|---|
| `rank` | **Keyword:** order found · **ASIN Family:** 1, 2, 3... (the product you entered first) · **Ranking:** the actual rank on Amazon's list |
| `asin` | The product's ASIN (for families, the child ASIN) |
| `brand` | Brand name |
| `title` | Product title |
| `subtitle` | **Keyword:** the short feature line under the title · **Family / Ranking:** the product's variation, e.g. `Colour: Black; Size: M` |
| `condition` | `New` or `Renewed` (refurbished) |
| `price_gbp` | Current price in £ |
| `list_price_gbp` | The RRP or "Was" price, when Amazon shows one above the current price |
| `list_price_type` | `RRP` or `Was` (product pages occasionally say `Typical` / `List Price`) |
| `discount_pct` | % below the list price |
| `rating` | Average stars out of 5 |
| `ratings_count` | Number of ratings |
| `bought_past_month` | e.g. `500+ bought in past month` (only when Amazon shows it) |
| `stock` | Blank when simply in stock, otherwise e.g. `Only 3 left in stock`, `Currently unavailable` |
| `badge` | e.g. `Amazon's Choice`, `Best Seller in Camcorders` / `#1 Best Seller in Camcorders` |
| `deal` | e.g. `Limited time deal` |
| `advertised` | `Yes` if it appeared as a *Sponsored* ad in the search results (always `No` in Family / Ranking) |
| `delivery` | Delivery message, e.g. `FREE delivery Sunday, 27 September` |
| `other_offers` | Other sellers, e.g. `More buying choices £493.10 (3+ used & new offers)` or `New & Used (12) from £251.52` |
| `found_via` | **Keyword:** the sort order that found it (`Featured`, `Price: high to low`...) · `ASIN Family` · `Ranking` |
| `page` | Results page / ranking page it was found on (`1` for families) |
| `url` | `https://www.amazon.co.uk/dp/<ASIN>` (clickable) |
| `image_url` | Full-size main product image |
| `scraped_at` | When it was collected (`YYYY-MM-DD HH:MM`) |

The header row is frozen, every column has a filter, and prices use the £ format.

### Info sheet: a `field` / `value` summary of the run

- **Keyword:** search, search URL, requested, collected, sort orders used, time, note.
- **ASIN Family:** input ASIN, parent ASIN, variation dimensions, requested, discovered, collected, failed, time, note.
- **Ranking:** ranking URL, list name, requested, discovered, collected, failed, time, note.

**Failed** lists any product that couldn't be scraped, with the reason. One failed product never stops the rest.

---

## Tips and troubleshooting

- **Stopping early:** press **Ctrl+C**. Everything collected so far is still saved.
- **"Amazon blocked the request (CAPTCHA)":** run the same command again with `--show-browser`. A Chrome window opens; solve the CAPTCHA there and the scraper carries on (it waits up to 3 minutes).
- **Speed:** there is a 4–8 second pause between page loads on purpose, because fast scraping gets blocked. Keyword mode reads ~20 products per page; Family and Ranking modes need one page per product.
- **"page did not load after 3 attempts":** Amazon occasionally doesn't send a page. That product is listed under *Failed* and the run continues. Re-running later usually works.
- **Folder names with spaces:** quote them in the terminal, e.g. `cd "amazon data"`.
- **Delivery dates and prices** are what a UK visitor who isn't logged in would see.

## How it works

```
 Discovery layer                   Product layer                Export layer
 ───────────────                   ─────────────                ────────────
 Keyword  ─ search result cards ──────────────────────────┐
 ASIN Family ─ variation data on the product page ─┐      ├──> export_results() ──> .xlsx / .csv
 Ranking  ─ ranked list on the ranking page ───────┴──> scrape_product(asin) ──┘
                                                   (opens /dp/<ASIN>)
```

- Pages are opened in real Google Chrome through [Playwright](https://playwright.dev/python/), so Amazon's JavaScript bot check passes the same way it does for a normal visit. Plain HTTP requests just get the bot-check page.
- **Keyword** reads everything from the search result cards, with no product pages opened.
- **ASIN Family** reads the variation data Amazon embeds in every product page with variations: the parent ASIN, each child ASIN, and its colour/size/style values. Then it opens each child's page.
- **Ranking** reads the ranked list Amazon embeds in ranking pages (all 50 per page, with their ranks), then opens each product's page.
- Before each product page the browser's cookies are cleared. Amazon strips the content (title, price...) from product pages for a session that has already viewed one.

## Project structure

```
amazon_scraper.py        Command line: arguments, the three modes, progress and summary
scraper/
  browser.py             Shared Chrome session: page loading, pauses, CAPTCHA handling
  search.py              Keyword mode: search result cards, sort orders, de-duplication
  asin_family.py         ASIN Family discovery
  ranking.py             Ranking discovery
  variations.py          Reads Amazon's variation data (parent / child ASINs)
  product.py             Product page -> one spreadsheet row (shared by Family and Ranking)
  export.py              Writes the Products / Info workbook (used by every mode)
  utils.py               Small helpers (prices, counts, ASIN parsing)
docs/
  amazon_asin_scraper_implementation_spec.md   Design spec for the Family and Ranking modes
requirements.txt
output/                  Your spreadsheets (not uploaded to GitHub)
```

## Known limitations

- **amazon.co.uk only.** Prices are in £.
- **Amazon changes its pages.** If a column suddenly comes back empty, the page layout has probably changed and the matching selector in `scraper/search.py` or `scraper/product.py` needs updating.
- **Search depth:** Keyword mode can't go beyond what Amazon's 20 pages × 6 sort orders show. Ranking lists stop at 100.
- **Variation data:** a product whose options aren't in Amazon's embedded variation data is treated as a single product.
- **Not collected:** Best Seller rank number, seller name and category. The spreadsheet has a fixed 24-column layout; the parent ASIN and variation dimensions are recorded in the Info sheet.
- **Speed:** Family and Ranking modes take about 10 seconds per product.

## Responsible use

Amazon's Conditions of Use don't allow automated data collection. Use this tool for small-scale, personal research only:

- keep the built-in pauses,
- don't run many copies at once,
- don't log in with your Amazon account while scraping,
- don't republish the data commercially.
